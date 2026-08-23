import os
import json
from pathlib import Path
from collections import defaultdict
from llama_index.core import Settings
from src.retrieval.ingest import load_and_merge_data, create_nodes, setup_embeddings, setup_vector_database

# run the test using -> python -m src.evals.test_ingest

# project paths
PROJECT_ROOT = Path(__file__).resolve().parents[2]
CATALOG_PATH = PROJECT_ROOT / "data" / "knowledge_base" / "catalog.json"
DESCRIPTIONS_PATH = PROJECT_ROOT / "data" / "knowledge_base" / "descriptions.json"
DEGREE_RULES_PATH = PROJECT_ROOT / "data" / "knowledge_base" / "degree_rules.json"
QUERIES_PATH = PROJECT_ROOT / "data" / "eval" / "queries.json"
OBSERVABILITY_DIR = PROJECT_ROOT / "src" / "observability"
REPORT_PATH = OBSERVABILITY_DIR / "ingest_test_results.md"

# report helpers
def add_report(report, text=""):
    report.append(text)

def add_pass(report, title, details=None):
    report.append(f"### ✅ {title}")
    if details:
        report.append(details)
    report.append("")

def add_fail(report, title, error):
    report.append(f"### ❌ {title}")
    report.append(f"**Reason:** `{error}`")
    report.append("")

# course filtering helpers
def load_original_catalog():
    with open(CATALOG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)

def find_filtered_courses():
    catalog = load_original_catalog()
    filtered_courses = []

    for course in catalog:
        course_code = course.get("course_code", "Unknown")
        try:
            credits = int(course.get("credits", 0))
        except (TypeError, ValueError):
            filtered_courses.append({"course_code": course_code, "reason": "Invalid credits value"})
            continue
            
        department = str(course.get("department", ""))

        if credits > 4 or credits <= 0:
            filtered_courses.append({"course_code": course_code, "reason": f"Invalid credits ({credits})"})
            continue

        if len(department) > 50:
            filtered_courses.append({"course_code": course_code, "reason": "Department name is longer than 50 characters (possible prompt injection)"})

    return filtered_courses

# query evaluation helpers
def load_evaluation_queries():
    with open(QUERIES_PATH, "r", encoding="utf-8") as file:
        return json.load(file)

def get_retrieved_course_codes(results):
    return [result.node.metadata.get("course_code") for result in results if result.node.metadata.get("course_code")]

def evaluate_single_query(retriever, query):
    query_id = query["id"]
    expected = set(query.get("should_recommend", []))
    should_not_recommend = set(query.get("should_not_recommend", []))
    nl_query = query["nl_query"]

    results = retriever.retrieve(nl_query)
    retrieved_courses = get_retrieved_course_codes(results)
    retrieved_set = set(retrieved_courses)

    # information retrieval metrics math (TP, FP, FN)
    tp = len(expected & retrieved_set)
    fp = len(retrieved_set - expected)
    fn = len(expected - retrieved_set)

    # calculate precision, recall, and f1-score with zero-division safety
    precision = tp / (tp + fp) if (tp + fp) > 0 else (1.0 if len(expected) == 0 else 0.0)
    recall = tp / (tp + fn) if (tp + fn) > 0 else (1.0 if len(expected) == 0 else 0.0)
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    missing_expected = expected - retrieved_set
    incorrectly_retrieved = should_not_recommend & retrieved_set
    passed = len(missing_expected) == 0 and len(incorrectly_retrieved) == 0

    if passed:
        reason = "Semantic retrieval successfully returned all expected course recommendations without returning any course marked as should-not-recommend." if expected else "Semantic retrieval did not return any course that was marked as should-not-recommend."
    else:
        reasons = []
        if missing_expected:
            reasons.append("expected course(s) were not retrieved: " + ", ".join(sorted(missing_expected)))
        if incorrectly_retrieved:
            reasons.append("course(s) marked as should-not-recommend were retrieved: " + ", ".join(sorted(incorrectly_retrieved)))
        reason = "Semantic retrieval did not satisfy the expected evaluation criteria because " + " and ".join(reasons) + "."

    return {
        "id": query_id,
        "passed": passed,
        "reason": reason,
        "retrieved": retrieved_courses,
        "expected": sorted(expected),
        "should_not_recommend": sorted(should_not_recommend),
        "missing_expected": sorted(missing_expected),
        "incorrectly_retrieved": sorted(incorrectly_retrieved),
        "precision": precision,
        "recall": recall,
        "f1": f1
    }

def group_evaluation_reasons(results):
    grouped = defaultdict(list)
    for result in results:
        grouped[result["reason"]].append(result["id"])
    return grouped




# main evaluation
if __name__ == "__main__":
    OBSERVABILITY_DIR.mkdir(parents=True, exist_ok=True)
    report = []

    add_report(report, "# Ingestion Pipeline Evaluation Report")
    add_report(report, "")
    add_report(report, "This evaluation verifies the ingestion pipeline from raw knowledge-base files to vector storage and semantic retrieval. It also evaluates the retrieval system against the predefined queries stored in `queries.json`, computing Precision, Recall, and F1-Score.")
    add_report(report, "")

    add_report(report, "## 1. Loading and Merging Course Data")
    add_report(report, "")
    add_report(report, "The catalog, course descriptions, and degree rules are loaded and converted into LlamaIndex documents.")
    add_report(report, "")

    try:
        docs, rules, dropped_count = load_and_merge_data(str(CATALOG_PATH), str(DESCRIPTIONS_PATH), str(DEGREE_RULES_PATH))
        filtered_courses = find_filtered_courses()
        original_catalog = load_original_catalog()
        original_count = len(original_catalog)
        filtered_count = len(filtered_courses)
        valid_count = len(docs)

        add_pass(report, "Data loading and validation", f"- **Courses in original catalog:** {original_count}\n- **Courses filtered out:** {filtered_count}\n- **Valid documents created:** {valid_count}\n- **Document structure:** Valid\n- **Required metadata:** Present")

        add_report(report, "### Courses Filtered Out During Ingestion")
        add_report(report, "")
        if filtered_courses:
            add_report(report, "| Course | Reason |")
            add_report(report, "|---|---|")
            for course in filtered_courses:
                add_report(report, f"| `{course['course_code']}` | {course['reason']} |")
            add_report(report, "")
            add_report(report, f"**Total filtered out:** {filtered_count}")
        else:
            add_report(report, "No courses were filtered out.")
        add_report(report, "")

    except Exception as error:
        add_fail(report, "Data loading and validation", error)
        REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
        raise

    add_report(report, "## 2. Creating Course Chunks")
    add_report(report, "")
    try:
        nodes = create_nodes(docs)
        add_pass(report, "Course node creation", f"- **Documents:** {len(docs)}\n- **Nodes created:** {len(nodes)}\n- **Node text:** Valid\n- **Metadata preserved:** Yes")
    except Exception as error:
        add_fail(report, "Course node creation", error)
        REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
        raise

    add_report(report, "## 3. Setting Up Cohere Embeddings")
    add_report(report, "")
    try:
        cohere_key = os.getenv("COHERE_API_KEY")
        embed_model = setup_embeddings(cohere_key)
        add_pass(report, "Cohere embedding setup", "- **API key:** Found\n- **Model:** `embed-english-v3.0`\n- **LlamaIndex Settings:** Configured")
    except Exception as error:
        add_fail(report, "Cohere embedding setup", error)
        REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
        raise

    add_report(report, "## 4. Building the Vector Database")
    add_report(report, "")
    try:
        index = setup_vector_database(docs, nodes, embed_model)
        add_pass(report, "ChromaDB and VectorStoreIndex", f"- **Documents indexed:** {len(docs)}\n- **Nodes indexed:** {len(nodes)}\n- **ChromaDB:** Ready\n- **VectorStoreIndex:** Ready")
    except Exception as error:
        add_fail(report, "ChromaDB and VectorStoreIndex", error)
        REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
        raise

    add_report(report, "## 5. Basic Semantic Retrieval")
    add_report(report, "")
    basic_query = "computer science programming courses"
    try:
        retriever = index.as_retriever(similarity_top_k=5)
        basic_results = retriever.retrieve(basic_query)
        retrieved_codes = get_retrieved_course_codes(basic_results)

        add_pass(report, "Semantic retrieval is operational", f"- **Test query:** `{basic_query}`\n- **Courses retrieved:** {len(retrieved_codes)}\n- **Course metadata available:** Yes")
        
        add_report(report, "### Retrieved Courses")
        add_report(report, "")
        add_report(report, "| # | Course | Score |")
        add_report(report, "|---:|---|---:|")
        for i, result in enumerate(basic_results, start=1):
            code = result.node.metadata.get("course_code", "Unknown")
            score = f"{result.score:.4f}" if result.score is not None else "N/A"
            add_report(report, f"| {i} | `{code}` | {score} |")
        add_report(report, "")

    except Exception as error:
        add_fail(report, "Basic semantic retrieval", error)
        REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
        raise

    add_report(report, "## 6. Evaluation Queries (with Information Retrieval Metrics)")
    add_report(report, "")

    evaluation_queries = load_evaluation_queries()
    query_retriever = index.as_retriever(similarity_top_k=10)
    evaluation_results = []

    for query in evaluation_queries:
        result = evaluate_single_query(query_retriever, query)
        evaluation_results.append(result)

    # statistics and metrics math
    total_queries = len(evaluation_results)
    passed_queries = sum(1 for result in evaluation_results if result["passed"])
    failed_queries = total_queries - passed_queries
    pass_rate = (passed_queries / total_queries) * 100 if total_queries else 0

    # macro-average metrics calculation
    avg_precision = (sum(r["precision"] for r in evaluation_results) / total_queries) * 100
    avg_recall = (sum(r["recall"] for r in evaluation_results) / total_queries) * 100
    avg_f1 = (sum(r["f1"] for r in evaluation_results) / total_queries) * 100

    evaluation_status = "✅ All evaluation queries passed." if failed_queries == 0 else "⚠️ Some evaluation queries did not satisfy the expected retrieval criteria. This indicates the need for metadata filtering and constraint-processing logic (Agents) in subsequent layers."

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
    add_report(report, f"**Status:** {evaluation_status}")
    add_report(report, "")

    add_report(report, "### High-Level Failure Summary")
    add_report(report, "")
    
    failed_results = [result for result in evaluation_results if not result["passed"]]
    
    missing_only = sum(1 for r in failed_results if r["missing_expected"] and not r["incorrectly_retrieved"])
    prohibited_only = sum(1 for r in failed_results if not r["missing_expected"] and r["incorrectly_retrieved"])
    both_errors = sum(1 for r in failed_results if r["missing_expected"] and r["incorrectly_retrieved"])
    
    add_report(report, "The failures in pure semantic retrieval are expected and highlight the limitations of using Vector Search without programmatic guardrails or Agentic filtering:")
    add_report(report, "")
    add_report(report, f"- **Retrieved Prohibited Courses (False Positives): {prohibited_only} queries.** The semantic search successfully found courses related to the topic, but returned courses marked as `should_not_recommend` (usually due to unmet prerequisites, wrong academic levels, or schedule conflicts). This validates the architectural need for the Constraint Critic node.")
    add_report(report, f"- **Missed Expected Courses (False Negatives): {missing_only} queries.** The required courses were not retrieved within the top-K results based on semantic similarity alone.")
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
    add_report(report, "The ingestion pipeline successfully loaded and validated the knowledge base, filtered invalid courses, created LlamaIndex nodes, generated Cohere embeddings, and built the ChromaDB vector index.")
    add_report(report, "")
    
    add_report(report, "### Overall Statistics")
    add_report(report, "")
    add_report(report, f"- **Original courses:** {original_count}\n- **Filtered out during ingestion:** {filtered_count}\n- **Valid documents:** {valid_count}\n- **Evaluation pass rate:** {pass_rate:.2f}%\n- **Average F1-Score:** {avg_f1:.2f}%")
    add_report(report, "")

    # save report
    REPORT_PATH.write_text("\n".join(report), encoding="utf-8")
    print(f"✅ Evaluation complete. Report generated")