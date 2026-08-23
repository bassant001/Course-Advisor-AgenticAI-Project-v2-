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

from src.retrieval.retrieve import load_existing_index, retrieve_courses
from src.agent.nodes import call_llm_json
from src.agent.repair_loop import QueryRepairLoop
from src.agent.prompts import PARSER_SYSTEM_PROMPT
from src.schemas import QueryFilterSchema

# Project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
QUERIES_PATH = PROJECT_ROOT / "data" / "eval" / "queries.json"
OBSERVABILITY_DIR = PROJECT_ROOT / "src" / "observability"
REPORT_PATH = OBSERVABILITY_DIR / "retrieval_test_results.md"
CACHE_PATH = OBSERVABILITY_DIR / "parsed_queries_cache.json"




# report helpers
def add_report(report, text=""):
    report.append(text)

def group_evaluation_reasons(results):
    grouped = defaultdict(list)
    for result in results:
        grouped[result["reason"]].append(result["id"])
    return grouped




# caching & parsing logic
def load_evaluation_queries():
    with open(QUERIES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)

def generate_or_load_cache(queries):
    """
    Loads parsed filters from cache if available.
    Otherwise, runs the LLM parser on all queries and caches the results.
    """
    if CACHE_PATH.exists():
        print(f"📦 Loading cached parsed filters from {CACHE_PATH}...")
        with open(CACHE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
            
    print("⏳ Cache not found! Running LLM Parser to generate filters (This will take a few minutes)...")
    parser_loop = QueryRepairLoop(llm_function=call_llm_json, max_retries=2)
    cached_filters = {}
    
    for i, query in enumerate(queries, start=1):
        query_id = str(query["id"])
        nl_query = query["nl_query"]
        print(f"   -> Parsing Query {i}/{len(queries)} (ID: {query_id})...")
        
        prompt = f"{PARSER_SYSTEM_PROMPT}\n\nReturn ONLY a JSON object matching this schema:\n{json.dumps(QueryFilterSchema.model_json_schema())}\n\nStudent request:\n{nl_query}"
        
        try:
            parsed_schema = parser_loop.parse(prompt)
            cached_filters[query_id] = parsed_schema.model_dump(exclude_none=True)
        except Exception as e:
            print(f"   ❌ Failed to parse Query {query_id}: {e}")
            cached_filters[query_id] = None
            
        time.sleep(3) # Anti Rate-Limit Delay
        
    OBSERVABILITY_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cached_filters, f, indent=4)
        
    print("✅ Cache generated and saved successfully!")
    return cached_filters



# evaluation logic
def evaluate_retrieval(index, query, cached_filter):
    query_id = query["id"]
    expected = set(query.get("should_recommend", []))
    should_not_recommend = set(query.get("should_not_recommend", []))
    nl_query = query["nl_query"]

    # Retrieve with Metadata & Schedule Filters
    try:
        results = retrieve_courses(index=index, query_str=nl_query, query_filters=cached_filter, top_k=5)
        retrieved_courses = [r.node.metadata.get("course_code") for r in results if r.node.metadata.get("course_code")]
    except Exception as e:
        print(f"   ❌ Retrieval failed for Query {query_id}: {e}")
        retrieved_courses = []

    retrieved_set = set(retrieved_courses)

    # Metrics Math (TP, FP, FN)
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
        reason = "Filtered retrieval successfully returned all expected recommendations and avoided prohibited courses."
    else:
        reasons = []
        if missing_expected:
            reasons.append("expected course(s) were not retrieved: " + ", ".join(sorted(missing_expected)))
        if incorrectly_retrieved:
            reasons.append("prohibited course(s) were retrieved despite filters: " + ", ".join(sorted(incorrectly_retrieved)))
        reason = "Filtered retrieval failed because " + " and ".join(reasons) + "."

    return {
        "id": query_id,
        "passed": passed,
        "reason": reason,
        "retrieved": retrieved_courses,
        "missing_expected": sorted(missing_expected),
        "incorrectly_retrieved": sorted(incorrectly_retrieved),
        "precision": precision,
        "recall": recall,
        "f1": f1
    }



# main evaluation
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 RUNNING FILTERED RETRIEVAL EVALUATION")
    print("=" * 60)
    
    OBSERVABILITY_DIR.mkdir(parents=True, exist_ok=True)
    report = []
    
    # 1. Setup
    queries = load_evaluation_queries()
    cached_filters = generate_or_load_cache(queries)
    index = load_existing_index()
    
    # 2. Evaluate
    evaluation_results = []
    print("\n⏳ Evaluating filtered retrieval on all queries...")
    for query in queries:
        query_id = str(query["id"])
        q_filter = cached_filters.get(query_id)
        result = evaluate_retrieval(index, query, q_filter)
        evaluation_results.append(result)
        
    # 3. Statistics
    total_queries = len(evaluation_results)
    passed_queries = sum(1 for result in evaluation_results if result["passed"])
    failed_queries = total_queries - passed_queries
    pass_rate = (passed_queries / total_queries) * 100 if total_queries else 0

    avg_precision = (sum(r["precision"] for r in evaluation_results) / total_queries) * 100
    avg_recall = (sum(r["recall"] for r in evaluation_results) / total_queries) * 100
    avg_f1 = (sum(r["f1"] for r in evaluation_results) / total_queries) * 100

    # 4. Generate Markdown Report
    add_report(report, "# Filtered Retrieval Evaluation Report (Layer 2)")
    add_report(report, "")
    add_report(report, "This evaluation tests the **Retrieval Layer** combined with **Metadata & Schedule Filters**. By applying parsed constraints (like credit limits, schedules, and levels), we expect a significant jump in Precision compared to the base Ingestion evaluation.")
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
    add_report(report, f"- **Average Precision:** {avg_precision:.2f}%")
    add_report(report, f"- **Average Recall:** {avg_recall:.2f}%")
    add_report(report, f"- **Average F1-Score:** {avg_f1:.2f}%")
    add_report(report, "")
    
    add_report(report, "### High-Level Failure Summary")
    add_report(report, "")
    failed_results = [result for result in evaluation_results if not result["passed"]]
    missing_only = sum(1 for r in failed_results if r["missing_expected"] and not r["incorrectly_retrieved"])
    prohibited_only = sum(1 for r in failed_results if not r["missing_expected"] and r["incorrectly_retrieved"])
    both_errors = sum(1 for r in failed_results if r["missing_expected"] and r["incorrectly_retrieved"])
    
    add_report(report, "The failures at this layer show the limits of metadata filtering alone:")
    add_report(report, "")
    add_report(report, f"- **Retrieved Prohibited Courses (False Positives): {prohibited_only} queries.** Metadata filters cannot catch unmet prerequisites (since they require comparing student history with course strings). This proves the need for the Final Agent (Critic).")
    add_report(report, f"- **Missed Expected Courses (False Negatives): {missing_only} queries.** The required courses were not retrieved within the top-K results.")
    add_report(report, f"- **Mixed Errors (Both): {both_errors} queries.** Failed due to both missing the expected recommendations and returning prohibited ones.")
    add_report(report, "")

    add_report(report, "### Detailed Failure Logs")
    add_report(report, "")
    failed_groups = group_evaluation_reasons(failed_results)

    if failed_groups:
        for reason, query_ids in failed_groups.items():
            add_report(report, f"- **{len(query_ids)} queries** failed because {reason}")
            add_report(report, f"  - Query IDs: {', '.join(map(str, query_ids))}")
    else:
        add_report(report, "No evaluation queries failed.")
    add_report(report, "")

    add_report(report, "## Final Summary")
    add_report(report, "")
    add_report(report, "The retrieval pipeline successfully applied the LLM-parsed metadata filters to the vector search. While Precision improved over pure semantic search, some violations (like prerequisites) still bypass the filters, requiring Agentic validation.")
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
    print(f"Pass Rate: {pass_rate:.2f}% | Precision: {avg_precision:.2f}% | Recall: {avg_recall:.2f}%")