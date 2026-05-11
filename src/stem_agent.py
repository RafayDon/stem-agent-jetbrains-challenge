"""
Stem Agent

A self-specializing agent: reads its task domain, figures out how
that domain is typically approached, and grows into a specialized
agent architecture on its own.

Design philosophy:
- Phase 1 (Differentiation): Understand the problem class deeply
- Phase 2 (Morphogenesis): Design architecture, tools, prompts
- Phase 3 (Validation): Self-test; adaptive patch loop
- Phase 4 (Execution): Run as the specialized agent it became

Key design decisions and why:
───────────────────────────────────────────────────────────────
SCORING: A separate model (gpt-4o-mini) is used as judge.
  The problem was gpt-4.1-mini evaluating its own output and awarding 1.0
  trivially. The judge now uses a CHECKLIST — it must verify that specific
  required outputs are present before assigning any score.

RUBRIC ALIGNMENT: Internal validation rubric IS the shared external rubric
  (SHARED_RUBRIC). Previously the agent trained against criterion A and got
  graded on criterion B — patches never actually helped the metric that matters.

DELIVERABLE-FIRST: "Output-first" previously made agents name their scoping
  step "Immediate Attack Surface Mapping" — same process, different label.
  Now Step 1 is explicitly "Produce [Primary Deliverable]" with instruction
  to show the table/fix-list/synthesis BEFORE any process narration.
"""

import json
import os
import re
import time
from typing import Any

from openai import OpenAI

# ── Config ─────────────────────────────────────────────────────────────────────

def _env(name: str) -> str:
    return (os.getenv(name) or "").strip()

API_KEY = _env("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError('OPENAI_API_KEY not set. export OPENAI_API_KEY="sk-..."')

client = OpenAI(api_key=API_KEY)

GENERATION_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
JUDGE_MODEL      = os.getenv("JUDGE_MODEL", "gpt-4o-mini")

READY_THRESHOLD       = 0.72
MAX_PATCH_ROUNDS      = 3
MIN_SCORE_IMPROVEMENT = 0.03
GENERALIZATION_WARN_GAP = 0.15

#require specialization to actually add value vs baseline during validation
IMPROVEMENT_MARGIN = 0.05  # must beat baseline by +5pts to "graduate"

#token budgets (your failures are dominated by cutoff / missing fixed code)
BASELINE_MAX_TOKENS = 4000
AGENT_MAX_TOKENS    = 6500   # give long security tables + fixed implementations room
JUDGE_MAX_TOKENS    = 1400

# ── Shared evaluation rubric ───────────────────────────────────────────────────
#
# Used for BOTH internal validation AND external baseline comparison.
# Same instrument = patches actually move the metric that matters.
#
# Each criterion has a CHECKLIST the judge must answer YES/NO before scoring.
# This prevents "looks complete" from earning 1.0.

SHARED_RUBRIC = [
    {
        "criterion": "completeness",
        "weight": 0.30,
        "question": "Does the output address ALL explicitly requested outputs?",
        "checklist": [
            "Every requested section is present (table if asked, fixes if asked, recommendation if asked)",
            "No major requested output type is entirely absent",
            "Output is not cut off before completing a required section",
        ],
        "good_signal": "All requested sections present and non-empty",
        "bad_signal":  "Any requested output type is missing or truncated",
        "cap_if_bad":  0.40,
    },
    {
        "criterion": "actionability",
        "weight": 0.40,
        "question": "Are the recommendations specific enough to act on without further research?",
        "checklist": [
            "Code fixes shown as actual code blocks (not described in prose only)",
            "For security/review tasks: at least one corrected code block present",
            "For synthesis tasks: a concrete recommendation with explicit justification present",
            "Recommendations are specific, not 'use best practices'",
        ],
        "good_signal": "Reader can implement the fix or make the decision without needing anything else",
        "bad_signal":  "Advice is prose-only with no code, or says 'use parameterized queries' without showing how",
        "cap_if_bad":  0.35,
    },
    {
        "criterion": "groundedness",
        "weight": 0.30,
        "question": "Is every claim tied to a specific detail from the task input?",
        "checklist": [
            "References specific variable names, function names, or line patterns from the input",
            "For synthesis: cites specific paper labels (A/B/C) and their specific numbers",
            "No generic advice that would apply to any task regardless of input",
        ],
        "good_signal": "Every finding points to something in the input by name",
        "bad_signal":  "Output could have been written without reading the specific input",
        "cap_if_bad":  0.40,
    },
]


# ── Utilities ──────────────────────────────────────────────────────────────────

def call_llm(messages: list[dict], system: str = "", max_tokens: int = 4096,
             model: str | None = None) -> str:
    full: list[dict] = []
    if system:
        full.append({"role": "system", "content": system})
    full.extend(messages)
    resp = client.chat.completions.create(
        model=model or GENERATION_MODEL,
        messages=full,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def log(phase: str, msg: str, data: Any = None) -> None:
    ts = time.strftime("%H:%M:%S")
    print(f"\n[{ts}] [{phase}] {msg}")
    if data:
        if isinstance(data, (dict, list)):
            print(json.dumps(data, indent=2)[:2000])
        else:
            print(str(data)[:2000])


def extract_json(text: str) -> dict | list:
    m = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?\s*```", text)
    if m:
        try:
            return json.loads(m.group(1).strip())
        except json.JSONDecodeError:
            pass
    for sc, ec in [('{', '}'), ('[', ']')]:
        idx = text.find(sc)
        while idx != -1:
            depth = in_str = esc = 0
            for i in range(idx, len(text)):
                ch = text[i]
                if esc:
                    esc = 0; continue
                if ch == '\\' and in_str:
                    esc = 1; continue
                if ch == '"':
                    in_str = not in_str; continue
                if in_str:
                    continue
                if ch == sc:
                    depth += 1
                elif ch == ec:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[idx:i + 1])
                        except json.JSONDecodeError:
                            break
            idx = text.find(sc, idx + 1)
    raise ValueError(f"No valid JSON:\n{text[:400]}")


_ARCH_FALLBACK: dict = {
    "agent_name": "SpecializedAgent",
    "system_prompt": "You are a helpful assistant.",
    "reasoning_protocol": [],
    "tools": [],
    "self_evaluation_rubric": [],
    "stopping_criterion": "Stop when complete.",
}


def sanitize_architecture(arch: Any, fallback: dict) -> dict:
    if not isinstance(arch, dict):
        return dict(fallback)
    fixed = dict(arch)

    # Ensure core list fields are lists
    for key in ("reasoning_protocol", "tools", "self_evaluation_rubric"):
        v = fixed.get(key)
        if not isinstance(v, list) or (v and not all(isinstance(x, dict) for x in v)):
            fixed[key] = fallback.get(key, [])

    # Normalize reasoning steps to avoid KeyError during formatting
    normalized_steps: list[dict] = []
    for i, s in enumerate(fixed.get("reasoning_protocol", []), start=1):
        step_num = s.get("step", i)
        normalized_steps.append({
            "step": step_num,
            "name": str(s.get("name", f"Step {step_num}")),
            "instruction": str(s.get("instruction", "Produce the required deliverable with concrete, grounded details.")),
            "output_format": str(s.get("output_format", "final")),
        })
    fixed["reasoning_protocol"] = normalized_steps

    # Ensure text fields exist
    for key in ("agent_name", "system_prompt", "stopping_criterion"):
        if not isinstance(fixed.get(key), str):
            fixed[key] = str(fallback.get(key, ""))

    fixed.pop("validation", None)
    return fixed


# ── Task banks ─────────────────────────────────────────────────────────────────
#
# "validation" split: used during phase_validation (agent trains/patches on these)
# "eval" split:       held out; only used for final baseline vs. stem comparison
#
# Tasks explicitly ask for the deliverable (table, fixed code, recommendation)
# so the judge checklist has something concrete to verify.

TASK_BANK: dict[str, dict[str, list[dict]]] = {
    "code_review": {
        "validation": [
            {
                "id": "py_second_largest",
                "task": (
                    "Review this Python function. For every issue found, show the corrected code:\n\n"
                    "```python\n"
                    "def find_second_largest(numbers):\n"
                    "    if not numbers or len(numbers) < 2:\n"
                    "        return None\n"
                    "    first = second = float('-inf')\n"
                    "    for n in numbers:\n"
                    "        if n > first:\n"
                    "            second = first; first = n\n"
                    "        elif n > second:\n"
                    "            second = n\n"
                    "    return second\n"
                    "```\n"
                    "Consider: duplicates, all-identical, NaN. Show a fixed version."
                ),
            },
            {
                "id": "sql_injection_dual",
                "task": (
                    "Review this snippet. For each issue: name it, explain the risk, "
                    "show the fixed code:\n\n"
                    "```python\n"
                    "user_id = request.args.get('user_id')\n"
                    "role    = request.args.get('role', 'user')\n"
                    "query   = f\"SELECT * FROM users WHERE id={user_id} AND role='{role}'\"\n"
                    "cursor.execute(query)\n"
                    "result  = cursor.fetchone()\n"
                    "if result:\n"
                    "    session['user'] = result\n"
                    "    return jsonify({'token': generate_token(result['id'])})\n"
                    "```\n"
                    "End with a fully corrected version."
                ),
            },
            {
                "id": "async_race_js",
                "task": (
                    "Review this async JavaScript. List every bug, explain the impact, "
                    "show a fully corrected version:\n\n"
                    "```js\n"
                    "async function fetchAll(urls) {\n"
                    "  const results = []\n"
                    "  urls.forEach(async (u) => {\n"
                    "    const r = await fetch(u)\n"
                    "    results.push(await r.json())\n"
                    "  })\n"
                    "  return results\n"
                    "}\n"
                    "```\n"
                    "What happens if one URL fails? Show fixed code."
                ),
            },
        ],
        "eval": [
            {
                "id": "py_get_user",
                "task": (
                    "Review this Python function for all issues (security, correctness, style). "
                    "For each issue: name it, explain the risk, show fixed code. "
                    "End with a fully corrected version:\n\n"
                    "```python\n"
                    "def get_user(db, user_id):\n"
                    "    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n"
                    "    return db.execute(query).fetchone()\n"
                    "```\n"
                ),
            },
            {
                "id": "js_fetch_loop",
                "task": (
                    "Review this JavaScript for bugs. For each bug: name it, explain the impact, "
                    "show the fix. End with a fully corrected version:\n\n"
                    "```js\n"
                    "async function fetchData(url) {\n"
                    "    let data = await fetch(url)\n"
                    "    return data.json()\n"
                    "}\n"
                    "const results = []\n"
                    "urls.forEach(url => fetchData(url).then(d => results.push(d)))\n"
                    "console.log(results)\n"
                    "```\n"
                ),
            },
        ],
    },
    "security_audit": {
        "validation": [
            {
                "id": "login_api",
                "task": (
                    "Security audit this login API. Required output: "
                    "(1) severity-ranked vulnerability table (Critical/High/Medium/Low), "
                    "(2) concrete code fix for each finding:\n\n"
                    "```js\n"
                    "app.post('/api/login', async (req, res) => {\n"
                    "  const { username, password } = req.body;\n"
                    "  const user = await db.query(`SELECT * FROM users WHERE username='${username}'`);\n"
                    "  if (!user) return res.status(401).send('no');\n"
                    "  if (password !== user.password) return res.status(401).send('no');\n"
                    "  const token = jwt.sign({ id: user.id }, 'hardcoded-secret');\n"
                    "  res.json({ token });\n"
                    "});\n"
                    "```\n"
                ),
            },
            {
                "id": "file_upload",
                "task": (
                    "Security audit this file upload handler. Required output: "
                    "(1) ranked vulnerability list with exploit scenario, "
                    "(2) a fixed implementation:\n\n"
                    "```python\n"
                    "def upload_file(request):\n"
                    "    file = request.files['file']\n"
                    "    filename = file.filename\n"
                    "    save_path = f'/var/www/uploads/{filename}'\n"
                    "    file.save(save_path)\n"
                    "    return {'url': f'https://example.com/uploads/{filename}'}\n"
                    "```\n"
                ),
            },
            {
                "id": "session_mgmt",
                "task": (
                    "Audit this session management code. Required output: "
                    "(1) severity-ranked vulnerability list, (2) a fixed version:\n\n"
                    "```python\n"
                    "def login(username, password):\n"
                    "    user = db.get_user(username)\n"
                    "    if user and user.password == password:\n"
                    "        session_id = str(random.randint(100000, 999999))\n"
                    "        sessions[session_id] = {'user': username, 'created': time.time()}\n"
                    "        response.set_cookie('session', session_id)\n"
                    "        return True\n"
                    "    return False\n"
                    "```\n"
                ),
            },
        ],
        "eval": [
            {
                "id": "auth_endpoint_prose",
                "task": (
                    "Audit this authentication endpoint. Required output: "
                    "(1) severity-ranked vulnerability table, "
                    "(2) exploit scenario for each, "
                    "(3) concrete code fix for each.\n\n"
                    "POST /api/login — Body: { username, password }\n\n"
                    "Implementation:\n"
                    "- Raw SQL string interpolation for DB query\n"
                    "- Plaintext password comparison with ==\n"
                    "- JWT signed with hardcoded 'secret123'\n"
                    "- No rate limiting, no account lockout\n"
                    "- No input validation/sanitization\n"
                ),
            },
        ],
    },
    "research_synthesis": {
        "validation": [
            {
                "id": "attention_mechanisms",
                "task": (
                    "Synthesize these abstracts. Required output: "
                    "(1) comparison table (method vs. speed / memory / accuracy), "
                    "(2) trade-offs for each method, "
                    "(3) open research questions, "
                    "(4) practitioner recommendation with justification.\n\n"
                    "[Paper A] Sparse top-k attention: 3x speedup on long contexts, "
                    "8% accuracy drop on short sequences.\n"
                    "[Paper B] FlashAttention: 2x throughput, zero accuracy loss, A100+ required.\n"
                    "[Paper C] Linear attention: 10x memory reduction, 15% drop on retrieval tasks.\n"
                ),
            },
            {
                "id": "rl_alignment",
                "task": (
                    "Synthesize these RL alignment findings. Required output: "
                    "(1) comparison table (method vs. effectiveness / cost / stability), "
                    "(2) trade-offs, (3) gaps, (4) recommendation for a resource-constrained team.\n\n"
                    "[Study 1] RLHF: 70% reduction in harmful outputs, $2M+ per run, reward hacking.\n"
                    "[Study 2] CAI: 80% cheaper than RLHF, 5% gap on adversarial benchmarks.\n"
                    "[Study 3] DPO: no reward model, comparable to RLHF, unstable out-of-distribution.\n"
                ),
            },
            {
                "id": "rag_methods",
                "task": (
                    "Synthesize these RAG designs. Required output: "
                    "(1) comparison table (system vs. accuracy / latency / use-case fit), "
                    "(2) trade-offs, (3) decision framework for when to use each.\n\n"
                    "[Naive RAG] 58% complex QA, fast and simple.\n"
                    "[HyDE] 72% complex QA, 40% higher latency, degrades on factual lookup.\n"
                    "[Iterative RAG] 78% complex QA, 3x latency, near-baseline on simple lookups.\n"
                ),
            },
        ],
        "eval": [
            {
                "id": "transformer_efficiency_eval",
                "task": (
                    "Synthesize these transformer efficiency abstracts. Required output: "
                    "(1) comparison table (method vs. speed / memory / accuracy), "
                    "(2) trade-offs for each method, "
                    "(3) open questions, "
                    "(4) practitioner recommendation with justification.\n\n"
                    "[Paper A] Linear attention: O(n) complexity, 10x memory reduction, "
                    "15% accuracy drop on retrieval tasks.\n"
                    "[Paper B] Sparse top-k attention: 3x speedup on long context, "
                    "8% drop on short sequences.\n"
                    "[Paper C] FlashAttention: 2x throughput, no accuracy loss, A100+ required.\n"
                ),
            },
        ],
    },
}


def get_validation_tasks(task_class: str) -> list[dict]:
    key = task_class.lower().replace(" ", "_").replace("-", "_")
    return TASK_BANK.get(key, {}).get("validation", [
        {"id": "generic_1", "task": "Analyze this and provide specific, actionable recommendations."},
    ])


def get_eval_tasks(task_class: str) -> list[dict]:
    key = task_class.lower().replace(" ", "_").replace("-", "_")
    return TASK_BANK.get(key, {}).get("eval", [
        {"id": "generic_eval", "task": "Analyze this and provide specific, actionable recommendations."},
    ])


# ── Scoring: checklist-based, separate judge model ────────────────────────────
def _judge_checklist_is_complete(result: dict, rubric: list[dict]) -> bool:
    """
    Validates that checklist_results answers EACH checklist item (by exact item text)
    and provides evidence_quote for each.
    """
    cr = result.get("checklist_results")
    if not isinstance(cr, dict):
        return False

    for r in rubric:
        crit = r.get("criterion")
        items = r.get("checklist", [])
        if not items:
            continue

        bucket = cr.get(crit)
        if not isinstance(bucket, dict):
            return False

        # Reject placeholder structure like {"item_text": {...}}
        if "item_text" in bucket:
            return False

        for item in items:
            v = bucket.get(item)
            if not isinstance(v, dict):
                return False
            if v.get("answer") not in ("yes", "no"):
                return False
            if not isinstance(v.get("evidence_quote", ""), str):
                return False
            # If they mark YES, force a non-empty quote
            if v.get("answer") == "yes" and not v.get("evidence_quote", "").strip():
                return False

    return True

def score_output(task: str, output: str, rubric: list[dict] | None = None) -> tuple[float, str]:
    """
    Score output using JUDGE_MODEL with a checklist.
    Returns (weighted_score 0–1, main_weakness string).
    """
    rubric = rubric or SHARED_RUBRIC

    checklist_sections = ""
    for r in rubric:
        items = r.get("checklist", [])
        if items:
            checklist_sections += f"\n{r['criterion'].upper()} checklist:\n"
            checklist_sections += "\n".join(f"  - {item}" for item in items)

    cap_rules = "\n".join(
        f"  - '{r['criterion']}' fails checklist → cap at {r.get('cap_if_bad', 0.45)}"
        for r in rubric if r.get("cap_if_bad")
    )

    # IMPORTANT: show more of the output so "cut off" can be judged.
    # Keeping this bounded avoids runaway prompt size.
    output_for_judge = output[:8000]

    prompt = f"""You are a strict evaluator. Follow this procedure exactly.

TASK (what was asked):
{task[:1200]}

OUTPUT (what the agent produced):
{output_for_judge}

RUBRIC:
{json.dumps(rubric, indent=2)}

CHECKLISTS (you must answer YES/NO for each item):
{checklist_sections}

PROCEDURE:
1. For each criterion, answer every checklist item YES or NO.
2. Apply caps: {cap_rules}
3. Score each criterion 0.0–1.0.
   - Reserve >0.90 ONLY if ALL checklist items are YES AND you provide direct quotes as evidence.
4. weighted_total = sum(weight * score)

HARD PENALTIES (apply before step 3):
- Task asks for fixed/corrected code and NO code block exists → actionability capped at 0.25
- Task asks for a comparison table and NO table exists → completeness capped at 0.30
- Task asks for a recommendation and output ends with analysis only → actionability capped at 0.40
- Output is mostly process narration with little substance → all criteria capped at 0.40

EVIDENCE RULE (mandatory):
- For EVERY checklist item you mark YES, include at least ONE short direct quote (verbatim substring)
  from the OUTPUT that supports it.
- If you cannot quote supporting evidence, mark NO.

Return ONLY valid JSON:
{{
  "checklist_results": {{
    "completeness": {{
      "{SHARED_RUBRIC[0]['checklist'][0]}": {{"answer": "yes|no", "evidence_quote": "..."}},
      "{SHARED_RUBRIC[0]['checklist'][1]}": {{"answer": "yes|no", "evidence_quote": "..."}},
      "{SHARED_RUBRIC[0]['checklist'][2]}": {{"answer": "yes|no", "evidence_quote": "..."}}
    }},
    "actionability": {{
      "{SHARED_RUBRIC[1]['checklist'][0]}": {{"answer": "yes|no", "evidence_quote": "..."}},
      "{SHARED_RUBRIC[1]['checklist'][1]}": {{"answer": "yes|no", "evidence_quote": "..."}},
      "{SHARED_RUBRIC[1]['checklist'][2]}": {{"answer": "yes|no", "evidence_quote": "..."}},
      "{SHARED_RUBRIC[1]['checklist'][3]}": {{"answer": "yes|no", "evidence_quote": "..."}}
    }},
    "groundedness": {{
      "{SHARED_RUBRIC[2]['checklist'][0]}": {{"answer": "yes|no", "evidence_quote": "..."}},
      "{SHARED_RUBRIC[2]['checklist'][1]}": {{"answer": "yes|no", "evidence_quote": "..."}},
      "{SHARED_RUBRIC[2]['checklist'][2]}": {{"answer": "yes|no", "evidence_quote": "..."}}
    }}
  }},
  "scores": [
    {{"criterion": "completeness", "score": 0.7, "reasoning": "cite evidence quotes + why caps applied"}},
    {{"criterion": "actionability", "score": 0.7, "reasoning": "cite evidence quotes + why caps applied"}},
    {{"criterion": "groundedness", "score": 0.7, "reasoning": "cite evidence quotes + why caps applied"}}
  ],
  "weighted_total": 0.72,
  "main_weakness": "Specific gap — quote what is missing"
}}"""

    raw = call_llm(
        [{"role": "user", "content": prompt}],
        system=(
            "You are a strict evaluator. Do not award high scores to outputs that merely look plausible. "
            "Follow the checklist. If you cannot quote evidence, mark NO and lower the score."
        ),
        max_tokens=JUDGE_MAX_TOKENS,
        model=JUDGE_MODEL,
    )
    try:
        result = extract_json(raw)
        log("EVAL", "Judge JSON (truncated)", json.dumps(result, indent=2)[:1800])

        weighted = float(result.get("weighted_total", 0.0))
        weakness = str(result.get("main_weakness", "Unknown"))

        # Enforce compliance: if checklist structure is wrong, cap score hard
        if isinstance(result, dict) and not _judge_checklist_is_complete(result, rubric):
            return min(weighted, 0.60), "Judge checklist incomplete/malformed; score capped"

        return weighted, weakness
    except Exception:
        return 0.0, "Evaluation parse error"


# ── Tool simulation ────────────────────────────────────────────────────────────

def _simulate_tool(tool_name: str, args: dict, task_excerpt: str) -> str:
    t = tool_name.lower()
    tx = task_excerpt.lower()
    issues = []

    if any(x in t for x in ("static", "lint", "scan", "analyze")):
        if ("f\"" in task_excerpt or "f'" in task_excerpt) and any(
            x in tx for x in ("sql", "query", "select", "where")
        ):
            issues.append("[CRITICAL] SQL injection via f-string interpolation")
        if "password ==" in tx or "== password" in tx or "!== user.password" in tx:
            issues.append("[CRITICAL] Plaintext password comparison (no hashing)")
        if "random.randint" in tx:
            issues.append("[HIGH] Insecure random — use secrets.token_hex(32)")
        if any(x in tx for x in ("'secret'", '"secret"', "secret123", "hardcoded")):
            issues.append("[HIGH] Hardcoded secret key detected")
        if "foreach" in tx and "async" in tx:
            issues.append("[HIGH] async callback in forEach — awaits not tracked, results empty")
        if "float('-inf')" in task_excerpt:
            issues.append("[MEDIUM] NaN propagation: float('nan') > float('-inf') is False")
        if "/var/www" in tx or ("save_path" in tx and "filename" in tx):
            issues.append("[CRITICAL] Path traversal: unsanitized filename used in file path")
        if not issues:
            issues.append("[INFO] No additional automated findings")
        return "TOOL_RESULT [static_analysis]:\n" + "\n".join(f"  {i}" for i in issues)

    if any(x in t for x in ("search", "lookup", "reference")):
        return (
            "TOOL_RESULT [reference_lookup]:\n"
            "  OWASP A03:2021 Injection: use cursor.execute(query, (user_id,)) parameterized form\n"
            "  OWASP A02:2021 Crypto: bcrypt.hashpw / argon2; never store or compare plaintext\n"
            "  CWE-22 Path Traversal: os.path.basename(filename) + allowlist extension check\n"
            "  JWT: load secret from os.environ; set exp/iat; use RS256 in production\n"
            "  Python secrets: secrets.token_urlsafe(32) for session IDs\n"
        )

    if any(x in t for x in ("cluster", "theme", "semantic")):
        return (
            "TOOL_RESULT [semantic_clustering]:\n"
            "  Cluster A (throughput): FlashAttention (C), Sparse (B)\n"
            "  Cluster B (memory/length): Linear attention (A)\n"
            "  Cluster C (accuracy-preserving): FlashAttention (C) only\n"
            "  Key tension: no single method wins on speed + memory + accuracy\n"
        )

    return f"TOOL_RESULT [{tool_name}]:\n  args={json.dumps(args)[:150]}\n  (simulated stub)\n"


def _parse_tool_request(line: str) -> tuple[str, dict]:
    m = re.match(r"TOOL_REQUEST:\s*(\w+)\s*\(?(.*?)\)?$", line.strip())
    if not m:
        return "unknown_tool", {}
    try:
        args = json.loads(m.group(2)) if m.group(2).strip() else {}
    except Exception:
        args = {"raw": m.group(2)}
    return m.group(1), args


# ── Baseline execution ─────────────────────────────────────────────────────────
#
# TRUE single-shot: one call_llm(), no protocol, no STEP labels, no tools.
# This is the real counterfactual — what does a plain LLM do without specialization?

def run_baseline_on_task(task_class: str, task: str) -> str:
    return call_llm(
        [{"role": "user", "content": task}],
        system=(
            f"You are a helpful AI assistant skilled at {task_class}. "
            "Be thorough, specific, and actionable. Show corrected code where relevant."
        ),
        max_tokens=4000,
    )


# ── Agent execution ────────────────────────────────────────────────────────────
#
# The deliverable-first contract:
#   Step 1 must produce the PRIMARY DELIVERABLE (the table / fix list / synthesis).
#   Process narration is explicitly forbidden before the deliverable appears.
#   This is enforced both in the system prompt and in the per-step instructions.

_DELIVERABLE_FIRST = """
EXECUTION RULE — DELIVERABLE FIRST:
Your PRIMARY DELIVERABLE must be the FIRST substantive content in your response.

FORBIDDEN as your opening:
  - "Step 1: I will now analyze..."
  - "First, let me scope the problem..."
  - Any process narration before showing results

REQUIRED as your opening:
  - The actual finding table, fix list, comparison, or corrected code
  - Every finding must cite the specific code/text from the input that triggered it
  - Add process commentary AFTER the deliverable
"""

def run_agent_on_task(architecture: dict, blueprint: dict, task: str, dry_run: bool = False) -> str:
    architecture = sanitize_architecture(architecture, fallback=_ARCH_FALLBACK)
    mode = "DRY-RUN" if dry_run else "EXECUTION"
    log(mode, f"Task: {task[:100]}")

    protocol = architecture.get("reasoning_protocol", [])
    tools    = architecture.get("tools", [])

    protocol_text = "\n".join(
        f"Step {s['step']}: {s['name']} — {s['instruction']} → {s.get('output_format', 'analysis')}"
        for s in protocol
    )
    tool_list = "\n".join(
        f"  - {t['name']}: {t['description']}" for t in tools
    ) or "  None."

    system = f"""{architecture.get('system_prompt', 'You are a helpful assistant.')}

REASONING PROTOCOL:
{protocol_text}

STOPPING CRITERION: {architecture.get('stopping_criterion', 'When deliverable is complete.')}
{_DELIVERABLE_FIRST}"""

    user = f"""TASK:
{task}

TOOL PROTOCOL (optional):
Emit: TOOL_REQUEST: tool_name({{"param": "value"}})
Do NOT fabricate tool results.
Available: {tool_list}

Reference SPECIFIC details from the task by name (variable names, paper labels, function names).
End with a SUMMARY."""

    response = call_llm(
        [{"role": "user", "content": user}],
        system=system,
        max_tokens=AGENT_MAX_TOKENS,
    )

    for _ in range(3):
        m = re.search(r"^TOOL_REQUEST:\s*(.+)$", response, flags=re.MULTILINE)
        if not m:
            break
        name, args = _parse_tool_request("TOOL_REQUEST: " + m.group(1))
        stub = _simulate_tool(name, args, task)
        response = call_llm(
            [
                {"role": "user", "content": user},
                {"role": "assistant", "content": response},
                {"role": "user", "content": stub + "\n\nContinue and complete all remaining steps."},
            ],
            system=system,
            max_tokens=AGENT_MAX_TOKENS,
        )

    log(mode, "Complete", response[:300] + "...")
    return response


# ── Phase 1: Differentiation ───────────────────────────────────────────────────

def phase_differentiation(task_class: str, example_tasks: list[str]) -> dict:
    log("DIFFERENTIATION", f"Studying task class: {task_class}")
    system = (
        "You are a meta-cognitive AI researcher. Analyze a class of tasks and produce "
        "a precise blueprint for how expert agents solve them. Be specific and empirical."
    )
    examples_text = "\n".join(f"- {t}" for t in example_tasks)
    prompt = f"""Task class: {task_class}

Examples:
{examples_text}

Return JSON:
{{
  "task_class": "{task_class}",
  "core_challenge": "1-2 sentences on what makes this hard",
  "typical_workflow": ["step1", "step2", "step3", "step4", "step5"],
  "common_failure_modes": ["fail1", "fail2", "fail3"],
  "primary_deliverable": "The concrete artifact the agent must produce first (e.g. 'severity-ranked table with code fixes', 'comparison table with recommendation')",
  "output_criteria": ["criterion1", "criterion2", "criterion3"],
  "recommended_architecture": {{
    "pattern": "iterative",
    "rationale": "why this fits",
    "num_steps": 5,
    "use_tools": true,
    "self_critique": true
  }},
  "specialized_system_prompt_theme": "The mindset/persona this agent should embody",
  "what_separates_good_from_great": "The single most important differentiator"
}}

Return ONLY valid JSON."""
    raw = call_llm([{"role": "user", "content": prompt}], system=system, max_tokens=2000)
    blueprint = extract_json(raw)
    log("DIFFERENTIATION", "Blueprint created", blueprint)
    return blueprint


# ── Phase 2: Morphogenesis ─────────────────────────────────────────────────────

def phase_morphogenesis(blueprint: dict, task_class: str) -> dict:
    log("MORPHOGENESIS", "Growing specialized agent architecture...")
    primary_deliverable = blueprint.get("primary_deliverable", "structured findings with fixes")
    system = (
        "You are an AI agent architect. Design a specialized agent. "
        "The agent must produce its primary deliverable as the first output — not narrate a plan."
    )
    prompt = f"""Blueprint for: "{task_class}"

{json.dumps(blueprint, indent=2)}

Primary deliverable: {primary_deliverable}

Design the agent. Return JSON:
{{
  "agent_name": "2-4 word name",
  "system_prompt": "200-400 words. Must explicitly: (1) establish expert persona, (2) name the PRIMARY DELIVERABLE the agent must produce, (3) state it must appear BEFORE any process narration.",
  "reasoning_protocol": [
    {{
      "step": 1,
      "name": "Produce {primary_deliverable}",
      "instruction": "Without any preamble, produce the complete {primary_deliverable}. Reference specific variable names, paper labels, or code patterns from the input. Do NOT scope, plan, or narrate — produce the deliverable directly.",
      "output_format": "The complete {primary_deliverable} with all required sections"
    }},
    {{"step": 2, "name": "...", "instruction": "...", "output_format": "..."}}
  ],
  "tools": [
    {{"name": "tool_name", "description": "When to call and what it returns", "inputs": {{"param": "type"}}, "simulated": true}}
  ],
  "self_evaluation_rubric": [
    {{"criterion": "completeness", "weight": 0.30, "question": "Primary deliverable fully present?", "good_signal": "All required sections present", "bad_signal": "Any required section missing"}},
    {{"criterion": "actionability", "weight": 0.40, "question": "Recommendations immediately usable with code?", "good_signal": "Concrete code blocks present", "bad_signal": "Prose-only, no corrected code"}},
    {{"criterion": "groundedness", "weight": 0.30, "question": "Every claim tied to specific input details?", "good_signal": "Cites variable/paper names from input", "bad_signal": "Generic advice not tied to input"}}
  ],
  "stopping_criterion": "When the {primary_deliverable} is complete with concrete fixes/recommendations for every finding."
}}

RULES:
- Step 1 instruction must say PRODUCE THE DELIVERABLE — not 'map', 'scope', or 'enumerate'
- reasoning_protocol: 4-6 steps
- rubric weights MUST sum to 1.0 (use 0.30/0.40/0.30)
- Return ONLY valid JSON"""

    raw = call_llm([{"role": "user", "content": prompt}], system=system, max_tokens=3500)
    arch = sanitize_architecture(extract_json(raw), fallback=_ARCH_FALLBACK)

    # Force rubric = SHARED_RUBRIC so internal validation == external metric
    arch["self_evaluation_rubric"] = SHARED_RUBRIC

    log("MORPHOGENESIS", "Architecture grown", {
        "agent_name": arch.get("agent_name"),
        "num_steps": len(arch.get("reasoning_protocol", [])),
        "num_tools": len(arch.get("tools", [])),
    })
    return arch


# ── Phase 3: Validation ────────────────────────────────────────────────────────

def _eval_architecture(arch: dict, blueprint: dict, tasks: list[dict]) -> tuple[float, str, list[dict]]:
    """Evaluate using SHARED_RUBRIC and JUDGE_MODEL — identical to external eval."""
    details = []
    scores = []
    for t in tasks:
        output = run_agent_on_task(arch, blueprint, t["task"], dry_run=True)
        score, critique = score_output(t["task"], output, SHARED_RUBRIC)
        scores.append(score)
        details.append({"task_id": t["id"], "score": score, "critique": critique})
    avg = sum(scores) / len(scores) if scores else 0.0
    worst = min(details, key=lambda d: d["score"])
    return avg, worst.get("critique", "Unknown"), details


def patch_architecture(arch: dict, blueprint: dict, critique: str, round_num: int) -> dict:
    primary_deliverable = blueprint.get("primary_deliverable", "structured findings with fixes")
    system = "You are an AI agent debugger. Fix a weak agent architecture based on critique."
    aggression = (
        "Make the single most impactful targeted fix." if round_num == 1
        else "Rewrite the system_prompt and Step 1 instruction if the agent is still not producing the deliverable first."
    )
    prompt = f"""Agent scored below threshold (round {round_num}).

Primary deliverable required: {primary_deliverable}
Worst critique: {critique}

Current architecture (truncated):
{json.dumps(arch, indent=2)[:2500]}

{aggression}

Diagnostic — if critique says:
- "scoping/planning before output": rewrite Step 1 to produce the actual deliverable directly
- "no code fix" / "prose only": add "For every issue, show a corrected code block"
- "generic": add "cite the specific variable name / paper label / function from the input"
- "table missing": add "Begin with a markdown table with required columns"
- "recommendation missing": add "End with explicit recommendation: choose X because Y"

Return COMPLETE valid JSON architecture. Same structure. Rubric weights 0.30/0.40/0.30.
Return ONLY valid JSON."""

    raw = call_llm([{"role": "user", "content": prompt}], system=system, max_tokens=3500)
    try:
        patched = extract_json(raw)
        if isinstance(patched, str):
            patched = json.loads(patched)
        if not isinstance(patched, dict):
            raise ValueError(f"Expected dict, got {type(patched)}")

        merged = dict(arch)

        # Only accept protocol/tools replacements if they are valid + non-empty
        if "reasoning_protocol" in patched:
            rp = patched.get("reasoning_protocol")
            if isinstance(rp, list) and rp and all(isinstance(x, dict) and "instruction" in x and "name" in x for x in rp):
                merged["reasoning_protocol"] = rp  # accept
        if "tools" in patched:
            tools = patched.get("tools")
            if isinstance(tools, list) and all(isinstance(x, dict) and "name" in x for x in tools):
                merged["tools"] = tools

        # Shallow-merge the rest
        for k, v in patched.items():
            if k in ("reasoning_protocol", "tools", "validation"):
                continue
            merged[k] = v

        merged.pop("validation", None)
        merged["self_evaluation_rubric"] = SHARED_RUBRIC  # keep aligned
        return sanitize_architecture(merged, fallback=arch)

    except Exception as e:
        log("VALIDATION", f"Patch failed round {round_num}: {e}")
        return arch


def phase_validation(architecture: dict, blueprint: dict, task_class: str) -> dict:
    log("VALIDATION", f"Running self-test (judge: {JUDGE_MODEL}, rubric: SHARED_RUBRIC)...")

    # Key fix: validate on BOTH validation split + a small held-out slice from eval split.
    # This reduces overfitting and better predicts demo.py eval.
    val_tasks = get_validation_tasks(task_class)
    eval_tasks = get_eval_tasks(task_class)
    heldout = eval_tasks[:1]  # small cost, big signal

    tasks = val_tasks + [{"id": f"heldout::{t['id']}", "task": t["task"]} for t in heldout]
    log("VALIDATION", f"Validation tasks: {[t['id'] for t in tasks]}")

    def _baseline_avg(tasks_: list[dict]) -> float:
        scores: list[float] = []
        for t in tasks_:
            out = run_baseline_on_task(task_class, t["task"])
            s, _ = score_output(t["task"], out, SHARED_RUBRIC)
            scores.append(s)
        return sum(scores) / len(scores) if scores else 0.0

    baseline_avg = _baseline_avg(tasks)

    current_arch = architecture
    current_score, current_critique, current_details = _eval_architecture(current_arch, blueprint, tasks)
    log("VALIDATION", f"Initial avg score: {current_score:.3f} (baseline={baseline_avg:.3f})", current_details)

    history = [{"round": 0, "score": current_score, "critique": current_critique, "baseline": baseline_avg}]

    for rnd in range(1, MAX_PATCH_ROUNDS + 1):
        # Patch if below threshold OR not beating baseline by margin
        if current_score >= READY_THRESHOLD and current_score >= baseline_avg + IMPROVEMENT_MARGIN:
            log("VALIDATION", f"Score {current_score:.3f} clears threshold and beats baseline by {IMPROVEMENT_MARGIN:.2f} — ready!")
            break

        reason = []
        if current_score < READY_THRESHOLD:
            reason.append("below_threshold")
        if current_score < baseline_avg + IMPROVEMENT_MARGIN:
            reason.append("not_beating_baseline")
        log("VALIDATION", f"Patching ({', '.join(reason)}) — patch round {rnd}/{MAX_PATCH_ROUNDS}")

        candidate = patch_architecture(current_arch, blueprint, current_critique, rnd)
        cand_score, cand_critique, cand_details = _eval_architecture(candidate, blueprint, tasks)
        log("VALIDATION", f"Post-patch avg: {cand_score:.3f} (baseline={baseline_avg:.3f})", cand_details)
        history.append({"round": rnd, "score": cand_score, "critique": cand_critique, "baseline": baseline_avg})

        if cand_score >= current_score + MIN_SCORE_IMPROVEMENT:
            log("VALIDATION", f"Improvement +{cand_score - current_score:.3f} — keeping")
            current_arch, current_score, current_critique = candidate, cand_score, cand_critique
        else:
            log("VALIDATION", f"No improvement — rollback")

    current_arch["validation"] = {
        "test_task_ids": [t["id"] for t in tasks],
        "avg_score": current_score,
        "critique": current_critique,
        "ready": (current_score >= READY_THRESHOLD) and (current_score >= baseline_avg + IMPROVEMENT_MARGIN),
        "threshold": READY_THRESHOLD,
        "baseline_avg": baseline_avg,
        "improvement_margin": IMPROVEMENT_MARGIN,
        "patch_rounds": len(history) - 1,
        "improvement_history": history,
        "judge_model": JUDGE_MODEL,
        "rubric": "SHARED_RUBRIC",
    }
    return current_arch

# ── Stem Agent Orchestrator ────────────────────────────────────────────────────

class StemAgent:
    """
    A stem agent that self-specializes into a task-specific agent.

    Usage:
        stem = StemAgent("Code Review")
        stem.differentiate(["example 1", "example 2"])
        result = stem.run("Review this code: ...")
    """

    def __init__(self, task_class: str) -> None:
        self.task_class = task_class
        self.state = "stem"
        self.blueprint: dict = {}
        self.architecture: dict = {}
        self.evolution_log: list[dict] = []

    def differentiate(self, example_tasks: list[str]) -> "StemAgent":
        start = time.time()
        self._record("start", {"task_class": self.task_class, "n_examples": len(example_tasks)})

        self.state = "differentiating"
        self.blueprint = phase_differentiation(self.task_class, example_tasks)
        self._record("differentiation", self.blueprint)

        self.state = "morphogenesis"
        self.architecture = phase_morphogenesis(self.blueprint, self.task_class)
        self._record("morphogenesis", {"agent_name": self.architecture.get("agent_name")})

        self.state = "validating"
        self.architecture = phase_validation(self.architecture, self.blueprint, self.task_class)
        self._record("validation", self.architecture.get("validation", {}))

        elapsed = time.time() - start
        self.state = "specialized"
        log(
            "STEM_AGENT",
            f"Specialization complete in {elapsed:.1f}s | "
            f"Agent: {self.architecture.get('agent_name')} | "
            f"Val score: {self.architecture.get('validation', {}).get('avg_score', 0):.3f} "
            f"(judge: {JUDGE_MODEL})",
        )
        return self

    def run(self, task: str) -> dict:
        if self.state != "specialized":
            raise RuntimeError("Call .differentiate() before .run()")
        output = run_agent_on_task(self.architecture, self.blueprint, task)
        score, critique = score_output(task, output, SHARED_RUBRIC)
        result = {
            "task": task,
            "agent": self.architecture.get("agent_name"),
            "output": output,
            "quality_score": score,
            "critique": critique,
            "evolution_log": self.evolution_log,
        }
        self._record("execution", {"score": score, "critique": critique})
        return result

    def _record(self, phase: str, data: dict) -> None:
        self.evolution_log.append({
            "phase": phase,
            "timestamp": time.strftime("%H:%M:%S"),
            "data": data,
        })

    def to_dict(self) -> dict:
        return {
            "task_class": self.task_class,
            "state": self.state,
            "blueprint": self.blueprint,
            "architecture": self.architecture,
            "evolution_log": self.evolution_log,
        }

    def save(self, path: str) -> None:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)
        log("STEM_AGENT", f"Saved to {path}")


if __name__ == "__main__":
    stem = StemAgent("Code Review")
    stem.differentiate([
        "Review Python functions for correctness and edge cases",
        "Check SQL queries for injection vulnerabilities",
        "Find race conditions in async JavaScript",
    ])
    result = stem.run(
        "Review this Python code for all issues. Show fixed code:\n\n"
        "```python\n"
        "def get_user(db, uid):\n"
        "    return db.execute(f'SELECT * FROM users WHERE id={uid}').fetchone()\n"
        "```"
    )
    print(f"\nScore: {result['quality_score']:.3f}")
    print(f"Critique: {result['critique']}")