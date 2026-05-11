#!/usr/bin/env python3
"""
demo.py — Evaluation harness for the Stem Agent.

Both agents scored on SHARED_RUBRIC using JUDGE_MODEL.
Baseline is a true single-shot LLM call — no scaffolding.

Usage:
  python demo.py                        # Code Review demo
  python demo.py --eval --all           # all task classes vs baseline
  python demo.py --eval --task "Security Audit"
  python demo.py --task "Code Review" --run "Review this: ..."
"""

import argparse
import json
import os
import sys
import time

from src.stem_agent import (
    StemAgent,
    run_baseline_on_task,
    run_agent_on_task,
    score_output,
    get_eval_tasks,
    log,
    SHARED_RUBRIC,
    JUDGE_MODEL,
    GENERALIZATION_WARN_GAP,
)

os.makedirs("outputs", exist_ok=True)

TASK_CLASSES = {
    "Code Review": {
        "examples": [
            "Review this Python function for correctness and edge cases",
            "Check this SQL query for injection vulnerabilities",
            "Find race conditions in async JavaScript",
        ],
        "save_as": "outputs/code_review_agent.json",
        "eval_out": "outputs/code_review_eval.json",
    },
    "Security Audit": {
        "examples": [
            "Audit this login endpoint for OWASP Top 10 vulnerabilities",
            "Find session fixation and rate limiting weaknesses",
            "Check this file upload handler for path traversal and RCE",
        ],
        "save_as": "outputs/security_audit_agent.json",
        "eval_out": "outputs/security_audit_eval.json",
    },
    "Research Synthesis": {
        "examples": [
            "Synthesize recent papers on transformer efficiency methods",
            "Compare RL alignment approaches: RLHF, CAI, DPO",
            "Survey RAG retrieval strategies and their trade-offs",
        ],
        "save_as": "outputs/research_synthesis_agent.json",
        "eval_out": "outputs/research_synthesis_eval.json",
    },
}


def evaluate_task_class(name: str, config: dict) -> dict:
    print(f"\n{'='*62}")
    print(f"EVALUATING: {name}")
    print(f"{'='*62}")

    eval_tasks = get_eval_tasks(name)

    # ── TRUE baseline: single call_llm(), no protocol, no tools ──
    log("EVAL", f"BASELINE — single-shot LLM, no specialization ({len(eval_tasks)} tasks)")
    baseline_results = []
    for t in eval_tasks:
        output = run_baseline_on_task(name, t["task"])
        score, critique = score_output(t["task"], output, SHARED_RUBRIC)
        baseline_results.append({"task_id": t["id"], "score": score, "critique": critique})
        log("EVAL", f"  Baseline [{t['id']}]: {score:.3f}")
    baseline_avg = sum(r["score"] for r in baseline_results) / len(baseline_results)

    # ── Stem Agent: full 4-phase specialization ──
    log("EVAL", f"STEM AGENT — full specialization pipeline...")
    stem = StemAgent(name)
    stem.differentiate(config["examples"])
    val_score = stem.architecture.get("validation", {}).get("avg_score", 0.0)
    patch_rounds = stem.architecture.get("validation", {}).get("patch_rounds", 0)

    stem_results = []
    for t in eval_tasks:
        output = run_agent_on_task(stem.architecture, stem.blueprint, t["task"])
        score, critique = score_output(t["task"], output, SHARED_RUBRIC)
        stem_results.append({"task_id": t["id"], "score": score, "critique": critique})
        log("EVAL", f"  Stem [{t['id']}]: {score:.3f}")

    stem_avg = sum(r["score"] for r in stem_results) / len(stem_results)
    gen_gap = val_score - stem_avg

    if gen_gap > GENERALIZATION_WARN_GAP:
        log("EVAL", f"⚠  GENERALIZATION WARNING: val={val_score:.3f} eval={stem_avg:.3f} gap={gen_gap:.3f}")

    stem.save(config["save_as"])

    result = {
        "task_class": name,
        "baseline_avg": baseline_avg,
        "stem_avg": stem_avg,
        "delta": stem_avg - baseline_avg,
        "pct_change": 100 * (stem_avg - baseline_avg) / (baseline_avg + 1e-9),
        "val_score": val_score,
        "generalization_gap": gen_gap,
        "patch_rounds": patch_rounds,
        "improvement_history": stem.architecture.get("validation", {}).get("improvement_history", []),
        "baseline_results": baseline_results,
        "stem_results": stem_results,
        "judge_model": JUDGE_MODEL,
        "rubric": "SHARED_RUBRIC",
    }

    with open(config["eval_out"], "w") as f:
        json.dump(result, f, indent=2)
    log("EVAL", f"Results saved to {config['eval_out']}")
    return result


def print_summary(results: list[dict]) -> None:
    print(f"\n\n{'='*76}")
    print(f"RESULTS SUMMARY  —  judge: {results[0].get('judge_model', JUDGE_MODEL)}, rubric: SHARED_RUBRIC")
    print(f"Baseline: single-shot LLM (no protocol, no tools)")
    print(f"{'='*76}")
    print(
        f"{'Task Class':<24} {'Baseline':>8} {'Stem':>7} {'Delta':>7} "
        f"{'Δ%':>7} {'ValScore':>9} {'GenGap':>7} {'Patches':>8}"
    )
    print(f"{'-'*76}")
    for r in results:
        arrow = "▲" if r["delta"] > 0.01 else ("▼" if r["delta"] < -0.01 else "─")
        warn  = " ⚠" if r["generalization_gap"] > GENERALIZATION_WARN_GAP else "  "
        print(
            f"{r['task_class']:<24} {r['baseline_avg']:>8.3f} {r['stem_avg']:>7.3f} "
            f"{r['delta']:>+7.3f} {r['pct_change']:>+6.1f}%  {arrow} "
            f"{r['val_score']:>8.3f} {r['generalization_gap']:>+7.3f}{warn} "
            f"{r['patch_rounds']:>5} patches"
        )
    print(f"{'='*76}")

    beat = sum(1 for r in results if r["delta"] > 0.01)
    avg_delta = sum(r["delta"] for r in results) / len(results)
    print(f"\nStem beat baseline: {beat}/{len(results)} task classes")
    print(f"Average delta (SHARED_RUBRIC, {JUDGE_MODEL} judge): {avg_delta:+.3f}")

    with open("outputs/all_evals.json", "w") as f:
        json.dump(results, f, indent=2)
    log("EVAL", "Combined results → outputs/all_evals.json")


def main() -> None:
    parser = argparse.ArgumentParser(description="Stem Agent Evaluation Harness")
    parser.add_argument("--eval", action="store_true", help="Compare vs baseline")
    parser.add_argument("--all", action="store_true", help="All task classes")
    parser.add_argument("--task", default="Code Review", help="Task class")
    parser.add_argument("--run", default="", help="Run stem agent on custom task")
    args = parser.parse_args()

    if args.eval and args.all:
        results = [evaluate_task_class(n, c) for n, c in TASK_CLASSES.items()]
        print_summary(results)

    elif args.eval:
        if args.task not in TASK_CLASSES:
            print(f"Unknown task class '{args.task}'. Options: {list(TASK_CLASSES.keys())}")
            sys.exit(1)
        result = evaluate_task_class(args.task, TASK_CLASSES[args.task])
        print_summary([result])

    else:
        task_name = args.task if args.task in TASK_CLASSES else "Code Review"
        config = TASK_CLASSES[task_name]
        stem = StemAgent(task_name)
        stem.differentiate(config["examples"])

        eval_tasks = get_eval_tasks(task_name)
        task = args.run or eval_tasks[0]["task"]
        result = stem.run(task)

        print(f"\n{'='*62}")
        print(f"Agent: {result['agent']}")
        print(f"Score (SHARED_RUBRIC, {JUDGE_MODEL}): {result['quality_score']:.3f}")
        print(f"Critique: {result['critique']}")
        print(f"{'='*62}")
        print(result["output"])
        stem.save(config["save_as"])


if __name__ == "__main__":
    main()