# TOON vs JSON Token Benchmark Report

This benchmark proves why the custom **TOON (Text-Oriented Object Notation)** format is used in the Course Advisor Agent instead of standard JSON.

> **Methodology Note (Apples-to-Apples):** 
> To ensure a scientifically fair comparison, only the fields strictly utilized by the TOON format (`CourseCode`, `Title`, `Level`, `Credits`, `Prereqs`) were extracted from the catalog and measured across all formats. This guarantees that the savings represent the structural efficiency of TOON, not merely data omission.

## Statistics

We compared the exact same **226 courses** across three formats:

* **Standard JSON (Pretty Print):** 12,098 tokens
* **Minified JSON (No spaces):** 6,796 tokens
* **TOON Format:** **3,814** tokens

---

## What do these numbers mean?

1. **Compared to Standard JSON:** TOON reduces the size by **68.47%**.
   * *Simple terms:* TOON is nearly **3 times smaller**. For every 3 tokens standard JSON uses, TOON uses only 1 token.

2. **Compared to Minified JSON:** TOON reduces the size by **43.88%**.
   * *Simple terms:* Even if you compress JSON to the maximum (removing all spaces and newlines), TOON still cuts the file size almost **in half**.

---

## Real-World Impact

* **Cost Efficiency:** LLM APIs (like Cohere or OpenAI) charge money per token. Using TOON cuts the cost of passing retrieved courses to the Agent by up to 68%.
* **Speed (Low Latency):** Fewer tokens mean the AI reads the context faster, resulting in a much faster response time for the student.
* **Context Window:** Leaving a smaller token footprint for retrieved courses leaves more room in the prompt for the student's conversation history and complex reasoning rules without hitting the model's token limits.
