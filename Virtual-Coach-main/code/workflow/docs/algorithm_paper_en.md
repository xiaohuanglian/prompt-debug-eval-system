# **Algorithm: Iterative RAG-Guided Workflow Synthesis with Formal Verification**

### **Problem Setup**

We consider a workflow synthesis system where each atomic capability is encapsulated as a **node** described by a JSON specification (e.g., type, parameters, I/O schema), and a complete workflow is represented as a JSON configuration composed of multiple nodes and their connections. Given a user’s natural-language requirement (and optional raw files), the goal is to automatically synthesize a workflow JSON that satisfies the requirement while conforming to a predefined workflow format and node constraints documented in a knowledge base.

Let

* **\mathcal{K} = \{d_i\}** denote a documentation knowledge base (workflow definitions, node definitions, action definitions, and implementation notes),
* **x** denote a user request, consisting of a textual requirement **r** and optional raw files **f**,
* **W** denote a candidate workflow JSON,
* **\mathrm{Verify}(W) \to (\texttt{ok}, \mathcal{E})** be a formal verifier that returns a boolean and a set of validation errors **\mathcal{E}**.

We aim to produce a verified workflow **W^\*** and an execution trace (log) capturing retrieval, planning, and verification decisions.

---

### **Overview**

The proposed method iteratively alternates between:

1. **Planning** a candidate workflow using an LLM conditioned on the current retrieved knowledge,
2. **Formal verification** against workflow/node specifications and template constraints, and
3. **Targeted retrieval** that expands the knowledge context when the candidate is invalid or uncertain.

This design enables (i) compliance with strict workflow formats via verification, and (ii) efficient retrieval by loading only the most relevant documentation when needed.

---

### **Components**

**Retriever**\mathrm{Retrieve}(\mathcal{K}, q)**: returns top-**k** documentation chunks relevant to query **q** (RAG).**

**Planner** **\mathrm{Plan}(r,f,\mathcal{C})**: an LLM-based planner producing a candidate workflow **W** and a structured rationale, conditioned on context **\mathcal{C}**.

**Verifier** **\mathrm{Verify}(W)**: a two-stage checker:

* **Schema check** (e.g., JSON Schema/Pydantic): validates structural format and types.
* **Rule check**: validates graph topology, node existence, I/O compatibility, parameter constraints, and optional alignment to standard workflow templates.

**Gap Analyzer** **\mathrm{Gap}(\mathcal{E})**: converts verification errors into retrieval intents/queries to fetch missing constraints or examples.

---

### **Algorithm Description**

We maintain a context set **\mathcal{C}** of retrieved knowledge and an iteration budget **T**.

1. **Initialize (Level-0 Knowledge):**
   Load base workflow and node format definitions (e.g., **workflow/base.md**, **node/base.md**), plus a lightweight index/registry of available node/workflow types. This yields the initial context **\mathcal{C}_0**.
2. **Iterative Synthesis Loop:** For **t = 1** to **T**:
   * **Planning:** Use the planner to generate a candidate workflow:
     **(W_t, \pi_t, s_t) \leftarrow \mathrm{Plan}(r,f,\mathcal{C}_{t-1}),**
     where **\pi_t** is a structured decision trace (e.g., selected node types and their rationale), and **s_t** is an optional confidence/uncertainty signal.
   * **Formal Verification:**
     **(\texttt{ok}_t, \mathcal{E}_t) \leftarrow \mathrm{Verify}(W_t).**
     **If **\texttt{ok}_t = \texttt{true}**, output **W^\* = W_t** and stop.**
   * **Targeted Retrieval (Level-1 Knowledge Expansion):**
     If verification fails (or confidence is below a threshold), derive missing knowledge needs from **\mathcal{E}_t**:
     **Q_t \leftarrow \mathrm{Gap}(\mathcal{E}_t, \pi_t),**
     then expand context:
     **\Delta \mathcal{C}_t \leftarrow \mathrm{Retrieve}(\mathcal{K}, Q_t), \quad
     \mathcal{C}_t \leftarrow \mathcal{C}_{t-1} \cup \Delta \mathcal{C}_t.**
     Continue to the next iteration.
3. **Termination:**
   If no verified workflow is produced after **T** iterations, return the best candidate along with the failure reasons **\mathcal{E}_{T}** and an explicit stop reason (max-iteration reached).
4. **Human-in-the-loop Correction and Bug Injection (Optional):**
   The user or an external validator may provide corrections or bug reports **\beta**. We treat **\beta** as additional requirements **\Delta r**, update **r \leftarrow r \oplus \Delta r**, and re-run the synthesis loop starting from Step 1 or Step 2 with cached context.

---

### **Logging and Reproducibility**

At each iteration, the system logs:

* the input requirement and file summaries,
* retrieved document identifiers and scores,
* planner outputs (workflow draft hash, decision trace),
* verifier outcomes (schema errors, rule violations),
* next retrieval intents.

This log enables reproducibility, debugging, and offline analysis of retrieval/planning failure modes.

---

### **Pseudocode**

```
Algorithm 1: RAG-Verifiable Workflow Synthesis
Input: requirement r, optional files f, knowledge base K, max iterations T
Output: verified workflow W* (if found), decision trace Π, run log L

1: C ← LoadBaseKnowledge(K)            ▷ Level-0: base workflow/node specs
2: Initialize log L
3: for t = 1..T do
4:     (W, π, s) ← Plan(r, f, C)       ▷ LLM planning with current context
5:     Append(L, "PLAN", t, hash(W), π, s)
6:     (ok, E) ← Verify(W)             ▷ schema + rule checks
7:     Append(L, "VERIFY", t, ok, E)
8:     if ok then
9:         return (W, π, L)
10:    Q ← Gap(E, π)                   ▷ derive missing knowledge needs
11:    D ← Retrieve(K, Q)              ▷ targeted retrieval (Level-1 expansion)
12:    C ← C ∪ D
13:    Append(L, "RETRIEVE", t, Q, ids(D))
14: end for
15: return (BestEffort(W), π, L)       ▷ with stop_reason = max_iter
```

---

### **Notes on Design Choices**

* **Separation of concerns:** planning is probabilistic, verification is deterministic, which improves reliability.
* **Targeted retrieval:** reduces context length and avoids injecting irrelevant constraints, improving both efficiency and correctness.
* **Template-aware verification:** when standard workflows are provided, constraints can be expressed as mandatory substructures, improving format adherence.
