import uuid
from fastapi import APIRouter, Request, HTTPException
from slowapi.util import get_remote_address
from slowapi import Limiter

from src.schemas.api import AdviceRequest, HumanReviewRequest
from src.schemas.recommendation import AdviceResponse, AdviceMetrics
from src.agent.graph import build_course_advisor_graph
from src.evals.retrieval_eval import evaluate_pipeline

router = APIRouter()

# ben7aded requests beta3et kol client
limiter = Limiter(key_func=get_remote_address)

# Build the graph once globally for the API to use
graph_app = build_course_advisor_graph()


@router.post("/advise", response_model=AdviceResponse)
@limiter.limit("10/minute")
async def advise(request: Request, body: AdviceRequest):
    # 1. Generate a unique session ID for this request
    thread_id = str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}

    # 2. Prepare the initial state
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
        "final_advice": None
    }

    try:
        # 3. Run the LangGraph agent
        graph_app.invoke(initial_state, config=config)
        
        # 4. Check if it paused for Human-in-the-Loop
        current_state = graph_app.get_state(config)
        if "human_review_node" in current_state.next:
            return AdviceResponse(
                recommendations=[],
                violations=current_state.values.get("violations", []),
                requires_human_review=True,
                message=f"PAUSED: Critic blocked this request. Waiting for advisor approval. Thread ID: {thread_id}",
                metrics=AdviceMetrics(
                    latency_ms=0, input_tokens=0, output_tokens=0, estimated_cost=0, retries=0, agent_steps=0
                )
            )

        # 5. If it finished successfully without pausing
        final_advice = current_state.values.get("final_advice")
        if final_advice:
            return final_advice
            
        raise HTTPException(status_code=500, detail="Failed to generate advice.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/human-review", response_model=AdviceResponse)
async def human_review(body: HumanReviewRequest):
    config = {"configurable": {"thread_id": body.thread_id}}

    # 1. Check if the thread actually exists and is waiting for review
    current_state = graph_app.get_state(config)
    if "human_review_node" not in current_state.next:
        raise HTTPException(status_code=400, detail="Thread is not paused for human review or does not exist.")

    try:
        # 2. Inject the human's decision into the state
        graph_app.update_state(config, {"human_decision": body.decision})

        # 3. Resume the graph execution
        graph_app.invoke(None, config=config)

        # 4. Fetch the final result after the graph completes
        final_state = graph_app.get_state(config).values
        final_advice = final_state.get("final_advice")
        
        if final_advice:
            return final_advice
            
        raise HTTPException(status_code=500, detail="Failed to generate final advice after human review.")

    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/evaluation/metrics")
async def evaluation_metrics():
    metrics = evaluate_pipeline()
    return metrics