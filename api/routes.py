import json
import uuid

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import StreamingResponse
from slowapi.util import get_remote_address
from slowapi import Limiter

from src.schemas.api import AdviceRequest, HumanReviewRequest
from src.schemas.recommendation import AdviceResponse
from src.agent.graph import build_course_advisor_graph
from src.evals.retrieval_eval import evaluate_pipeline


router = APIRouter()

# Limit requests per client
limiter = Limiter(key_func=get_remote_address)

# Build the graph once globally
graph_app = build_course_advisor_graph()



COST_PER_MILLION_INPUT_TOKENS = 2.50
COST_PER_MILLION_OUTPUT_TOKENS = 10.00


def estimate_cost_usd(input_tokens: int, output_tokens: int) -> float:
    return (
        (input_tokens / 1_000_000) * COST_PER_MILLION_INPUT_TOKENS
        + (output_tokens / 1_000_000) * COST_PER_MILLION_OUTPUT_TOKENS
    )



# HELPERS
def make_event(event_type: str, message: str, data=None):
    """
    Convert an internal event into a Server-Sent Event.
    """

    payload = {
        "type": event_type,
        "message": message,
    }

    if data is not None:
        payload["data"] = data

    return f"data: {json.dumps(payload, default=str)}\n\n"


def build_usage_payload(state_values: dict) -> dict:
    """
    Pull the running token totals out of the graph's final state and
    turn them into the small dict the frontend expects to find under
    `data.usage` on the "final" event.
    """

    input_tokens = state_values.get("total_input_tokens", 0) or 0
    output_tokens = state_values.get("total_output_tokens", 0) or 0

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": round(
            estimate_cost_usd(input_tokens, output_tokens),
            6,
        ),
    }



# STREAMING ADVISOR
@router.post("/advise/stream")
@limiter.limit("10/minute")
async def advise_stream(request: Request, body: AdviceRequest):

    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    initial_state = {
        "user_query": body.query,
        "messages": [],
        "parsed_filters": None,
        "retrieved_courses": [],
        "violations": [],
        "requires_human_review": False,
        "human_decision": None,
        "parsing_failed": False,
        "integrity_flags": [],
        "final_advice": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }

    async def event_generator():

        try:

            
            # START
            

            yield make_event(
                "start",
                "🚀 Starting Course Advisor...",
                {
                    "thread_id": thread_id
                }
            )

            
            # STREAM LANGGRAPH EVENTS
            

            for event in graph_app.stream(
                initial_state,
                config=config,
                stream_mode="updates",
            ):

                # event is usually:
                #
                # {
                #     "node_name": {
                #         "state_update": ...
                #     }
                # }

                if not event:
                    continue

                for node_name, update in event.items():

                    # PARSING

                    if node_name == "parse_query_node":

                        yield make_event(
                            "node",
                            "🧠 Parsing your academic request...",
                            {
                                "node": node_name
                            }
                        )

                        yield make_event(
                            "complete",
                            "✅ Request successfully parsed.",
                            {
                                "node": node_name
                            }
                        )

                    # RETRIEVAL

                    elif node_name == "retrieve_courses_node":

                        retrieved = []

                        if isinstance(update, dict):
                            retrieved = update.get(
                                "retrieved_courses",
                                []
                            )

                        yield make_event(
                            "node",
                            "🔍 Searching the course catalog...",
                            {
                                "node": node_name
                            }
                        )

                        yield make_event(
                            "complete",
                            f"✅ Course retrieval completed. "
                            f"Found {len(retrieved)} candidate courses.",
                            {
                                "node": node_name,
                                "count": len(retrieved)
                            }
                        )

                    # CRITIC

                    elif node_name == "constraint_critic_node":

                        yield make_event(
                            "node",
                            "🛡️ Checking prerequisites and hard constraints...",
                            {
                                "node": node_name
                            }
                        )

                        violations = []

                        if isinstance(update, dict):
                            violations = update.get(
                                "violations",
                                []
                            )

                        requires_review = False

                        if isinstance(update, dict):
                            requires_review = update.get(
                                "requires_human_review",
                                False
                            )

                        if requires_review:

                            yield make_event(
                                "human_review",
                                "⚠️ The request requires human advisor review.",
                                {
                                    "node": node_name,
                                    "violations": violations,
                                    "thread_id": thread_id
                                }
                            )

                        else:

                            yield make_event(
                                "complete",
                                "✅ Constraint validation completed.",
                                {
                                    "node": node_name,
                                    "violations": violations
                                }
                            )

                    # HUMAN REVIEW

                    elif node_name == "human_review_node":

                        decision = None

                        if isinstance(update, dict):
                            decision = update.get(
                                "human_decision"
                            )

                        yield make_event(
                            "human_review",
                            "👤 Human advisor review completed.",
                            {
                                "node": node_name,
                                "decision": decision,
                                "thread_id": thread_id
                            }
                        )

                    # RECOMMENDATION

                    elif node_name == "generate_recommendation_node":

                        yield make_event(
                            "node",
                            "🤖 Generating personalized recommendations...",
                            {
                                "node": node_name
                            }
                        )

                        final_advice = None

                        if isinstance(update, dict):
                            final_advice = update.get(
                                "final_advice"
                            )

                        if final_advice:

                            if hasattr(
                                final_advice,
                                "model_dump"
                            ):
                                final_advice = (
                                    final_advice.model_dump()
                                )

                            # NOTE: `update` here is only what THIS node
                            # returned, not the fully-reduced graph state,
                            # so it doesn't include token usage from
                            # earlier nodes (parser/critic). We
                            # deliberately don't attach `usage` to this
                            # intermediate event — the accurate,
                            # cumulative total is read from the reduced
                            # state after the stream finishes below.
                            yield make_event(
                                "final",
                                "🎉 Recommendations are ready!",
                                {
                                    "thread_id": thread_id,
                                    "response": final_advice
                                }
                            )

            
            # CHECK INTERRUPT / FINAL STATE
            

            current_state = graph_app.get_state(config)

            # Human review interrupt
            if "human_review_node" in current_state.next:

                yield make_event(
                    "human_review",
                    "⏸️ Waiting for human advisor approval.",
                    {
                        "thread_id": thread_id,
                        "violations": current_state.values.get(
                            "violations",
                            []
                        )
                    }
                )

                return

            # Final response
            final_advice = current_state.values.get(
                "final_advice"
            )

            if final_advice:

                if hasattr(
                    final_advice,
                    "model_dump"
                ):
                    final_advice = final_advice.model_dump()

                yield make_event(
                    "final",
                    "🎉 Final recommendation generated.",
                    {
                        "thread_id": thread_id,
                        "response": final_advice,
                        "usage": build_usage_payload(
                            current_state.values
                        ),
                    }
                )

            else:

                yield make_event(
                    "error",
                    "❌ The advisor finished without producing a final response.",
                    {
                        "thread_id": thread_id
                    }
                )

        except Exception as e:

            import traceback
            traceback.print_exc()

            yield make_event(
                "error",
                f"❌ Advisor error: {str(e)}",
                {
                    "thread_id": thread_id
                }
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )



# NORMAL ADVISOR ENDPOINT
@router.post(
    "/advise",
    response_model=AdviceResponse
)
@limiter.limit("10/minute")
async def advise(
    request: Request,
    body: AdviceRequest
):

    thread_id = str(uuid.uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    initial_state = {
        "user_query": body.query,
        "messages": [],
        "parsed_filters": None,
        "retrieved_courses": [],
        "violations": [],
        "requires_human_review": False,
        "human_decision": None,
        "parsing_failed": False,
        "integrity_flags": [],
        "final_advice": None,
        "total_input_tokens": 0,
        "total_output_tokens": 0,
    }

    try:

        graph_app.invoke(
            initial_state,
            config=config
        )

        current_state = graph_app.get_state(config)

        if "human_review_node" in current_state.next:

            return AdviceResponse(
                recommendations=[],
                violations=current_state.values.get(
                    "violations",
                    []
                ),
                requires_human_review=True,
                message=(
                    "PAUSED: Critic blocked this request. "
                    "Waiting for advisor approval. "
                    f"Thread ID: {thread_id}"
                ),
            )

        final_advice = current_state.values.get(
            "final_advice"
        )

        if final_advice:
            return final_advice

        raise HTTPException(
            status_code=500,
            detail="Failed to generate advice."
        )

    except Exception as e:

        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )



# HUMAN REVIEW
@router.post(
    "/human-review",
    response_model=AdviceResponse
)
async def human_review(
    body: HumanReviewRequest
):

    config = {
        "configurable": {
            "thread_id": body.thread_id
        }
    }

    current_state = graph_app.get_state(config)

    if "human_review_node" not in current_state.next:

        raise HTTPException(
            status_code=400,
            detail=(
                "Thread is not paused for human review "
                "or does not exist."
            )
        )

    try:

        graph_app.update_state(
            config,
            {
                "human_decision": body.decision
            }
        )

        graph_app.invoke(
            None,
            config=config
        )

        final_state = graph_app.get_state(
            config
        ).values

        final_advice = final_state.get(
            "final_advice"
        )

        if final_advice:
            return final_advice

        raise HTTPException(
            status_code=500,
            detail=(
                "Failed to generate final advice "
                "after human review."
            )
        )

    except Exception as e:

        import traceback
        traceback.print_exc()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )



# EVALUATION
@router.get("/evaluation/metrics")
async def evaluation_metrics():

    metrics = evaluate_pipeline()

    return metrics