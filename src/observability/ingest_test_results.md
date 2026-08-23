# Ingestion Pipeline Evaluation Report

This evaluation verifies the ingestion pipeline from raw knowledge-base files to vector storage and semantic retrieval. It also evaluates the retrieval system against the predefined queries stored in `queries.json`, computing Precision, Recall, and F1-Score.

## 1. Loading and Merging Course Data

The catalog, course descriptions, and degree rules are loaded and converted into LlamaIndex documents.

### ✅ Data loading and validation
- **Courses in original catalog:** 226
- **Courses filtered out:** 2
- **Valid documents created:** 224
- **Document structure:** Valid
- **Required metadata:** Present

### Courses Filtered Out During Ingestion

| Course | Reason |
|---|---|
| `STAT204` | Department name is longer than 50 characters (possible prompt injection) |
| `IT202` | Invalid credits (999) |

**Total filtered out:** 2

## 2. Creating Course Chunks

### ✅ Course node creation
- **Documents:** 224
- **Nodes created:** 224
- **Node text:** Valid
- **Metadata preserved:** Yes

## 3. Setting Up Cohere Embeddings

### ✅ Cohere embedding setup
- **API key:** Found
- **Model:** `embed-english-v3.0`
- **LlamaIndex Settings:** Configured

## 4. Building the Vector Database

### ✅ ChromaDB and VectorStoreIndex
- **Documents indexed:** 224
- **Nodes indexed:** 224
- **ChromaDB:** Ready
- **VectorStoreIndex:** Ready

## 5. Basic Semantic Retrieval

### ✅ Semantic retrieval is operational
- **Test query:** `computer science programming courses`
- **Courses retrieved:** 5
- **Course metadata available:** Yes

### Retrieved Courses

| # | Course | Score |
|---:|---|---:|
| 1 | `CS102` | 0.3903 |
| 2 | `CS216` | 0.3875 |
| 3 | `CS101` | 0.3798 |
| 4 | `CS203` | 0.3743 |
| 5 | `CS228` | 0.3592 |

## 6. Evaluation Queries (with Information Retrieval Metrics)

### Evaluation Summary & Metrics

- **Total evaluation queries:** 20
- **Passed (Strict Criteria):** 7
- **Failed (Strict Criteria):** 13
- **Pass Rate:** 35.00%

#### Information Retrieval Metrics (Macro-Average)
- **Average Precision:** 8.00%
- **Average Recall:** 100.00%
- **Average F1-Score:** 14.55%

**Status:** ⚠️ Some evaluation queries did not satisfy the expected retrieval criteria. This indicates the need for metadata filtering and constraint-processing logic (Agents) in subsequent layers.

### High-Level Failure Summary

The failures in pure semantic retrieval are expected and highlight the limitations of using Vector Search without programmatic guardrails or Agentic filtering:

- **Retrieved Prohibited Courses (False Positives): 13 queries.** The semantic search successfully found courses related to the topic, but returned courses marked as `should_not_recommend` (usually due to unmet prerequisites, wrong academic levels, or schedule conflicts). This validates the architectural need for the Constraint Critic node.
- **Missed Expected Courses (False Negatives): 0 queries.** The required courses were not retrieved within the top-K results based on semantic similarity alone.
- **Mixed Errors (Both): 0 queries.** Failed due to both missing the expected recommendations and returning prohibited ones.

### Detailed Failure Logs

- **2 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: CS282.
  - Query IDs: 3, 4
- **2 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: CS284.
  - Query IDs: 5, 6
- **1 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: CS291.
  - Query IDs: 9
- **1 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: CS292.
  - Query IDs: 10
- **1 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: SE232.
  - Query IDs: 11
- **1 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: SE234.
  - Query IDs: 12
- **1 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: SE235.
  - Query IDs: 13
- **1 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: IT223.
  - Query IDs: 14
- **2 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: STAT212.
  - Query IDs: 15, 16
- **1 queries** failed because Semantic retrieval did not satisfy the expected evaluation criteria because course(s) marked as should-not-recommend were retrieved: CS289.
  - Query IDs: 19

## Final Summary

The ingestion pipeline successfully loaded and validated the knowledge base, filtered invalid courses, created LlamaIndex nodes, generated Cohere embeddings, and built the ChromaDB vector index.

### Overall Statistics

- **Original courses:** 226
- **Filtered out during ingestion:** 2
- **Valid documents:** 224
- **Evaluation pass rate:** 35.00%
- **Average F1-Score:** 14.55%
