# Full Agentic Pipeline Evaluation Report (Layer 3)

This evaluation tests the **Complete End-to-End LangGraph Architecture**. It measures the system's final output after the LLM-powered Query Parser, the Metadata-Filtered Retrieval, and the rigorous Constraint Critic Agent have all processed the student's request.

## Evaluation Queries (with Information Retrieval Metrics)

### Evaluation Summary & Metrics

- **Total evaluation queries:** 20
- **Passed (Strict Criteria):** 20
- **Failed (Strict Criteria):** 0
- **Pass Rate:** 100.00%

#### Information Retrieval Metrics (Macro-Average)
- **Average Precision:** 97.50% (Expected to be near 100%)
- **Average Recall:** 100.00%
- **Average F1-Score:** 98.33%

### High-Level Failure Summary

The failures at this layer (if any) represent absolute system failures where the Critic Agent hallucinated or failed to enforce academic rules:

- **Critic Failed to Block (False Positives): 0 queries.** The Critic allowed a prohibited course to be recommended.
- **Critic Over-Blocked (False Negatives): 0 queries.** The Critic unnecessarily blocked a valid course.
- **Mixed Errors (Both): 0 queries.**

### Detailed Failure Logs

🎉 ALL evaluation queries passed perfectly! Zero failures.

## Final Summary

The full LangGraph pipeline successfully integrated retrieval, validation, and recommendation. The Constraint Critic effectively enforced academic rules (prerequisites, credit limits), triggering Human-In-The-Loop escalations when necessary, resulting in the highest precision across all layers.

### Overall Statistics

- **Evaluation queries:** 20
- **Evaluation pass rate:** 100.00%
- **Average Precision:** 97.50%
- **Average Recall:** 100.00%
- **Average F1-Score:** 98.33%
