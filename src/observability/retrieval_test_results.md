# Filtered Retrieval Evaluation Report (Layer 2)

This evaluation tests the **Retrieval Layer** combined with **Metadata & Schedule Filters**. By applying parsed constraints (like credit limits, schedules, and levels), we expect a significant jump in Precision compared to the base Ingestion evaluation.

## Evaluation Queries (with Information Retrieval Metrics)

### Evaluation Summary & Metrics

- **Total evaluation queries:** 20
- **Passed (Strict Criteria):** 10
- **Failed (Strict Criteria):** 10
- **Pass Rate:** 50.00%

#### Information Retrieval Metrics (Macro-Average)
- **Average Precision:** 16.00%
- **Average Recall:** 100.00%
- **Average F1-Score:** 26.67%

### High-Level Failure Summary

The failures at this layer show the limits of metadata filtering alone:

- **Retrieved Prohibited Courses (False Positives): 10 queries.** Metadata filters cannot catch unmet prerequisites (since they require comparing student history with course strings). This proves the need for the Final Agent (Critic).
- **Missed Expected Courses (False Negatives): 0 queries.** The required courses were not retrieved within the top-K results.
- **Mixed Errors (Both): 0 queries.** Failed due to both missing the expected recommendations and returning prohibited ones.

### Detailed Failure Logs

- **2 queries** failed because Filtered retrieval failed because prohibited course(s) were retrieved despite filters: CS282.
  - Query IDs: 3, 4
- **2 queries** failed because Filtered retrieval failed because prohibited course(s) were retrieved despite filters: CS284.
  - Query IDs: 5, 6
- **1 queries** failed because Filtered retrieval failed because prohibited course(s) were retrieved despite filters: CS291.
  - Query IDs: 9
- **1 queries** failed because Filtered retrieval failed because prohibited course(s) were retrieved despite filters: CS292.
  - Query IDs: 10
- **1 queries** failed because Filtered retrieval failed because prohibited course(s) were retrieved despite filters: SE232.
  - Query IDs: 11
- **1 queries** failed because Filtered retrieval failed because prohibited course(s) were retrieved despite filters: IT223.
  - Query IDs: 14
- **2 queries** failed because Filtered retrieval failed because prohibited course(s) were retrieved despite filters: STAT212.
  - Query IDs: 15, 16

## Final Summary

The retrieval pipeline successfully applied the LLM-parsed metadata filters to the vector search. While Precision improved over pure semantic search, some violations (like prerequisites) still bypass the filters, requiring Agentic validation.

### Overall Statistics

- **Evaluation queries:** 20
- **Evaluation pass rate:** 50.00%
- **Average Precision:** 16.00%
- **Average Recall:** 100.00%
- **Average F1-Score:** 26.67%
