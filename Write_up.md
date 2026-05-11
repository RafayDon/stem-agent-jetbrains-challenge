# 🧬 STEM AGENT  
## A Self-Specializing Agent Architecture  
JetBrains AI Agents Challenge 
**Author:** Rafay Suleman Durrani 

**Task Classes Evaluated:** Code Review, Security Audit, Research Synthesis
**Evaluation Method:** baseline vs self-specialized agent using a shared rubric and LLM judge
**Specialization Time:** multi-minute per class in the final run (see `run_final.log`)  
**Judge:** `gpt-4o-mini` • **Rubric:** `SHARED_RUBRIC`  

---

## Architecture Diagram (at a glance)

```text
Task Class + Example Tasks
          |
          v
(1) Differentiation  ────────────────┐
    - detect signals                 |
    - outline expert workflow        |
    - enumerate failure modes        |
          |                          |
          v                          |
      Blueprint (structured)         |
          |                          |
          v                          |
(2) Morphogenesis                    |
    - system prompt                  |
    - reasoning protocol             |
    - tool schema (simulated)        |
    - self-rubric                    |
          |                          |
          v                          |
   Specialized Agent (draft)         |
          |                          |
          v                          |
(3) Validation Loop  <───────────────┘
    - run sample task
    - score vs rubric
    - patch if score < 0.6
          |
          v
(4) Execution
    - run on real tasks
    - stop via class-specific criterion
```

---

## 1. The Question I Started With

The prompt asks: what if agents worked like stem cells — undifferentiated at birth, reading signals from their environment, and growing into what the situation demands?

My first instinct was to reach for complexity: a recursive meta-agent that modifies its own weights, spawns sub-agents, and converges through reinforcement. I sketched that for an hour. Then I deleted it.

The reason: the most interesting part of the stem cell metaphor isn't the transformation — it's the **mechanism** of transformation. A stem cell doesn't randomly mutate. It runs a structured developmental program, triggered by environmental signals, with checkpoints that can pull it back if something goes wrong. That’s the structure I wanted to preserve.

So I decomposed the problem into four biologically-motivated phases and asked: what’s the minimal implementation that captures each phase meaningfully?

---

## 2. Architecture: Four Phases

| Phase | Name | What it does |
|---:|---|---|
| 01 | **Differentiation** | Reads task class signals and examples. Produces a structured blueprint: workflow, failure modes, and an architecture recommendation. |
| 02 | **Morphogenesis** | Grows its own system prompt, reasoning protocol, tool definitions, and a self-evaluation rubric. |
| 03 | **Validation** | Self-tests on a sample task. Patches architecture if score < 0.6 (safeguard before commitment). |
| 04 | **Execution** | Runs as the specialized agent it became — using its own protocol, tools, and stopping criterion. |

### Phase 1 — Differentiation: Reading Environmental Signals

Before an agent can grow, it needs to understand its niche. The stem agent receives a `task_class` (e.g. “Code Review”) and a handful of example tasks — the environmental signal.

It produces a structured blueprint with fields like:
- **Core challenge** — what makes this class hard
- **Typical workflow** — how experts approach it step by step
- **Common failure modes** — where agents typically go wrong
- **Output criteria** — what makes output good or bad
- **Recommended architecture** — pattern, rationale, tool needs

This phase is undervalued in agent design. Many frameworks skip it — they assume you already know the architecture. The stem metaphor says: no, the architecture should emerge from understanding the domain.

### Phase 2 — Morphogenesis: Growing the Architecture

Using the blueprint, the agent designs itself — derived from domain understanding:
- A **specialized system prompt** (mindset/persona)
- A **reasoning protocol** (ordered steps matching expert workflow)
- **Tool definitions** tailored to the class
- A **self-evaluation rubric** (including weights) that the agent chooses

### Phase 3 — Validation: Built-In Safeguards

I implemented a self-test loop:
1. Run the newly-designed specialist on a sample task
2. Score the output against its rubric
3. If score < 0.6, patch the architecture and re-test

From the final run logs, each specialist passed validation (example validation scores: Code Review **0.890**, Security Audit **0.801**, Research Synthesis **0.718**)—sometimes after a patch round.

### Phase 4 — Execution: Running as the Specialized Agent

The validated agent runs on real tasks using its own protocol, tools, and stopping criterion. At this point it’s no longer a stem agent — it’s a specialist.

Tool execution is currently simulated (tools are described in the prompt). Live tool execution is straightforward to add; the core idea is the **specialization program** that produces the protocol, rubric, and stopping rules.

---

## 2.5 Concrete Example: One Specialization “Transformation”

This section shows an end-to-end artifact trail: **a toy input**, a **generated blueprint excerpt**, and a **protocol snippet** representing what the stem agent is trying to grow.

### Example input task (Code Review)

```python
def get_user(conn, user_id):
    query = f"SELECT * FROM users WHERE id = {user_id}"
    cur = conn.cursor()
    cur.execute(query)
    result = cur.fetchall()
    return result[0]["email"]
```

### Blueprint excerpt (what Differentiation produces)

```yaml
task_class: Code Review
core_challenge: >
  Find correctness + security issues while keeping signal-to-noise high, and
  propose fixes that are directly actionable.
typical_workflow:
  - "understand intent + inputs/outputs"
  - "scan for P0 security/correctness (injection, auth, data handling)"
  - "scan for reliability pitfalls (errors, edge cases, resource leaks)"
  - "propose concrete fixes with snippets"
common_failure_modes:
  - "spot issue but give no fix"
  - "generic advice without pointing to the exact construct"
  - "no severity ranking"
recommended_architecture:
  pattern: "iterative, priority-first"
  stopping_criterion: "all P0/P1 issues identified, ranked, and fixed concretely"
```

### Protocol snippet (what Morphogenesis grows)

```text
1) Restate intent + identify trust boundaries (where does user input enter?)
2) P0 pass: find vulnerabilities/correctness failures; for each, add:
   - why it’s risky
   - how to reproduce/fail
   - a concrete fix (code)
3) P1 pass: reliability + maintainability (errors, resource cleanup, edge cases)
4) Provide a ranked issue list (P0/P1/P2) + a “patch plan” checklist
Stop when: every ranked issue has a concrete fix or a clear next step.
```

This is the core claim of the project: the “stem cell” program produces *different, domain-specific operating procedures* rather than a single generic checklist.

---

## 3. Evaluation Design

### Setup

For each task class, two conditions are compared using a shared rubric (the same criteria for both), ensuring an apples-to-apples comparison:
- **Baseline:** single-shot LLM (no protocol/tools)
- **Stem:** full specialization pipeline

In the final run, evaluation used an LLM judge:
- **Judge:** `gpt-4o-mini`
- **Rubric:** `SHARED_RUBRIC`

### Results (final run)

| Task Class | Baseline | Stem Agent | Delta | Lift |
|---|---:|---:|---:|---:|
| Code Review | 0.880 | 0.860 | -0.020 | -2.3% |
| Security Audit | 0.710 | 0.720 | +0.010 | +1.4% |
| Research Synthesis | 0.730 | 0.720 | -0.010 | -1.4% |
| **Average** | **0.773** | **0.767** | **-0.007** | **-0.9%** |

Full results: `outputs/all_evals.json` (see also `run_final.log`).

### What the Numbers Show (updated)

This final run produced **mixed outcomes**:
This project prioritizes studying the emergence of specialization behavior over maximizing benchmark scores on a fixed evaluation harness.
- Specialization improved **Security Audit** slightly.
- It underperformed the baseline on **Code Review** and **Research Synthesis**.

Interpretation: the pipeline reliably generates coherent specialist protocols, but end-to-end gains are sensitive to:
- **Rubric/judge expectations** (especially “groundedness”: concrete, input-tied claims)
- Whether the specialization explicitly optimizes for those specific judge-visible signals
- The limitation of “self-critique by the same model” during patching

The central takeaway remains: specialization changes not just *style*, but the agent’s **workflow, priorities, and stopping rules** — even when that doesn’t always translate into a higher judge score.

---

## 4. Architectures Grown

Each specialist grown from a task class produces a distinct architecture — not just a different system prompt, but a different “theory of good work.”

In the final run, the grown agents were:

### Code Review — **ExpertCode Auditor**
**Pattern:** Iterative reviewer protocol (multi-step)  
**Stops when:** All prioritized issues have clear fixes, and the review is complete and structured.

### Security Audit — **AuditPrime**
**Pattern:** Threat-driven audit  
**Stops when:** Plausible exploit chains are demonstrated or ruled out, and mitigations are prioritized.

### Research Synthesis — **SynthesisTable Pro**
**Pattern:** Structured synthesis  
**Stops when:** The output moves beyond enumeration into an integrated view: agreements, tensions, and a justified conclusion with caveats.

---

## 5. What Surprised Me

The most surprising thing wasn’t “performance goes up.” It was what the agent changed about itself.

Across task classes, the differences were sharper than expected: different protocols, different rubric emphases, and — most tellingly — different stopping criteria.

A code review specialist stops when issues are prioritized and fixed concretely. A security specialist stops when exploit chains are established or ruled out. A synthesis specialist stops when tensions are integrated into a coherent picture. These are different theories of “when you know enough to stop,” encoded directly into the architecture the stem agent designs.

---

## 6. What Failed (and what’s fragile)

- **Patch mechanism echo chamber:** when the initial architecture fails self-testing, the same model critiques and repairs it. This can improve scores, but may plateau.
- **Simulated tools:** tools are described rather than executed; tool-dependent tasks (I/O, repo search, code execution) aren’t truly exercised.
- **Single specialization commit:** the agent specializes once, then executes. Real tasks often require cross-domain shifts.
- **LLM-judge correlation:** evaluation uses an LLM judge; it can reward presentation patterns (explicit grounding) and introduces correlated errors.
- **Rubric objective mismatch:** if the specialization doesn’t optimize for the judge’s groundedness expectations, it may regress even if outputs feel “more expert” to humans.

---

## 7. What I’d Do With More Time

- **Real tool execution** (repo reading, running tests, static analysis hooks)
- **Supervisor for validation** (stronger/differently-prompted model for critique than for generation)
- **Multi-turn specialization** (update protocols/rubrics over multiple tasks)
- **Cross-agent consultation** (recruit another specialist when needed)
- **Lineage tracking** (store evolution logs for analysis)
- **Ground-truth evaluation** (bug lists / known-vulnerable code; measure recall/precision)

---

## 8. Setup & Running the Code

### Installation

```
pip install -r requirements.txt
export OPENAI_API_KEY=your_key_here
```

### Run the Demo

```
python demo.py                            # Code Review (default)
python demo.py --class "Security Audit"
python demo.py --class "Research Synthesis"
```

### Run Before/After Evaluation

```
python demo.py --eval
python demo.py --eval --all > run_final.log 2>&1
```

Outputs are saved under `outputs/` (see `outputs/all_evals.json`).

---

Stem Agent · JetBrains AI Agents Challenge · May 2025