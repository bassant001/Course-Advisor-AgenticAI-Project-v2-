import sys
import os
import json
from pydantic import ValidationError

# To run:
# python -m src.evals.retrieval_eval

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.retrieval.retrieve import load_existing_index, retrieve_courses

from src.agent.query_parser import QueryParser


def load_eval_data(filepath="data/eval/queries.json"):
    if not os.path.exists(filepath):
        raise FileNotFoundError(
            f"Evaluation file not found at {filepath}"
        )

    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def mock_llm_raw_output(query_id):
    """
    Temporary simulation of LLM structured output.
    """

    mocks = {
        1: {"level": 300},

        19: {
            "unavailable_days": ["Mon", "Wed"],
            "unavailable_time": {
                "start": "15:00",
                "end": "16:30"
            }
        },

        21: {"level": 100},

        23: {
            "unavailable_days": ["Tue", "Thu"],
            "unavailable_time": {
                "start": "08:00",
                "end": "11:00"
            }
        },

        25: {"max_credits": 1},

        35: {"min_credits": 999},

        40: {"level": 100}
    }

    return mocks.get(query_id, {})


def evaluate_pipeline():

    print("\n⌛ Loading systems for evaluation...")

    index = load_existing_index()
    eval_data = load_eval_data()
    parser = QueryParser()

    total_precision = 0.0
    total_recall = 0.0
    total_violations = 0

    valid_queries = 0

    print(
        f"\n🚀 Starting Full Evaluation "
        f"on {len(eval_data)} queries...\n"
    )

    for item in eval_data:

        q_id = item["id"]
        nl_query = item["nl_query"]

        expected_to_recommend = set(
            item.get("should_recommend", [])
        )

        expected_not_to_recommend = set(
            item.get("should_not_recommend", [])
        )

        # --------------------------------------------------
        # Simulate LLM extraction
        # --------------------------------------------------

        raw_llm_data = mock_llm_raw_output(q_id)

        parsed_schema = None

        if raw_llm_data:

            try:
                parsed_schema = parser.parse(
                    raw_llm_data
                )

            except ValidationError as e:

                print(
                    f"❌ Parser Error for Q{q_id}: {e}"
                )

                continue

        # --------------------------------------------------
        # Retrieval
        # --------------------------------------------------

        retrieved_nodes = retrieve_courses(
            index=index,
            query_str=nl_query,
            query_filters=parsed_schema,
            top_k=3,
        )

        retrieved_courses = set(
            node.node.metadata.get("course_code")
            for node in retrieved_nodes
            if node.node.metadata.get("course_code")
        )

        # --------------------------------------------------
        # Metrics
        # --------------------------------------------------

        true_positives = len(
            expected_to_recommend
            & retrieved_courses
        )

        false_positives = len(
            retrieved_courses
            - expected_to_recommend
        )

        false_negatives = len(
            expected_to_recommend
            - retrieved_courses
        )

        precision = (
            true_positives /
            (true_positives + false_positives)
            if (true_positives + false_positives) > 0
            else 0.0
        )

        recall = (
            true_positives /
            (true_positives + false_negatives)
            if (true_positives + false_negatives) > 0
            else 0.0
        )

        violations = len(
            expected_not_to_recommend
            & retrieved_courses
        )

        # --------------------------------------------------
        # Accumulate
        # --------------------------------------------------

        total_precision += precision
        total_recall += recall
        total_violations += violations

        valid_queries += 1

        print(
            f"✅ Q{q_id} | "
            f"Retrieved: {list(retrieved_courses)} | "
            f"Precision: {precision:.2f} | "
            f"Recall: {recall:.2f} | "
            f"Violations: {violations}"
        )

    # ======================================================
    # FINAL METRICS
    # ======================================================

    if valid_queries > 0:

        avg_precision = (
            total_precision / valid_queries
        )

        avg_recall = (
            total_recall / valid_queries
        )

    else:

        avg_precision = 0.0
        avg_recall = 0.0

    print("\n" + "=" * 55)
    print("📊 FINAL EVALUATION REPORT")
    print("=" * 55)

    print(
        f"Total Queries Evaluated : "
        f"{valid_queries} / {len(eval_data)}"
    )

    print(
        f"Average Precision       : "
        f"{avg_precision:.2f}"
    )

    print(
        f"Average Recall          :ِ "
        f"{avg_recall:.2f}"
    )

    print(
        f"Total Violations        : "
        f"{total_violations}"
    )

    print("=" * 55 + "\n")

    # ======================================================
    # RETURN METRICS TO FASTAPI
    # ======================================================

    return {
        "total_queries": valid_queries,
        "total_available_queries": len(eval_data),
        "precision": round(avg_precision, 4),
        "recall": round(avg_recall, 4),
        "hard_constraint_violations": total_violations,
    }


if __name__ == "__main__":
    evaluate_pipeline()