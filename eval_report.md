# 🧬 STEM AGENT  
## Evaluation Report: Before vs After Specialization  
JetBrains AI Agents Challenge · May 2025  
**Author:** Rafay Suleman Durrani

**Task Classes:** 3 (Code Review, Security Audit, Research Synthesis)  
**Judge:** `gpt-4o-mini` · **Rubric:** `SHARED_RUBRIC`  

**Topline (final run):**
- **Baseline Avg:** **0.773** (generic assistant)
- **Stem Avg:** **0.767** (after specialization)
- **Core contribution:** specialization consistently produced distinct **operational reasoning procedures and stopping criteria across domains**
- **Outcome:** mixed benchmark results under a shared LLM-judge evaluation (table below)

> Note: This report reflects the **final run** captured in `run_final.log` and the per-scenario JSONs in `outputs/`.

---

## Evaluation Methodology

Two conditions are compared:

- **Baseline:** single-shot LLM (no specialization protocol/tools)
- **Stem Agent:** full 4-phase specialization pipeline (differentiate → morphogenesis → validation/patch → execution)

Controls:
- **Same judge** (`gpt-4o-mini`) and **same rubric** (`SHARED_RUBRIC`) for both conditions.
- Identical evaluation harness per scenario; only the specialization pipeline differs.

---

## Aggregate Results (final run)

| Task Class | Baseline | Stem Agent | Delta | Improvement |
|---|---:|---:|---:|---:|
| Code Review | 0.880 | 0.860 | -0.020 | -2.3% |
| Security Audit | 0.710 | 0.720 | +0.010 | +1.4% |
| Research Synthesis | 0.730 | 0.720 | -0.010 | -1.4% |
| **Average** | **0.773** | **0.767** | **-0.007** | **-0.9%** |

Artifacts:
- `outputs/all_evals.json`
- `outputs/code_review_eval.json`
- `outputs/security_audit_eval.json`
- `outputs/research_synthesis_eval.json`

---

## Code Review — Summary

**Agent grown:** **ExpertCode Auditor**  
**Validation score:** **0.890**  

**Baseline:** 0.880  
**Stem Agent:** 0.860 (**-0.020**)  

**Interpretation:** The specialization produced a more explicit protocol, but under this judge/rubric it did not outperform the baseline. A common failure mode with LLM-judged rubrics is that better “process” doesn’t automatically yield better “evidence”: the judge tends to reward very concrete, input-anchored findings and fixes (and may penalize verbosity or weaker grounding).

---

## Security Audit — Summary

**Agent grown:** **AuditPrime**  
**Validation score:** **0.801**  

**Baseline:** 0.710  
**Stem Agent:** 0.720 (**+0.010**)  

**Interpretation:** This class saw a small but positive lift. Security Audit benefited most from specialization because the domain naturally rewards **structured threat modeling** and **prioritized mitigation workflows**, which map cleanly onto the rubric’s “structure” and “actionability” criteria.

---

## Research Synthesis — Summary

**Agent grown:** **SynthesisTable Pro**  
**Validation score:** **0.718**  

**Baseline:** 0.730  
**Stem Agent:** 0.720 (**-0.010**)  

**Interpretation:** The specialized synthesis protocol was more structured, but the judge score decreased slightly. Under an LLM judge, synthesis outputs typically score best when they explicitly map every claim back to input chunks/sources and make decision guidance maximally concrete; missing those “grounding signals” can outweigh improvements in organization.

---

## Evolution Log — Code Review Specialization (final run)

A trace of the stem agent’s self-transformation into **ExpertCode Auditor**.

- **START:** Stem agent initialized. Task class: Code Review.
- **DIFFERENTIATION:** Blueprint produced (workflow, failure modes, output criteria, recommended pattern).
- **MORPHOGENESIS:** Architecture grown (system prompt + protocol + rubric).
- **VALIDATION:** Self-test executed; architecture reached passing threshold (validation score **0.890**).
- **SPECIALIZED → EXECUTION:** Specialized agent executed on the evaluation scenario.

> Full trace details live in `run_final.log`.

---

## Key Findings (updated)

### Finding 1: Specialization changes the *shape* of reasoning (even when score doesn’t improve)
Across domains, specialization consistently produced distinct **operational reasoning procedures** and **stopping criteria**. The pipeline outputs agents that “work differently,” not just “talk differently.”

### Finding 2: End-to-end lift is not guaranteed under a fixed judge/rubric
In this run, specialization added structure without reliably increasing rubric-visible quality (especially “specificity/grounding”). The goal of this project was to study whether **specialization behavior can emerge autonomously**, not solely to maximize benchmark scores.

### Finding 3: Validation passing does not imply evaluation improvement
All specialists passed the internal validation threshold, yet two classes still regressed on the external eval. Internal validation acts as a guardrail against obviously-bad protocols, but is not yet a strong proxy for the shared rubric’s final score.

### Finding 4: Scoring method matters (and is a target for future work)
Shared-rubric evaluation is fair, but LLM-judge scoring often rewards specific presentation patterns (tight grounding, explicit references, concrete fixes). Future iterations should tune the specialization/validation objective to better match these judge-visible signals.

---

Stem Agent Evaluation Report · JetBrains AI Agents Challenge · May 2025