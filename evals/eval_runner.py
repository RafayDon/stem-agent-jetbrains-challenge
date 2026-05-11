"""
eval_runner.py — Evaluation framework for the Stem Agent.

Measures quality gap between:
  BASELINE:   Single-shot LLM call (no protocol, no tools, no specialization)
  STEM AGENT: After full self-specialization (4 phases)

Both conditions are scored with the same SHARED_RUBRIC using JUDGE_MODEL.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.stem_agent import (
    StemAgent,
    score_output,
    run_baseline_on_task,
    log,
    SHARED_RUBRIC,
    JUDGE_MODEL,
)


# ── Eval Scenarios ────────────────────────────────────────────────────────────

EVAL_SCENARIOS = {
    "Code Review": {
        "description": "Reviewing code for bugs, style, security, and maintainability",
        "example_tasks": [
            "Review this Python function for correctness and edge cases",
            "Check this SQL query for injection vulnerabilities",
            "Review this async JavaScript code for race conditions",
        ],
        "eval_tasks": [
            (
                "Review this Python code for all issues. "
                "For each issue: name it, explain the risk, show fixed code. "
                "End with a fully corrected version:\n\n"
                "```python\n"
                "def get_user(db, user_id):\n"
                "    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n"
                "    result = db.execute(query)\n"
                "    return result[0]\n"
                "```"
            ),
            (
                "Review this JavaScript for bugs. For each bug: name it, explain the impact, "
                "show the fix. End with a fully corrected version:\n\n"
                "```js\n"
                "async function fetchData(url) {\n"
                "    let data = await fetch(url)\n"
                "    return data.json()\n"
                "}\n"
                "const results = []\n"
                "urls.forEach(url => {\n"
                "    fetchData(url).then(d => results.push(d))\n"
                "})\n"
                "console.log(results)\n"
                "```"
            ),
        ],
    },

    "Security Audit": {
        "description": "Identifying security vulnerabilities in systems and code",
        "example_tasks": [
            "Audit authentication flow for session fixation vulnerabilities",
            "Find OWASP Top 10 issues in this web application",
            "Review API endpoint security and rate limiting",
        ],
        "eval_tasks": [
            (
                "Audit this authentication endpoint. Required output: "
                "(1) severity-ranked vulnerability table (Critical/High/Medium/Low), "
                "(2) exploit scenario for each, "
                "(3) concrete code fix for each.\n\n"
                "POST /api/login — Body: { username, password }\n\n"
                "Implementation details:\n"
                "- Looks up user by username (no parameterized query)\n"
                "- Compares password with stored MD5 hash using ==\n"
                "- Returns JWT with 10-year expiry, no refresh token\n"
                "- No rate limiting on failed attempts\n"
                "- Session ID returned in URL parameter\n"
            ),
        ],
    },

    "Research Synthesis": {
        "description": "Synthesizing multiple sources into clear, structured insights",
        "example_tasks": [
            "Synthesize recent papers on LLM reasoning capabilities",
            "Compare approaches to RAG: dense vs sparse retrieval",
            "Summarize the state of AI safety research in 2024",
        ],
        "eval_tasks": [
            (
                "Synthesize these three abstracts on transformer efficiency. "
                "Required output: (1) comparison table (method vs. speed / memory / accuracy), "
                "(2) trade-offs for each, (3) open questions, "
                "(4) practitioner recommendation with justification.\n\n"
                "[Paper A] Linear attention approximates softmax attention with O(n) complexity but loses "
                "the ability to attend to rare tokens precisely, causing 15% degradation on "
                "needle-in-haystack retrieval tasks.\n\n"
                "[Paper B] Sparse attention patterns (top-k selection) recover most performance on "
                "downstream tasks while reducing compute by 60-70%, but require specialized CUDA kernels "
                "and degrade 8% on short sequences.\n\n"
                "[Paper C] FlashAttention achieves full softmax attention at reduced memory footprint "
                "via IO-aware tiling, with 2x throughput improvement and no accuracy loss, "
                "becoming the de facto standard in production systems.\n"
            ),
        ],
    },
}


# ── Run Evaluation ────────────────────────────────────────────────────────────

def run_evaluation(task_class: str, scenario: dict, save_dir: str = "outputs") -> dict:
    """Full before/after evaluation for one task class."""
    os.makedirs(save_dir, exist_ok=True)

    results: dict = {
        "task_class": task_class,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "judge_model": JUDGE_MODEL,
        "rubric_used": "SHARED_RUBRIC",
        "baseline": [],
        "stem_agent": [],
        "summary": {},
    }

    eval_tasks = scenario["eval_tasks"]
    examples   = scenario["example_tasks"]

    # ── TRUE baseline: single call_llm(), no protocol ──
    log("EVAL", f"BASELINE for '{task_class}' — single-shot LLM ({len(eval_tasks)} tasks)...")
    for task in eval_tasks:
        output = run_baseline_on_task(task_class, task)
        score, weakness = score_output(task, output, SHARED_RUBRIC)
        results["baseline"].append({
            "task_snippet": task[:120] + "...",
            "output_snippet": output[:300] + "...",
            "score": score,
            "main_weakness": weakness,
        })
        log("EVAL", f"  Baseline score: {score:.3f}")

    # ── Stem Agent ──
    log("EVAL", f"STEM AGENT for '{task_class}'...")
    stem = StemAgent(task_class)
    stem.differentiate(examples)

    for task in eval_tasks:
        result = stem.run(task)
        score, weakness = score_output(task, result["output"], SHARED_RUBRIC)
        results["stem_agent"].append({
            "task_snippet": task[:120] + "...",
            "agent_name": result["agent"],
            "output_snippet": result["output"][:300] + "...",
            "score": score,
            "main_weakness": weakness,
        })
        log("EVAL", f"  Stem agent score: {score:.3f}")

    # ── Summary ──
    n = len(eval_tasks)
    baseline_avg = sum(r["score"] for r in results["baseline"]) / n
    stem_avg     = sum(r["score"] for r in results["stem_agent"]) / n
    delta        = stem_avg - baseline_avg

    results["summary"] = {
        "baseline_avg": round(baseline_avg, 3),
        "stem_agent_avg": round(stem_avg, 3),
        "delta": round(delta, 3),
        "improvement_pct": round(delta / baseline_avg * 100, 1) if baseline_avg > 0 else 0.0,
        "agent_name": stem.architecture.get("agent_name", "Unknown"),
        "architecture_pattern": stem.blueprint.get("recommended_architecture", {}).get("pattern", "unknown"),
        "validation_score": stem.architecture.get("validation", {}).get("avg_score", None),
        "patch_rounds": stem.architecture.get("validation", {}).get("patch_rounds", 0),
        "n_tasks": n,
        "judge_model": JUDGE_MODEL,
    }

    stem.save(f"{save_dir}/{task_class.lower().replace(' ', '_')}_agent.json")
    out_path = f"{save_dir}/{task_class.lower().replace(' ', '_')}_eval.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    log("EVAL", f"Results saved to {out_path}")

    return results


def run_all_evals(scenarios: dict | None = None, save_dir: str = "outputs") -> dict:
    if scenarios is None:
        scenarios = EVAL_SCENARIOS

    all_results: dict = {}
    for task_class, scenario in scenarios.items():
        print(f"\n{'='*60}")
        print(f"EVALUATING: {task_class}")
        print("=" * 60)
        try:
            r = run_evaluation(task_class, scenario, save_dir)
            all_results[task_class] = r
        except Exception as e:
            log("EVAL", f"ERROR on {task_class}: {e}")
            all_results[task_class] = {"error": str(e)}

    print(f"\n\n{'='*70}")
    print(f"RESULTS SUMMARY  (judge: {JUDGE_MODEL}, rubric: SHARED_RUBRIC)")
    print(f"Baseline: single-shot LLM — no protocol, no tools")
    print("=" * 70)
    print(f"{'Task Class':<25} {'Baseline':>10} {'Stem Agent':>12} {'Delta':>8} {'Improvement':>12} {'Patches':>8}")
    print("-" * 70)
    for tc, r in all_results.items():
        if "error" not in r and "summary" in r:
            s = r["summary"]
            arrow = "▲" if s["delta"] > 0.01 else ("▼" if s["delta"] < -0.01 else "─")
            print(
                f"{tc:<25} {s['baseline_avg']:>10.3f} {s['stem_agent_avg']:>12.3f} "
                f"{s['delta']:>+8.3f} {s['improvement_pct']:>+11.1f}%  {arrow}  "
                f"{s['patch_rounds']:>4} patches"
            )

    out_path = f"{save_dir}/all_evals.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)
    log("EVAL", f"Combined results → {out_path}")

    return all_results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Stem Agent Evaluator")
    parser.add_argument("--task-class", choices=list(EVAL_SCENARIOS.keys()))
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--output-dir", default="outputs")
    args = parser.parse_args()

    if args.all:
        run_all_evals(save_dir=args.output_dir)
    elif args.task_class:
        r = run_evaluation(args.task_class, EVAL_SCENARIOS[args.task_class], args.output_dir)
        print("\n\nFINAL RESULT:")
        print(json.dumps(r["summary"], indent=2))
    else:
        r = run_evaluation("Code Review", EVAL_SCENARIOS["Code Review"], args.output_dir)
        print("\n\nFINAL RESULT:")
        print(json.dumps(r["summary"], indent=2))