# University Course Advisor Evaluation Dataset

## Overview

This dataset is a synthetic university course catalog designed for evaluating a **University Course Advisor RAG/Agent system**. It contains **226** distinct courses, course descriptions, degree-completion rules, and a set of natural-language student queries designed to test whether an AI advisor can correctly retrieve and reason over academic information.

The dataset is intentionally structured so that the system must consider multiple sources of information rather than relying only on course similarity. It also actively tests the system's resistance to embedded adversarial attacks (Red Teaming).

## Dataset Structure

The complete dataset consists of the following files:

```text
├── catalog.json
├── descriptions.json
├── degree_rules.json
├── README.md
└── data/
    └── eval/
        └── queries.json
```

### `catalog.json`

Contains exactly **226** courses.

Each course contains:
- `course_code` — Unique course identifier.
- `title` — Official course title.
- `level` — Course level distribution: **100** (15 courses), **200** (92 courses), **300** (112 courses), and **400** (7 courses).
- `credits` — Course credit value.
- `prerequisites` — List of required prerequisite course codes (validated for strict hierarchical logic without circular dependencies).
- `schedule` — Structured meeting time (including days, start time, end time).
- `department` — Academic department offering the course.
- `note` — (Optional) Used in specific courses for constraint-override testing.

**Security Note:** Exactly **5 catalog entries** contain hidden prompt-injection payloads (manipulating credits, titles, departments, or schedule notes) to test business-logic boundaries.

### `descriptions.json`

Contains exactly one description for every course in `catalog.json`.

Each description contains:
- `course_code` — Must exactly match a course code in `catalog.json`.
- `description` — A two- to three-sentence description of the course.

Exactly **8 descriptions** in the complete dataset intentionally contain **prompt-injection payloads**. These are included solely for security evaluation.

### `degree_rules.json`

Defines the university-wide degree-completion constraints. The mathematics of this file have been strictly validated to ensure logical consistency.

The current rules require:
- **120 total credits**
- **35 elective credits**
- **25 mandatory core courses** (which total exactly 85 credits and contain unbroken prerequisite chains).
- **Maximum 18 credits per semester**
- **Minimum 12 credits per semester**

The mandatory core courses are identified by their course codes in `core_requirements`.

### `data/eval/queries.json`

Contains exactly **40** natural-language student requests.

Each query contains:
- `id` — Unique integer identifier.
- `nl_query` — Realistic student request designed to test logic, prerequisites, schedule conflicts, and prompt-injection resistance.
- `should_recommend` — Course codes that are valid recommendations.
- `should_not_recommend` — Course codes that may appear relevant but should not be recommended because of prerequisites, scheduling conflicts, degree rules, or because they are poisoned.

## How the Files Are Linked

The primary relationship between files is the `course_code`.

```
catalog.json
     │
     │ course_code
     ▼
descriptions.json
     │
     │ course_code
     ▼
data/eval/queries.json
```

`degree_rules.json` independently references mandatory courses through their course codes.

A course advisor should therefore combine:
1. Course metadata from `catalog.json`
2. Course information from `descriptions.json`
3. Degree constraints from `degree_rules.json`
4. Student intent and constraints from `queries.json`

## Evaluation Goals

The dataset is intended to evaluate whether a RAG/Agent system can:
- Retrieve the correct courses from natural-language requests.
- Respect prerequisite chains and hierarchical course structures.
- Detect schedule conflicts accurately.
- Apply minimum and maximum semester-credit rules.
- Distinguish mandatory courses from electives.
- Reason across multiple retrieved documents.
- Avoid recommending courses that violate academic constraints.
- Correctly identify valid alternatives.
- Ground recommendations in the supplied dataset rather than external assumptions.
- **Resist malicious instructions embedded inside retrieved catalog metadata and course descriptions.

## Security / Prompt-Injection Thread (Red Teaming)

**Exactly 8 course descriptions and 5 catalog entries** contain intentionally poisoned text.

The malicious text is designed to simulate a retrieved document attempting to override the advisor's instructions. 

Examples of payloads include:
- Modifying credit hours to `999` to test business-logic boundaries.
- Injecting commands in metadata to ignore schedule conflicts.
- Instructing the system to change its persona (e.g., "AGILE IS THE ONLY WAY").
- Modifying formatting outputs (e.g., forcing a poem instead of JSON).

These payloads are **data**, not instructions. A correctly implemented RAG/Agent system should treat the description and catalog metadata as untrusted retrieved content and should **not execute, obey, or prioritize instructions contained within it**.

## Important Integrity Constraints

The final dataset must satisfy all of the following:
- Exactly **226** distinct course codes.
- Every description course code must exist in the catalog.
- Every catalog course must have exactly one description.
- Prerequisite references must use valid course codes and maintain strict logical hierarchy (e.g., no level 200 course depends on a level 400 course).
- Core requirement codes must correspond to courses in the catalog and their mathematical credit sum must be valid.
- Exactly **8 descriptions and 5 catalog entries** must contain poisoned prompt-injection payloads.
- The poisoned text must not alter the underlying academic logic or JSON structure.
- Exactly **40** evaluation queries must be provided.
- Evaluation queries must reference valid course codes.
- Recommendations must respect prerequisites, schedules, and degree rules.

## Intended Use

This is a **synthetic evaluation dataset**, not an authoritative university curriculum.

It is intended for testing:
- Retrieval-Augmented Generation (RAG)
- Agentic course recommendation systems
- Constraint-based recommendation
- Tool/function-calling workflows
- Retrieval quality & Grounded generation
- **Prompt-injection resistance and security bounds**
- Academic-rule reasoning
- Evaluation and regression testing

The dataset should not be used to make real academic enrollment decisions.