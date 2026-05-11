# 🧬 Stem Agent

A self-specializing AI agent that reads its task domain, designs its own architecture, 
and grows into a specialized agent — through its own process.

**Author:** Rafay Suleman Durrani

## Reports
- `/write_up.md`
- `/eval_report.md`

## Concept

A stem cell doesn't know what it will become. It reads signals from its environment.

This agent does the same:

1. **Differentiation** — Studies the task class; builds a blueprint of how experts solve it
2. **Morphogenesis** — Designs its own system prompt, reasoning protocol, tools, and rubric  
3. **Validation** — Tests itself; patches if score < 0.6 (built-in safeguard)
4. **Execution** — Runs as the specialized agent it became

For a different class of tasks, you start a new stem agent.

## Setup

```bash
# 1. Clone / unzip the project
cd stem-agent

# 2. Install dependencies (only one: openai)
pip install -r requirements.txt

# 3. Set your API key
export OPENAI_API_KEY=your_key_here

# 4. Run the demo
python demo.py                            # Code Review (default)
python demo.py --class "Security Audit"
python demo.py --class "Research Synthesis"

# 5. Run before/after evaluation
python demo.py --eval                     # Code Review eval
python demo.py --eval --all > run_final.log 2>&1   # All three task classes
# the terminal output will take some time and it will all be showed in the run_final.log
```

## What it produces

- **Specialized agent** with its own system prompt, reasoning protocol, tools
- **Quality score** from self-evaluation rubric the agent designed for itself
- **Evolution log** tracing each phase of specialization
- **Before/after comparison** vs generic assistant baseline

## Project Structure

```
stem-agent/
├── src/
│   └── stem_agent.py        # Core: StemAgent class + 4 phases
├── evals/
│   └── eval_runner.py       # Before/after evaluation framework
├── outputs/                 # Results from runs
├── docs/
│   └── writeup.md          # 4-page write-up
├── demo.py                  # CLI entry point
└── requirements.txt
```

## Supported Task Classes

| Class             | Agent Name           | Pattern |
|------------------|----------------------|---------|
| Code Review       | ExpertCode Auditor   | Iterative |
| Security Audit    | AuditPrime           | Threat-driven audit |
| Research Synthesis| SynthesisTable Pro   | Structured synthesis |

Add your own in `evals/eval_runner.py` → `EVAL_SCENARIOS`.

## Evaluation Results

Judge: `gpt-4o-mini` • Rubric: `SHARED_RUBRIC`  
Baseline: single-shot LLM (no protocol/tools) • Stem: full specialization pipeline

| Task Class        | Baseline| Stem Agent| Δ        | Improvement |
|------------------ |------:  |----------:|---------:|------------:|
| Code Review       | 0.880   | 0.860     | -0.020   | -2.3% |
| Security Audit    | 0.710   | 0.720     | +0.010   | +1.4% |
| Research Synthesis| 0.730   | 0.720     | -0.010   | -1.4% |
| **Average**       |**0.773**| **0.767** |**-0.007**| **-0.9%** |

**Summary:** Stem beat baseline in **1/3** task classes.  
Full results: `outputs/all_evals.json` (and `run_final.log` for the full trace).

Scoring: LLM-judge against `SHARED_RUBRIC` checklist (completeness, actionability, groundedness).
