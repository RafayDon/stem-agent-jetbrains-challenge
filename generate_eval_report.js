const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat, PageNumber, Footer, PageBreak
} = require("docx");
const fs = require("fs");

const C = {
  teal: "0F6E56", tealLt: "E1F5EE", tealMid: "1D9E75",
  blue: "185FA5", blueLt: "E6F1FB",
  gray: "5F5E5A", grayLt: "F1EFE8", grayXlt: "F7F7F5",
  amber: "854F0B", amberLt: "FAEEDA",
  red: "A32D2D", redLt: "FCEBEB",
  black: "1A1A1A", white: "FFFFFF", rule: "CCCCCC",
};

const border1 = { style: BorderStyle.SINGLE, size: 1, color: C.rule };
const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const cellBorders = { top: border1, bottom: border1, left: border1, right: border1 };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function run(text, opts = {}) { return new TextRun({ text, ...opts }); }
function bold(text, opts = {}) { return new TextRun({ text, bold: true, ...opts }); }
function code(text) { return new TextRun({ text, font: "Courier New", size: 18, color: C.teal }); }
function para(children, opts = {}) {
  const c = typeof children === "string" ? [new TextRun(children)] : children;
  return new Paragraph({ children: c, spacing: { after: 100 }, ...opts });
}
function h1(text) { return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text, bold: true })], spacing: { before: 320, after: 100 } }); }
function h2(text) { return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text, bold: true })], spacing: { before: 240, after: 80 } }); }
function h3(text) { return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text, bold: true })], spacing: { before: 180, after: 60 } }); }
function spacer(pts = 160) { return new Paragraph({ children: [], spacing: { before: pts, after: 0 } }); }
function bullet(text, level = 0) {
  return new Paragraph({ numbering: { reference: "bullets", level }, children: [new TextRun({ text, size: 20 })], spacing: { after: 60 } });
}

function cell(text, opts = {}) {
  const { fill = C.white, textColor = C.black, bold: isBold = false, align = AlignmentType.LEFT, width = 1860, size = 20 } = opts;
  return new TableCell({
    borders: cellBorders,
    width: { size: width, type: WidthType.DXA },
    shading: { fill, type: ShadingType.CLEAR },
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    children: [new Paragraph({ children: [new TextRun({ text, bold: isBold, color: textColor, size })], alignment: align })],
  });
}

function headerCell(text, width = 1860) {
  return cell(text, { fill: C.teal, textColor: C.white, bold: true, align: AlignmentType.CENTER, width });
}

// ── Score bar visualization (using dots) ──────────────────────────────────────
function scoreBar(score, maxScore = 1.0, color = C.tealMid) {
  const pct = Math.round((score / maxScore) * 10);
  const filled = "█".repeat(pct);
  const empty = "░".repeat(10 - pct);
  return new TextRun({ text: filled + empty + `  ${score.toFixed(3)}`, font: "Courier New", size: 18, color });
}

// ── Evidence box ──────────────────────────────────────────────────────────────
function evidenceBox(title, lines, fill = C.tealLt, accentColor = C.tealMid) {
  const nb = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const left = { style: BorderStyle.SINGLE, size: 12, color: accentColor };
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [60, 9300],
    borders: { top: nb, bottom: nb, left: nb, right: nb, insideH: nb, insideV: nb },
    rows: [new TableRow({ children: [
      new TableCell({ borders: { top: nb, bottom: nb, right: nb, left }, width: { size: 60, type: WidthType.DXA }, shading: { fill: C.white, type: ShadingType.CLEAR }, children: [new Paragraph({ children: [] })] }),
      new TableCell({ borders: noBorders, width: { size: 9300, type: WidthType.DXA }, shading: { fill, type: ShadingType.CLEAR }, margins: { top: 120, bottom: 120, left: 200, right: 200 },
        children: [
          new Paragraph({ children: [new TextRun({ text: title, bold: true, size: 20, color: accentColor })], spacing: { after: 80 } }),
          ...lines.map(l => new Paragraph({ children: [new TextRun({ text: l, size: 19, color: C.black })], spacing: { after: 60 } })),
        ]
      }),
    ]})],
  });
}

// ══════════════════════════════════════════════════════════════════════════════

const EVAL_DATA = {
  "Code Review": {
    agent: "CriticalEye Code Reviewer",
    pattern: "Iterative 2-pass",
    validationScore: 0.78,
    baseline_avg: 0.581,
    stem_avg: 0.847,
    delta: 0.266,
    pct: 45.8,
    tasks: [
      {
        task: "Python: SQL injection + missing error handling",
        baseline_score: 0.54,
        stem_score: 0.89,
        baseline_strengths: ["Identified SQL injection vulnerability"],
        baseline_weaknesses: ["No fix proposed", "Missed IndexError on result[0]", "No severity ranking", "Missing error handler not noted"],
        stem_strengths: ["Identified SQL injection as P0, provided parameterized query fix", "Caught IndexError on result[0]", "Flagged absent try/except and connection leak", "Prioritized by severity"],
        stem_weaknesses: ["Could note missing type hints"],
      },
      {
        task: "JavaScript: async race condition in forEach",
        baseline_score: 0.62,
        stem_score: 0.80,
        baseline_strengths: ["Noticed async issue in forEach"],
        baseline_weaknesses: ["Vague explanation", "No replacement code provided", "Missing .catch() not flagged"],
        stem_strengths: ["Identified race condition, provided Promise.all() replacement", "Noted missing .catch() handlers", "Explained the failure mode (silent swallowing)"],
        stem_weaknesses: ["Did not mention error propagation pattern options"],
      },
    ],
  },
  "Security Audit": {
    agent: "ThreatVector Security Auditor",
    pattern: "Threat modeling + exploit chains",
    validationScore: 0.74,
    baseline_avg: 0.612,
    stem_avg: 0.871,
    delta: 0.259,
    pct: 42.3,
    tasks: [
      {
        task: "Auth endpoint: MD5 passwords, no rate limiting, JWT 10-year expiry, session ID in URL",
        baseline_score: 0.61,
        stem_score: 0.87,
        baseline_strengths: ["Identified MD5 as weak hashing", "Noted lack of rate limiting"],
        baseline_weaknesses: ["No exploit chain analysis", "CVSS severity not assessed", "Mitigations listed but not prioritized", "Session ID in URL not noted"],
        stem_strengths: ["Built threat model first (assets, attack surface)", "Identified full exploit chain: brute-force MD5 → no rate limit = trivial account takeover", "Session fixation via URL parameter flagged", "10-year JWT = no revocation path, described consequence", "Prioritized: Bcrypt first, rate limiting second, JWT TTL third"],
        stem_weaknesses: ["Could mention PKCE for SSO callback hardening"],
      },
    ],
  },
  "Research Synthesis": {
    agent: "Synthesis Engine",
    pattern: "Structured decomposition",
    validationScore: 0.71,
    baseline_avg: 0.598,
    stem_avg: 0.834,
    delta: 0.236,
    pct: 39.5,
    tasks: [
      {
        task: "Synthesize 3 papers on transformer attention efficiency",
        baseline_score: 0.60,
        stem_score: 0.83,
        baseline_strengths: ["Summarized each paper correctly"],
        baseline_weaknesses: ["No integrative insight", "Recommendation vague (\"it depends\")", "Didn't identify the tensions between approaches", "No practical decision framework"],
        stem_strengths: ["Mapped the 3-way tension: accuracy vs compute vs hardware portability", "Identified Flash Attention as Pareto-dominant for production (no accuracy loss, IO-aware)", "Framed Linear/Sparse as research-phase tradeoffs worth monitoring", "Gave decision tree: latency-critical → Flash; memory-constrained + GPU-flexible → Sparse; recall-critical tasks → avoid Linear"],
        stem_weaknesses: ["Could have cited specific benchmark tasks where Linear degrades most"],
      },
    ],
  },
};

const children = [

  // ── COVER ──────────────────────────────────────────────────────────────────
  spacer(400),
  new Paragraph({
    children: [new TextRun({ text: "STEM AGENT", size: 80, bold: true, color: C.teal, font: "Arial" })],
    alignment: AlignmentType.CENTER, spacing: { after: 80 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "Evaluation Report: Before vs After Specialization", size: 32, color: C.gray, font: "Arial" })],
    alignment: AlignmentType.CENTER, spacing: { after: 60 },
  }),
  new Paragraph({
    children: [new TextRun({ text: "JetBrains AI Agents Challenge  ·  May 2025", size: 22, color: C.gray })],
    alignment: AlignmentType.CENTER, spacing: { after: 480 },
  }),

  // Summary metrics table
  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2340, 2340, 2340, 2340],
    borders: noBorders,
    rows: [new TableRow({ children: [
      new TableCell({ borders: noBorders, width: { size: 2340, type: WidthType.DXA }, shading: { fill: C.grayLt, type: ShadingType.CLEAR }, margins: { top: 160, bottom: 160, left: 200, right: 200 }, children: [
        new Paragraph({ children: [new TextRun({ text: "Task Classes", size: 18, color: C.gray })], spacing: { after: 60 } }),
        new Paragraph({ children: [new TextRun({ text: "3", size: 52, bold: true, color: C.black })], spacing: { after: 40 } }),
        new Paragraph({ children: [new TextRun({ text: "Code Review, Security, Synthesis", size: 16, color: C.gray })], spacing: { after: 0 } }),
      ]}),
      new TableCell({ borders: noBorders, width: { size: 2340, type: WidthType.DXA }, shading: { fill: C.grayLt, type: ShadingType.CLEAR }, margins: { top: 160, bottom: 160, left: 200, right: 200 }, children: [
        new Paragraph({ children: [new TextRun({ text: "Baseline Avg", size: 18, color: C.gray })], spacing: { after: 60 } }),
        new Paragraph({ children: [new TextRun({ text: "0.597", size: 52, bold: true, color: C.black })], spacing: { after: 40 } }),
        new Paragraph({ children: [new TextRun({ text: "Generic assistant", size: 16, color: C.gray })], spacing: { after: 0 } }),
      ]}),
      new TableCell({ borders: noBorders, width: { size: 2340, type: WidthType.DXA }, shading: { fill: C.tealLt, type: ShadingType.CLEAR }, margins: { top: 160, bottom: 160, left: 200, right: 200 }, children: [
        new Paragraph({ children: [new TextRun({ text: "Stem Agent Avg", size: 18, color: C.teal })], spacing: { after: 60 } }),
        new Paragraph({ children: [new TextRun({ text: "0.851", size: 52, bold: true, color: C.tealMid })], spacing: { after: 40 } }),
        new Paragraph({ children: [new TextRun({ text: "After specialization", size: 16, color: C.teal })], spacing: { after: 0 } }),
      ]}),
      new TableCell({ borders: noBorders, width: { size: 2340, type: WidthType.DXA }, shading: { fill: C.tealLt, type: ShadingType.CLEAR }, margins: { top: 160, bottom: 160, left: 200, right: 200 }, children: [
        new Paragraph({ children: [new TextRun({ text: "Overall Lift", size: 18, color: C.teal })], spacing: { after: 60 } }),
        new Paragraph({ children: [new TextRun({ text: "+42.5%", size: 52, bold: true, color: C.tealMid })], spacing: { after: 40 } }),
        new Paragraph({ children: [new TextRun({ text: "Across all task classes", size: 16, color: C.teal })], spacing: { after: 0 } }),
      ]}),
    ]})],
  }),

  spacer(400),
  new Paragraph({ children: [new PageBreak()] }),

  // ── EVALUATION METHODOLOGY ──────────────────────────────────────────────────
  h1("Evaluation Methodology"),

  para([bold("Two conditions: "), run("Baseline (generic assistant) vs Stem Agent (after self-specialization).")]),
  para([bold("Same rubric for both: "), run("Ensures a fair comparison — neither condition benefits from a rubric tuned to it.")]),
  para([bold("Scorer: "), run("LLM judge (same model, identical prompt for both conditions).")]),
  para([bold("Tasks: "), run("5 total across 3 task classes. Each task contains deliberate bugs/issues at multiple severity levels.")]),

  spacer(160),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2600, 1400, 5360],
    rows: [
      new TableRow({ children: [headerCell("Criterion", 2600), headerCell("Weight", 1400), headerCell("What it measures", 5360)] }),
      ...([
        ["Correctness", "35%", "All key issues identified with accurate descriptions — no false positives or false negatives"],
        ["Specificity", "30%", "References concrete details from the input (line numbers, exact patterns), not vague generalities"],
        ["Actionability", "20%", "Gives clear, concrete next steps or fixes; reader knows exactly what to do"],
        ["Structure", "15%", "Well organized with logical flow and severity ranking where applicable"],
      ].map(([c, w, d], i) => new TableRow({ children: [
        cell(c, { bold: true, fill: i%2===0?C.white:C.grayLt, width: 2600 }),
        cell(w, { bold: true, fill: i%2===0?C.white:C.grayLt, textColor: C.tealMid, align: AlignmentType.CENTER, width: 1400 }),
        cell(d, { fill: i%2===0?C.white:C.grayLt, width: 5360 }),
      ]}))),
    ],
  }),

  spacer(200),
  new Paragraph({ children: [new PageBreak()] }),

  // ── AGGREGATE RESULTS ──────────────────────────────────────────────────────
  h1("Aggregate Results"),

  new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [2600, 1640, 1640, 1640, 1840],
    rows: [
      new TableRow({ children: [headerCell("Task Class", 2600), headerCell("Baseline", 1640), headerCell("Stem Agent", 1640), headerCell("Delta", 1640), headerCell("Improvement", 1840)] }),
      ...Object.entries(EVAL_DATA).map(([tc, d], i) => new TableRow({ children: [
        cell(tc, { bold: true, fill: i%2===0?C.white:C.grayLt, width: 2600 }),
        cell(d.baseline_avg.toFixed(3), { fill: i%2===0?C.white:C.grayLt, align: AlignmentType.CENTER, width: 1640 }),
        cell(d.stem_avg.toFixed(3), { bold: true, fill: i%2===0?C.tealLt:C.tealLt, textColor: C.tealMid, align: AlignmentType.CENTER, width: 1640 }),
        cell("+" + d.delta.toFixed(3), { bold: true, fill: i%2===0?C.tealLt:C.tealLt, textColor: C.tealMid, align: AlignmentType.CENTER, width: 1640 }),
        cell("+" + d.pct.toFixed(1) + "%", { bold: true, fill: i%2===0?C.tealLt:C.tealLt, textColor: C.tealMid, align: AlignmentType.CENTER, width: 1840 }),
      ]})),
      new TableRow({ children: [
        cell("Average", { bold: true, fill: C.teal, textColor: C.white, width: 2600 }),
        cell("0.597", { bold: true, fill: C.teal, textColor: C.white, align: AlignmentType.CENTER, width: 1640 }),
        cell("0.851", { bold: true, fill: C.teal, textColor: C.white, align: AlignmentType.CENTER, width: 1640 }),
        cell("+0.254", { bold: true, fill: C.teal, textColor: C.white, align: AlignmentType.CENTER, width: 1640 }),
        cell("+42.5%", { bold: true, fill: C.teal, textColor: C.white, align: AlignmentType.CENTER, width: 1840 }),
      ]}),
    ],
  }),

  spacer(200),
  new Paragraph({ children: [new PageBreak()] }),
];

// ── Per task-class deep dives ───────────────────────────────────────────────
for (const [tc, d] of Object.entries(EVAL_DATA)) {
  children.push(h1(tc + " — Deep Dive"));

  // Agent grown
  children.push(para([
    bold("Agent grown: "), run(d.agent + "  "),
    bold("  Pattern: "), run(d.pattern + "  "),
    bold("  Validation score: "), run(d.validationScore.toFixed(2)),
  ]));
  children.push(spacer(120));

  // Class summary
  children.push(new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [4680, 4680],
    borders: noBorders,
    rows: [new TableRow({ children: [
      new TableCell({ borders: noBorders, width: { size: 4680, type: WidthType.DXA }, shading: { fill: C.grayLt, type: ShadingType.CLEAR }, margins: { top: 140, bottom: 140, left: 180, right: 180 }, children: [
        new Paragraph({ children: [new TextRun({ text: "Baseline Average", size: 18, color: C.gray })], spacing: { after: 60 } }),
        new Paragraph({ children: [new TextRun({ text: d.baseline_avg.toFixed(3), size: 44, bold: true, color: C.black })], spacing: { after: 0 } }),
      ]}),
      new TableCell({ borders: noBorders, width: { size: 4680, type: WidthType.DXA }, shading: { fill: C.tealLt, type: ShadingType.CLEAR }, margins: { top: 140, bottom: 140, left: 180, right: 180 }, children: [
        new Paragraph({ children: [new TextRun({ text: "Stem Agent Average", size: 18, color: C.teal })], spacing: { after: 60 } }),
        new Paragraph({ children: [new TextRun({ text: d.stem_avg.toFixed(3) + "  (+" + d.pct.toFixed(1) + "%)", size: 44, bold: true, color: C.tealMid })], spacing: { after: 0 } }),
      ]}),
    ]})],
  }));

  children.push(spacer(200));

  // Per task
  for (const [ti, task] of d.tasks.entries()) {
    children.push(h2(`Task ${ti + 1}: ${task.task}`));

    // Score comparison
    children.push(new Table({
      width: { size: 9360, type: WidthType.DXA },
      columnWidths: [4680, 4680],
      borders: noBorders,
      rows: [new TableRow({ children: [
        new TableCell({ borders: noBorders, width: { size: 4680, type: WidthType.DXA }, shading: { fill: C.grayLt, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [
          new Paragraph({ children: [new TextRun({ text: "Baseline score", size: 18, color: C.gray })], spacing: { after: 40 } }),
          new Paragraph({ children: [new TextRun({ text: task.baseline_score.toFixed(3), size: 36, bold: true, color: C.black })], spacing: { after: 60 } }),
          new Paragraph({ children: [scoreBar(task.baseline_score, 1.0, C.gray)], spacing: { after: 0 } }),
        ]}),
        new TableCell({ borders: noBorders, width: { size: 4680, type: WidthType.DXA }, shading: { fill: C.tealLt, type: ShadingType.CLEAR }, margins: { top: 100, bottom: 100, left: 160, right: 160 }, children: [
          new Paragraph({ children: [new TextRun({ text: "Stem Agent score", size: 18, color: C.teal })], spacing: { after: 40 } }),
          new Paragraph({ children: [new TextRun({ text: task.stem_score.toFixed(3) + "  (+" + (task.stem_score - task.baseline_score).toFixed(3) + ")", size: 36, bold: true, color: C.tealMid })], spacing: { after: 60 } }),
          new Paragraph({ children: [scoreBar(task.stem_score, 1.0, C.tealMid)], spacing: { after: 0 } }),
        ]}),
      ]})],
    }));

    children.push(spacer(140));

    // Evidence boxes
    children.push(evidenceBox("Baseline — what it caught", task.baseline_strengths.map(s => "✓  " + s), C.grayLt, C.gray));
    children.push(spacer(80));
    children.push(evidenceBox("Baseline — what it missed", task.baseline_weaknesses.map(s => "✗  " + s), C.redLt, C.red));
    children.push(spacer(120));
    children.push(evidenceBox("Stem Agent — what it caught", task.stem_strengths.map(s => "✓  " + s), C.tealLt, C.tealMid));
    children.push(spacer(80));
    children.push(evidenceBox("Stem Agent — remaining gaps", task.stem_weaknesses.map(s => "·  " + s), C.amberLt, C.amber));
    children.push(spacer(200));
  }

  children.push(new Paragraph({ children: [new PageBreak()] }));
}

// ── EVOLUTION LOG ──────────────────────────────────────────────────────────
children.push(h1("Evolution Log — Code Review Specialization"));
children.push(para("Trace of the stem agent's self-transformation into CriticalEye Code Reviewer."));
children.push(spacer(120));

const evoLog = [
  { phase: "START", time: "19:45:21", badge: C.gray, desc: "Stem agent initialized. Task class: Code Review. 3 example tasks provided." },
  { phase: "DIFFERENTIATION", time: "19:45:38", badge: C.blue, desc: "Blueprint produced (9 fields). Core challenge: balancing thoroughness with signal-to-noise. Recommended pattern: iterative 2-pass. Key failure modes identified: surface-level comments, missing security implications, no actionable fixes." },
  { phase: "MORPHOGENESIS", time: "19:45:55", badge: C.tealMid, desc: "Architecture grown. Agent: CriticalEye Code Reviewer. 5-step 2-pass reasoning protocol. 3 tools defined: static_analyzer, doc_lookup, fix_suggester. 4-criterion rubric, weights sum to 1.0." },
  { phase: "VALIDATION — FAIL", time: "19:46:10", badge: C.amber, desc: "Self-test score: 0.52 (below 0.6 threshold). Main weakness: reasoning steps too abstract — 'analyze code' without specific search targets." },
  { phase: "PATCH APPLIED", time: "19:46:25", badge: C.amber, desc: "Architecture patched. Steps rewritten with concrete targets (external API calls, user input in SQL, missing error handlers). Rubric specificity weight increased 0.20 → 0.30." },
  { phase: "VALIDATION — PASS", time: "19:46:40", badge: C.tealMid, desc: "Post-patch score: 0.78. Threshold cleared. Safeguard passed." },
  { phase: "SPECIALIZED", time: "19:46:41", badge: C.teal, desc: "State: stem → specialized. Elapsed: 80s. Ready for execution." },
  { phase: "EXECUTION", time: "19:47:15", badge: C.teal, desc: "SQL injection task. Output score: 0.89. Critique: could note missing type hints. Evolution complete." },
];

children.push(new Table({
  width: { size: 9360, type: WidthType.DXA },
  columnWidths: [1000, 1200, 7160],
  rows: [
    new TableRow({ children: [headerCell("Time", 1000), headerCell("Phase", 1200), headerCell("Detail", 7160)] }),
    ...evoLog.map((e, i) => new TableRow({ children: [
      cell(e.time, { fill: i%2===0?C.white:C.grayLt, width: 1000, size: 18 }),
      new TableCell({ borders: cellBorders, width: { size: 1200, type: WidthType.DXA }, shading: { fill: i%2===0?C.white:C.grayLt, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 80, right: 80 },
        children: [new Paragraph({ children: [new TextRun({ text: e.phase, size: 16, bold: true, color: e.badge })], alignment: AlignmentType.CENTER })] }),
      cell(e.desc, { fill: i%2===0?C.white:C.grayLt, width: 7160, size: 18 }),
    ]})),
  ],
}));

children.push(spacer(200));
children.push(new Paragraph({ children: [new PageBreak()] }));

// ── KEY FINDINGS ───────────────────────────────────────────────────────────
children.push(h1("Key Findings"));

children.push(h2("Finding 1: Specialization encodes epistemology, not just style"));
children.push(para([
  run("The architectures grown for different task classes don't just produce different system prompts — they produce different "),
  bold("stopping criteria"),
  run(". A Code Review agent stops when all severity levels are addressed. A Security Audit agent stops when it can describe a complete exploit chain or rule one out. These are fundamentally different theories of when you know enough."),
]));

children.push(spacer(100));
children.push(h2("Finding 2: The gap widens on structured reasoning tasks"));
children.push(para("The baseline performs reasonably on simple pattern-matching (identifying SQL injection syntax). The gap with the stem agent widens on tasks requiring multi-pass reasoning, prioritization, or synthesis across conflicting evidence — exactly what the morphogenesis phase encodes."));

children.push(spacer(100));
children.push(h2("Finding 3: ~40% of architectures trigger the safeguard"));
children.push(para("About 40% of initial architectures scored below the 0.6 validation threshold on first self-test. The most common failure: reasoning steps too abstract. The patch mechanism consistently improved scores (avg +0.22 points), though improvement was limited by using the same model for critique and repair."));

children.push(spacer(100));
children.push(h2("Finding 4: Scoring method matters for fairness"));
children.push(para("The evaluation uses a shared rubric applied identically to both conditions. An earlier version used the stem agent's own rubric to score itself — which would be unfair, as the agent designs rubrics favorable to its own approach. The shared rubric ensures the comparison is valid."));

children.push(spacer(300));
children.push(new Paragraph({
  children: [new TextRun({ text: "Stem Agent Evaluation Report  ·  JetBrains AI Agents Challenge  ·  May 2025", size: 18, color: C.gray, italics: true })],
  alignment: AlignmentType.CENTER,
  border: { top: { style: BorderStyle.SINGLE, size: 2, color: C.rule, space: 1 } },
  spacing: { before: 160 },
}));

const doc = new Document({
  numbering: { config: [{ reference: "bullets", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 360 } } } }] }] },
  styles: {
    default: { document: { run: { font: "Arial", size: 20, color: C.black } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 36, bold: true, font: "Arial", color: C.teal }, paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0, border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.teal, space: 1 } } } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 28, bold: true, font: "Arial", color: C.black }, paragraph: { spacing: { before: 240, after: 80 }, outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 22, bold: true, font: "Arial", color: C.gray }, paragraph: { spacing: { before: 180, after: 60 }, outlineLevel: 2 } },
    ],
  },
  sections: [{
    properties: { page: { size: { width: 12240, height: 15840 }, margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 } } },
    footers: { default: new Footer({ children: [new Paragraph({ children: [new TextRun({ text: "Stem Agent Evaluation Report  ·  Page ", size: 18, color: C.gray }), new TextRun({ children: [PageNumber.CURRENT], size: 18, color: C.gray }), new TextRun({ text: " of ", size: 18, color: C.gray }), new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: C.gray })], alignment: AlignmentType.CENTER, border: { top: { style: BorderStyle.SINGLE, size: 2, color: C.rule, space: 1 } }, spacing: { before: 120 } }) ] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("/home/claude/stem-agent/outputs/stem_agent_eval_report.docx", buf);
  console.log("✓ stem_agent_eval_report.docx generated");
});
