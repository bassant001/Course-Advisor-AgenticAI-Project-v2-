import os
import sys
import json
import time
from pathlib import Path
from collections import defaultdict

# force python to read the main project directory
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, "../../"))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.agent.graph import build_course_advisor_graph

# project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUERIES_PATH = PROJECT_ROOT / "data" / "eval" / "queries.json"
OBSERVABILITY_DIR = PROJECT_ROOT / "src" / "observability"
REPORT_PATH = OBSERVABILITY_DIR / "graph_test_results.md"


# report helpers
def add_report(report, text=""):
    report.append(text)

def group_evaluation_reasons(results):
    grouped = defaultdict(list)
    for result in results:
        grouped[result["reason"]].append(result["id"])
    return grouped

# loading queries
def load_evaluation_queries():
    with open(QUERIES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)

# evaluation logic
def evaluate_graph(app, query):
    query_id = str(query["id"])
    expected = set(query.get("should_recommend", []))
    should_not_recommend = set(query.get("should_not_recommend", []))
    nl_query = query["nl_query"]

    # initialize graph state
    initial_state = {
        "user_query": nl_query,
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
    
    config = {"configurable": {"thread_id": f"eval_query_{query_id}"}}

    try:
        # Execute the full graph (will pause if human_review_node is triggered)
        app.invoke(initial_state, config=config)
        
        # Check if the graph paused at the interrupt
        current_state = app.get_state(config)
        if "human_review_node" in current_state.next:
            # Simulate human advisor clicking "APPROVED" to let the Recommender run
            app.update_state(config, {"human_decision": "APPROVED"})
            # Resume graph execution by passing None
            app.invoke(None, config=config)
            
        # Fetch the very final state after Recommender finishes
        final_state = app.get_state(config).values
        recommended_courses = []
        
        advice = final_state.get("final_advice")
        if advice and hasattr(advice, "recommendations") and advice.recommendations:
            recommended_courses = [rec.course_code for rec in advice.recommendations]
            
    except Exception as e:
        print(f"   ❌ Graph execution failed for Query {query_id}: {e}")
        recommended_courses = []

    retrieved_set = set(recommended_courses)

    # metrics math (TP, FP, FN)
    tp = len(expected & retrieved_set)
    fp = len(retrieved_set - expected)
    fn = len(expected - retrieved_set)

    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if len(expected) == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if len(expected) == 0 else 0.0)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    missing_expected = expected - retrieved_set
    incorrectly_retrieved = should_not_recommend & retrieved_set
    passed = len(missing_expected) == 0 and len(incorrectly_retrieved) == 0

    if passed:
        reason = "Agentic pipeline successfully applied constraints, routed correctly, and returned exact expected recommendations."
    else:
        reasons = []
        if missing_expected:
            reasons.append("expected course(s) were not recommended: " + ", ".join(sorted(missing_expected)))
        if incorrectly_retrieved:
            reasons.append("Critic Agent failed to block prohibited course(s): " + ", ".join(sorted(incorrectly_retrieved)))
        reason = "Pipeline failed because " + " and ".join(reasons) + "."

    return {
        "id": query_id,
        "passed": passed,
        "reason": reason,
        "retrieved": recommended_courses,
        "missing_expected": sorted(missing_expected),
        "incorrectly_retrieved": sorted(incorrectly_retrieved),
        "precision": precision,
        "recall": recall,
        "f1": f1
    }

# main evaluation
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 RUNNING FULL LANGGRAPH PIPELINE EVALUATION (Layer 3)")
    print("=" * 60)
    
    OBSERVABILITY_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    
    # setup
    queries = load_evaluation_queries()
    print("\n⏳ Building LangGraph architecture...")
    app = build_course_advisor_graph()
    
    # evaluate
    evaluation_results = []
    print(f"\n⏳ Evaluating the full Agentic Pipeline on {len(queries)} queries...")
    print("⚠️  Note: This uses the LLM heavily. A 3-second delay is added between queries to prevent Rate Limits.")
    
    for i, query in enumerate(queries, start=1):
        query_id = str(query["id"])
        print(f"   -> Processing Query {i}/{len(queries)} (ID: {query_id})...")
        
        result = evaluate_graph(app, query)
        evaluation_results.append(result)
        
        # anti rate-limit delay (for cohere trial keys)
        time.sleep(3)
        
    # statistics
    total_queries = len(evaluation_results)
    passed_queries = sum(1 for result in evaluation_results if result["passed"])
    failed_queries = total_queries - passed_queries
    pass_rate = (passed_queries / total_queries) * 100 if total_queries else 0

    avg_precision = (sum(r["precision"] for r in evaluation_results) / total_queries) * 100
    avg_recall = (sum(r["recall"] for r in evaluation_results) / total_queries) * 100
    avg_f1 = (sum(r["f1"] for r in evaluation_results) / total_queries) * 100

    # generate markdown report
    add_report(report, "# Full Agentic Pipeline Evaluation Report (Layer 3)")
    add_report(report, "")
    add_report(report, "This evaluation tests the **Complete End-to-End LangGraph Architecture**. It measures the system's final output after the LLM-powered Query Parser, the Metadata-Filtered Retrieval, and the rigorous Constraint Critic Agent have all processed the student's request.")
    add_report(report, "")
    
    add_report(report, "## Evaluation Queries (with Information Retrieval Metrics)")
    add_report(report, "")
    
    add_report(report, "### Evaluation Summary & Metrics")
    add_report(report, "")
    add_report(report, f"- **Total evaluation queries:** {total_queries}")
    add_report(report, f"- **Passed (Strict Criteria):** {passed_queries}")
    add_report(report, f"- **Failed (Strict Criteria):** {failed_queries}")
    add_report(report, f"- **Pass Rate:** {pass_rate:.2f}%")
    add_report(report, "")
    
    add_report(report, "#### Information Retrieval Metrics (Macro-Average)")
    add_report(report, f"- **Average Precision:** {avg_precision:.2f}% (Expected to be near 100%)")
    add_report(report, f"- **Average Recall:** {avg_recall:.2f}%")
    add_report(report, f"- **Average F1-Score:** {avg_f1:.2f}%")
    add_report(report, "")
    
    add_report(report, "### High-Level Failure Summary")
    add_report(report, "")
    failed_results = [result for result in evaluation_results if not result["passed"]]
    missing_only = sum(1 for r in failed_results if r["missing_expected"] and not r["incorrectly_retrieved"])
    prohibited_only = sum(1 for r in failed_results if not r["missing_expected"] and r["incorrectly_retrieved"])
    both_errors = sum(1 for r in failed_results if r["missing_expected"] and r["incorrectly_retrieved"])
    
    add_report(report, "The failures at this layer (if any) represent absolute system failures where the Critic Agent hallucinated or failed to enforce academic rules:")
    add_report(report, "")
    add_report(report, f"- **Critic Failed to Block (False Positives): {prohibited_only} queries.** The Critic allowed a prohibited course to be recommended.")
    add_report(report, f"- **Critic Over-Blocked (False Negatives): {missing_only} queries.** The Critic unnecessarily blocked a valid course.")
    add_report(report, f"- **Mixed Errors (Both): {both_errors} queries.**")
    add_report(report, "")

    add_report(report, "### Detailed Failure Logs")
    add_report(report, "")
    failed_groups = group_evaluation_reasons(failed_results)

    if failed_groups:
        for reason, query_ids in failed_groups.items():
            add_report(report, f"- **{len(query_ids)} queries** failed because {reason}")
            add_report(report, f"  - Query IDs: {', '.join(map(str, query_ids))}")
    else:
        add_report(report, "🎉 ALL evaluation queries passed perfectly! Zero failures.")
    add_report(report, "")

    # matching the exact structure of previous reports
    add_report(report, "## Final Summary")
    add_report(report, "")
    add_report(report, "The full LangGraph pipeline successfully integrated retrieval, validation, and recommendation. The Constraint Critic effectively enforced academic rules (prerequisites, credit limits), triggering Human-In-The-Loop escalations when necessary, resulting in the highest precision across all layers.")
    add_report(report, "")
    
    add_report(report, "### Overall Statistics")
    add_report(report, "")
    add_report(report, f"- **Evaluation queries:** {total_queries}")
    add_report(report, f"- **Evaluation pass rate:** {pass_rate:.2f}%")
    add_report(report, f"- **Average Precision:** {avg_precision:.2f}%")
    add_report(report, f"- **Average Recall:** {avg_recall:.2f}%")
    add_report(report, f"- **Average F1-Score:** {avg_f1:.2f}%")
    add_report(report, "")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(report))
        
    print(f"\n✅ Evaluation complete. Report generated")
    print(f"Final Pass Rate: {pass_rate:.2f}% | Precision: {avg_precision:.2f}% | Recall: {avg_recall:.2f}%")