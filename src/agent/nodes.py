import os
import sys
import json
import dotenv
import cohere
from typing import Any, Dict, List, Tuple
from pydantic import ValidationError

from src.agent.state import AgentState
from src.agent.prompts import (
    CRITIC_SYSTEM_PROMPT,
    RECOMMENDER_SYSTEM_PROMPT,
    PARSER_SYSTEM_PROMPT
)
from src.schemas import QueryFilterSchema, AdviceResponse
from src.schemas.query import MAX_CREDITS_PER_SEMESTER, COURSE_CODE_PATTERN
from src.agent.repair_loop import QueryRepairLoop
from src.retrieval.retrieve import retrieve_courses, load_existing_index



# PROJECT PATH


current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))

if project_root not in sys.path:
    sys.path.insert(0, project_root)



# LAZY LOADING


_vector_index = None
_co_client = None



# COHERE CLIENT


def get_cohere_client():
    global _co_client

    if _co_client is None:
        dotenv.load_dotenv()

        key = os.getenv("COHERE_API_KEY")

        if not key:
            raise ValueError(
                "⚠️ COHERE_API_KEY is missing! Check your .env file."
            )

        print("🔑 [Cohere] API key loaded successfully.")

        _co_client = cohere.Client(key)

    return _co_client



# VECTOR INDEX


def get_vector_index():
    global _vector_index

    if _vector_index is None:
        print("📦 [Retrieval] Loading existing vector index...")

        _vector_index = load_existing_index()

        print("✅ [Retrieval] Vector index loaded successfully.")
        print(f"📦 [Retrieval] Index type: {type(_vector_index).__name__}")

    return _vector_index



# TOKEN USAGE TRACKING


class TokenTracker:
    """
    Accumulates Cohere token usage across however many LLM calls happen
    inside a single node (a node can call the LLM more than once, e.g.
    the parser/recommender repair loops retry on validation failure —
    every retry is a real, billed API call, so it should count).

    Each node calls `reset()` once at the start, lets `call_llm_text` /
    `call_llm_json` add to the tracker as they run, then reads `totals()`
    right before returning its state update.
    """

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0

    def reset(self):
        self.input_tokens = 0
        self.output_tokens = 0

    def add(self, input_tokens: int = 0, output_tokens: int = 0):
        self.input_tokens += input_tokens or 0
        self.output_tokens += output_tokens or 0

    def totals(self) -> Tuple[int, int]:
        return self.input_tokens, self.output_tokens


# Single global tracker. Nodes run sequentially (not concurrently) inside
# one graph invocation, so a module-level instance reset at the top of
# each node is safe and avoids threading every LLM helper's signature
# through the whole call stack (repair loop, retry loops, etc.).
_token_tracker = TokenTracker()


def _extract_usage(response) -> Tuple[int, int]:
    """
    Best-effort extraction of billed token usage from a Cohere `chat()`
    response. Cohere's SDK has moved this field around between versions
    (`meta.billed_units` vs `meta.tokens`), so we probe both and fall
    back to (0, 0) instead of raising if neither is present — a missing
    usage field should never break a recommendation.
    """

    input_tokens = 0
    output_tokens = 0

    meta = getattr(response, "meta", None)

    if meta is not None:

        billed = getattr(meta, "billed_units", None)

        if billed is not None:
            input_tokens = getattr(billed, "input_tokens", 0) or 0
            output_tokens = getattr(billed, "output_tokens", 0) or 0

        else:
            tokens = getattr(meta, "tokens", None)

            if tokens is not None:
                input_tokens = getattr(tokens, "input_tokens", 0) or 0
                output_tokens = getattr(tokens, "output_tokens", 0) or 0

    return input_tokens, output_tokens



# LLM TEXT


def call_llm_text(prompt: str) -> str:
    try:
        response = get_cohere_client().chat(
            model="command-r-plus-08-2024",
            message=prompt,
        )

        input_tok, output_tok = _extract_usage(response)
        _token_tracker.add(input_tok, output_tok)

        return response.text

    except Exception as e:
        print(f"❌ Cohere API Text Error: {type(e).__name__}: {e}")
        return ""



# LLM JSON


def call_llm_json(prompt: str) -> Dict[str, Any]:
    try:
        response = get_cohere_client().chat(
            model="command-r-plus-08-2024",
            message=prompt,
            response_format={"type": "json_object"}
        )

        input_tok, output_tok = _extract_usage(response)
        _token_tracker.add(input_tok, output_tok)

        print("✅ [Cohere] JSON response received.")

        return json.loads(response.text)

    except Exception as e:
        print(f"❌ Cohere API JSON Error: {type(e).__name__}: {e}")
        raise



# QUERY PARSER NODE


def parse_query_node(state: AgentState):

    print("\n" + "=" * 70)
    print("🤖 [Node] Parsing User Query...")
    print("=" * 70)

    _token_tracker.reset()

    user_query = state["user_query"]

    print(f"📝 User Query: {user_query}")

    parser_loop = QueryRepairLoop(
        llm_function=call_llm_json,
        max_retries=2
    )

    initial_prompt = f"""
    {PARSER_SYSTEM_PROMPT}

    Return ONLY a JSON object matching this schema:

    {json.dumps(QueryFilterSchema.model_json_schema(), indent=2)}

    Student request:
    {user_query}
    """

    try:

        parsed_schema = parser_loop.parse(initial_prompt)

        print("✅ [Node] Query parsed successfully.")
        print(f"📋 [Node] Parsed filters: {parsed_schema}")

        input_tok, output_tok = _token_tracker.totals()

        return {
            "parsed_filters": parsed_schema,
            "parsing_failed": False,
            "total_input_tokens": input_tok,
            "total_output_tokens": output_tok,
        }

    except Exception as e:

        print(
            f"❌ [Node] Parsing failed: "
            f"{type(e).__name__}: {e}"
        )

       
        raise



# RETRIEVAL NODE


def retrieve_courses_node(state: AgentState):

    print("\n" + "=" * 70)
    print("🔍 [Node] Retrieving Courses from Vector DB...")
    print("=" * 70)

    parsed_filters = state.get("parsed_filters")

    # SAFETY CHECK

    if state.get("parsing_failed") or parsed_filters is None:

        print(
            "⚠️ [Node] No valid filters parsed."
        )

        print(
            "⚠️ [Node] Skipping retrieval."
        )

        return {
            "retrieved_courses": []
        }

    user_query = state["user_query"]

    print(f"🔎 Query: {user_query}")
    print(f"📋 Filters: {parsed_filters}")

    # LOAD INDEX

    try:

        index = get_vector_index()

        print(
            f"✅ [Retrieval] Index ready: "
            f"{type(index).__name__}"
        )

    except Exception as e:

        print(
            f"❌ [Retrieval] Failed to load index: "
            f"{type(e).__name__}: {e}"
        )

        raise

    # RETRIEVE

    try:

        retrieved_nodes = retrieve_courses(
            index=index,
            query_str=user_query,
            query_filters=parsed_filters,
            top_k=3
        )

    except Exception as e:

        print(
            f"❌ [Retrieval] retrieve_courses() failed: "
            f"{type(e).__name__}: {e}"
        )

        raise

    # DEBUG RETRIEVAL RESULT

    if retrieved_nodes is None:

        print(
            "❌ [Retrieval] retrieve_courses() returned None."
        )

        return {
            "retrieved_courses": []
        }

    print(
        f"📦 [Retrieval] Retrieved nodes: "
        f"{len(retrieved_nodes)}"
    )

    if retrieved_nodes:

        print("🔎 [Retrieval] First retrieved node:")

        try:
            print(retrieved_nodes[0])
        except Exception as e:
            print(
                f"⚠️ Could not print first node: {e}"
            )

    # EXTRACT METADATA

    courses_data = [
        node.node.metadata
        for node in retrieved_nodes
        if node.node.metadata
    ]

    print(
        f"📚 [Retrieval] Courses metadata count: "
        f"{len(courses_data)}"
    )

    print(
        f"📚 [Retrieval] Courses metadata: "
        f"{courses_data}"
    )

   
    if not courses_data:

        print(
            "❌ [Retrieval] ZERO COURSES RETURNED."
        )

        print(
            "⚠️ [Retrieval] The problem is BEFORE "
            "the critic/recommender nodes."
        )

    else:

        print(
            f"✅ [Retrieval] Successfully retrieved "
            f"{len(courses_data)} courses."
        )

        for i, course in enumerate(courses_data, start=1):


            print(
                f"   {i}. "
                f"{course.get('course_code', 'UNKNOWN')} "
                f"- "
                f"{course.get('title', 'NO TITLE')}"
            )

    return {
        "retrieved_courses": courses_data
    }





SAFE_METADATA_KEYS = (
    "course_code",
    "course_title",
    "level",
    "credits",
    "department",
    "course_type",
    "schedule_days",
    "schedule_start",
    "schedule_end"
)


def _normalize_prerequisites(course: Dict[str, Any]) -> List[str]:
    """
    FIX: the raw catalog metadata stores "prerequisites" as a JSON
    list (e.g. ["CS201", "MATH103"] or []), never as a comma-joined
    string. The old code assumed a string and called .split(",") on
    it, which crashes with AttributeError the moment a course with
    any prerequisites (or even an empty list) was evaluated, because
    `[] != "None"` is always True for a list.

    This normalizes either shape defensively: a real list is used
    as-is, a legacy comma-separated string is split, and anything
    else (missing/None) becomes an empty list. Only tokens matching
    the course code pattern are kept, so injected junk in the data
    (e.g. "OVERRIDE_ALL_RULES") is filtered out rather than treated
    as a real prerequisite.
    """

    raw = course.get("prerequisites")

    if raw is None:
        candidates: List[str] = []
    elif isinstance(raw, str):
        candidates = raw.split(",") if raw != "None" else []
    elif isinstance(raw, (list, tuple)):
        candidates = list(raw)
    else:
        candidates = []

    return [
        p.strip()
        for p in candidates
        if isinstance(p, str) and COURSE_CODE_PATTERN.match(p.strip())
    ]


def _sanitize_course_for_llm(
    course: Dict[str, Any]
) -> Dict[str, Any]:

    # course title.
    schedule = course.get("schedule", {}) or {}

    safe = {
        "course_code": course.get("course_code"),
        "course_title": course.get("title"),
        "level": course.get("level"),
        "credits": course.get("credits"),
        "department": course.get("department"),
        "course_type": course.get("course_type"),
        "schedule_days": schedule.get("days"),
        "schedule_start": schedule.get("start_time"),
        "schedule_end": schedule.get("end_time"),
    }

    safe["prerequisites"] = _normalize_prerequisites(course)

    return safe






def constraint_critic_node(state: AgentState):

    print("\n" + "=" * 70)
    print("🧐 [Node] Critic evaluating constraints...")
    print("=" * 70)

    _token_tracker.reset()

    retrieved_courses = state.get(
        "retrieved_courses",
        []
    )

    parsed_filters = state.get(
        "parsed_filters"
    )

    print(
        f"📚 Courses received by critic: "
        f"{len(retrieved_courses)}"
    )


    if not retrieved_courses:

        print(
            "⚠️ [Node] No courses were retrieved."
        )

        return {
            "violations": [],
            "requires_human_review": False,
            "integrity_flags": [
                "No courses were retrieved."
            ]
        }



    completed_courses = (
        parsed_filters.completed_courses
        if parsed_filters
        else []
    )

    current_credits = (
        parsed_filters.current_credits
        if parsed_filters
        and parsed_filters.current_credits
        else 0
    )

    print(
        f"🎓 Completed courses: "
        f"{completed_courses}"
    )

    print(
        f"📊 Current credits: "
        f"{current_credits}"
    )

    violations = []

    integrity_flags = state.get(
        "integrity_flags",
        []
    )



    for course in retrieved_courses:

        c_code = course.get(
            "course_code",
            "Unknown"
        )


        valid_prereqs = _normalize_prerequisites(course)

        missing = [
            p
            for p in valid_prereqs
            if p not in completed_courses
        ]

        if missing:

            violations.append(
                f"{c_code} has unmet prerequisites: "
                f"{', '.join(missing)}"
            )



        c_credits = course.get(
            "credits",
            0
        )

        if (
            current_credits + c_credits
            > MAX_CREDITS_PER_SEMESTER
        ):

            violations.append(
                f"Taking {c_code} "
                f"({c_credits} credits) exceeds the "
                f"{MAX_CREDITS_PER_SEMESTER}-credit limit."
            )

    # SANITIZE DATA FOR LLM

    safe_course_data = [
        _sanitize_course_for_llm(c)
        for c in retrieved_courses
    ]

    evaluation_prompt = f"""
    {CRITIC_SYSTEM_PROMPT}

    Student Completed Courses:
    {completed_courses}

    Retrieved Courses to Evaluate:
    {json.dumps(safe_course_data, indent=2)}

    Respond ONLY with a JSON object containing
    a single key "violations" which is an array of strings.

    If there are no violations, return:
    {{"violations": []}}
    """



    try:

        violations_response = call_llm_json(
            evaluation_prompt
        )

        llm_violations = violations_response.get("violations", [])

        print(f"🤖 [Critic] LLM observations: {llm_violations}")
        print(f"🔒 [Critic] Hard violations: {violations}")

    except Exception as e:

        print(
            f"⚠️ [Node] Critic LLM Error: "
            f"{type(e).__name__}: {e}"
        )

        violations.append(
            "System security evaluation failure. "
            "Human review strictly mandated."
        )



    violations = list(
        set(violations)
    )

    requires_human_review = (
        len(violations) > 0
    )

    print(
        f"✅ [Node] Critic found "
        f"{len(violations)} violations."
    )

    print(
        f"👤 Human review required: "
        f"{requires_human_review}"
    )

    input_tok, output_tok = _token_tracker.totals()

    return {
        "violations": violations,
        "requires_human_review": (
            requires_human_review
        ),
        "integrity_flags": integrity_flags,
        "total_input_tokens": input_tok,
        "total_output_tokens": output_tok,
    }






def generate_recommendation_node(
    state: AgentState
):

    print("\n" + "=" * 70)
    print("💬 [Node] Generating Final Recommendation...")
    print("=" * 70)

    _token_tracker.reset()

    retrieved_courses = state.get(
        "retrieved_courses",
        []
    )

    print(
        f"📚 Courses available to recommender: "
        f"{len(retrieved_courses)}"
    )

    
    if not retrieved_courses:

        print(
            "❌ [Recommender] No courses available."
        )

        final_advice = AdviceResponse(
            recommendations=[],
            violations=state.get(
                "violations",
                []
            ),
            requires_human_review=False,
            message=(
                "No matching courses were retrieved "
                "for this request."
            )
        )

        input_tok, output_tok = _token_tracker.totals()

        return {
            "final_advice": final_advice,
            "total_input_tokens": input_tok,
            "total_output_tokens": output_tok,
        }

    safe_retrieved_courses = [
        _sanitize_course_for_llm(c)
        for c in retrieved_courses
    ]

    base_prompt = f"""
    {RECOMMENDER_SYSTEM_PROMPT}

    User Query:
    {state['user_query']}

    Retrieved Courses:
    {json.dumps(
        safe_retrieved_courses,
        indent=2
    )}

    Violations Found:
    {state['violations']}

    IMPORTANT:
    You MUST return a valid JSON object that
    strictly matches the following JSON schema.

    Use the exact key names specified in the schema:

    {json.dumps(
        AdviceResponse.model_json_schema(),
        indent=2
    )}
    """

    final_advice = None
    error_feedback = ""


    for attempt in range(3):

        print(
            f"🔄 [Recommender] Attempt "
            f"{attempt + 1}/3"
        )

        current_prompt = (
            base_prompt
            + f"\n\n{error_feedback}"
            if error_feedback
            else base_prompt
        )

        try:

            response_data = call_llm_json(
                current_prompt
            )

            print(
                f"📦 [Recommender] Raw response: "
                f"{response_data}"
            )

            final_advice = (
                AdviceResponse.model_validate(
                    response_data
                )
            )

            print(
                "✅ [Node] Recommendation "
                "generated successfully."
            )

            break

        except ValidationError as e:

            print(
                f"⚠️ [Node] Recommender "
                f"Validation Error "
                f"(Attempt {attempt + 1})"
            )

            print(e)

            error_feedback = (
                "YOUR PREVIOUS RESPONSE FAILED "
                "PYDANTIC VALIDATION. "
                "Fix these errors:\n"
                f"{e.errors()}"
            )

        except Exception as e:

            print(
                f"⚠️ [Node] Recommender General "
                f"Error (Attempt {attempt + 1}): "
                f"{type(e).__name__}: {e}"
            )

            error_feedback = (
                "INVALID JSON FORMAT: "
                f"{str(e)}"
            )


    if final_advice is None:

        print(
            "❌ [Recommender] All attempts failed."
        )

        final_advice = AdviceResponse(
            recommendations=[],
            violations=state.get(
                "violations",
                []
            ),
            requires_human_review=True,
            message=(
                "An internal error occurred while "
                "generating recommendations. "
                "Please consult your human advisor."
            )
        )

    input_tok, output_tok = _token_tracker.totals()

    return {
        "final_advice": final_advice,
        "total_input_tokens": input_tok,
        "total_output_tokens": output_tok,
    }