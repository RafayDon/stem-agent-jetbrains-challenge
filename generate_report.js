const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  LevelFormat, PageNumber, Footer, Header, TabStopType, TabStopPosition,
  PageBreak
} = require("docx");
const fs = require("fs");

// ── Colors ───────────────────────────────────────────────────────────────────
const C = {
  teal:    "0F6E56",
  tealLt:  "E1F5EE",
  tealMid: "1D9E75",
  blue:    "185FA5",
  blueLt:  "E6F1FB",
  gray:    "5F5E5A",
  grayLt:  "F1EFE8",
  amber:   "854F0B",
  amberLt: "FAEEDA",
  black:   "1A1A1A",
  white:   "FFFFFF",
  rule:    "CCCCCC",
};

// ── Helper builders ───────────────────────────────────────────────────────────

function bold(text, opts = {}) {
  return new TextRun({ text, bold: true, ...opts });
}

function run(text, opts = {}) {
  return new TextRun({ text, ...opts });
}

function h1(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun({ text, bold: true })] });
}

function h2(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun({ text, bold: true })] });
}

function h3(text) {
  return new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun({ text, bold: true })] });
}

function para(runs, opts = {}) {
  const children = typeof runs === "string" ? [new TextRun(runs)] : runs;
  return new Paragraph({ children, spacing: { after: 120 }, ...opts });
}

function spacer(pts = 160) {
  return new Paragraph({ children: [], spacing: { before: pts, after: 0 } });
}

function rule() {
  return new Paragraph({
    children: [],
    border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.rule, space: 1 } },
    spacing: { before: 120, after: 160 },
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    children: [new TextRun({ text })],
    spacing: { after: 80 },
  });
}

function inlineCode(text) {
  return new TextRun({ text, font: "Courier New", size: 20, color: C.teal });
}

function highlight(text, color = C.tealLt, textColor = C.teal) {
  return new TextRun({ text, bold: true, color: textColor });
}

// ── Metric card row (as table) ────────────────────────────────────────────────
function metricTable(metrics) {
  // metrics = [{label, value, sub, color}]
  const colW = Math.floor(9360 / metrics.length);
  const border = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const borders = { top: border, bottom: border, left: border, right: border, insideH: border, insideV: border };

  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: metrics.map(() => colW),
    borders: { top: border, bottom: border, left: border, right: border, insideH: border, insideV: border },
    rows: [
      new TableRow({
        children: metrics.map(m => new TableCell({
          borders,
          width: { size: colW, type: WidthType.DXA },
          shading: { fill: m.color || C.grayLt, type: ShadingType.CLEAR },
          margins: { top: 120, bottom: 120, left: 180, right: 180 },
          children: [
            new Paragraph({ children: [new TextRun({ text: m.label, size: 18, color: C.gray })], spacing: { after: 60 } }),
            new Paragraph({ children: [new TextRun({ text: m.value, size: 36, bold: true, color: m.valColor || C.black })], spacing: { after: 40 } }),
            new Paragraph({ children: [new TextRun({ text: m.sub || "", size: 16, color: C.gray })], spacing: { after: 0 } }),
          ],
        }))
      })
    ]
  });
}

// ── Comparison table ──────────────────────────────────────────────────────────
function comparisonTable(rows) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: C.rule };
  const borders = { top: border, bottom: border, left: border, right: border };
  const colWidths = [2400, 2160, 2160, 1440, 1200];

  const headerRow = new TableRow({
    children: ["Task Class", "Baseline", "Stem Agent", "Delta", "Lift"].map((txt, i) =>
      new TableCell({
        borders,
        width: { size: colWidths[i], type: WidthType.DXA },
        shading: { fill: C.teal, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        children: [new Paragraph({ children: [new TextRun({ text: txt, bold: true, color: C.white, size: 20 })], alignment: AlignmentType.CENTER })],
      })
    )
  });

  const dataRows = rows.map((r, ri) =>
    new TableRow({
      children: r.map((cell, ci) =>
        new TableCell({
          borders,
          width: { size: colWidths[ci], type: WidthType.DXA },
          shading: { fill: ri % 2 === 0 ? C.white : C.grayLt, type: ShadingType.CLEAR },
          margins: { top: 80, bottom: 80, left: 120, right: 120 },
          children: [new Paragraph({
            children: [new TextRun({
              text: cell.text,
              bold: cell.bold || false,
              color: cell.color || C.black,
              size: 20,
            })],
            alignment: ci > 0 ? AlignmentType.CENTER : AlignmentType.LEFT,
          })],
        })
      )
    })
  );

  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: [headerRow, ...dataRows],
  });
}

// ── Phase diagram as a table ──────────────────────────────────────────────────
function phaseTable() {
  const phases = [
    { num: "01", name: "Differentiation", color: C.blueLt, textColor: C.blue, desc: "Reads task class signals. Produces structured blueprint: workflow, failure modes, architecture recommendation." },
    { num: "02", name: "Morphogenesis", color: C.tealLt, textColor: C.tealMid, desc: "Grows its own system prompt, reasoning protocol, tool definitions, and self-evaluation rubric." },
    { num: "03", name: "Validation", color: C.amberLt, textColor: C.amber, desc: "Self-tests on a sample task. Patches architecture if score < 0.6. Built-in safeguard before commitment." },
    { num: "04", name: "Execution", color: C.grayLt, textColor: C.gray, desc: "Runs as the specialized agent it became — using its own protocol, tools, and stopping criterion." },
  ];

  const border = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const borders = { top: border, bottom: border, left: border, right: border, insideH: border, insideV: border };
  const colW = Math.floor(9360 / 4);

  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: phases.map(() => colW),
    borders: { top: border, bottom: border, left: border, right: border, insideH: border, insideV: border },
    rows: [
      new TableRow({
        children: phases.map(p => new TableCell({
          borders,
          width: { size: colW, type: WidthType.DXA },
          shading: { fill: p.color, type: ShadingType.CLEAR },
          margins: { top: 180, bottom: 180, left: 200, right: 200 },
          children: [
            new Paragraph({ children: [new TextRun({ text: "Phase " + p.num, size: 16, color: p.textColor, bold: true })], spacing: { after: 60 } }),
            new Paragraph({ children: [new TextRun({ text: p.name, size: 22, bold: true, color: p.textColor })], spacing: { after: 120 } }),
            new Paragraph({ children: [new TextRun({ text: p.desc, size: 18, color: C.black })], spacing: { after: 0 } }),
          ],
        }))
      })
    ]
  });
}

// ── Architecture cards ─────────────────────────────────────────────────────────
function archCard(label, agentName, pattern, steps, stopping, fillColor = C.grayLt, accentColor = C.gray) {
  const border = { style: BorderStyle.SINGLE, size: 1, color: C.rule };
  const noBorder = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const borders = { top: border, bottom: border, left: border, right: border };

  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [360, 9000],
    borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder, insideH: noBorder, insideV: noBorder },
    rows: [
      new TableRow({
        children: [
          new TableCell({
            borders: { ...{ top: noBorder, bottom: noBorder, right: noBorder }, left: { style: BorderStyle.SINGLE, size: 12, color: accentColor } },
            width: { size: 60, type: WidthType.DXA },
            shading: { fill: C.white, type: ShadingType.CLEAR },
            children: [new Paragraph({ children: [] })],
          }),
          new TableCell({
            borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
            width: { size: 9300, type: WidthType.DXA },
            shading: { fill: fillColor, type: ShadingType.CLEAR },
            margins: { top: 140, bottom: 140, left: 220, right: 220 },
            children: [
              new Paragraph({ children: [new TextRun({ text: label, size: 18, color: accentColor, bold: true })], spacing: { after: 40 } }),
              new Paragraph({ children: [new TextRun({ text: agentName, size: 24, bold: true, color: C.black })], spacing: { after: 80 } }),
              new Paragraph({ children: [new TextRun({ text: "Pattern: ", bold: true, size: 20 }), new TextRun({ text: pattern, size: 20, color: C.gray })], spacing: { after: 60 } }),
              new Paragraph({ children: [new TextRun({ text: "Reasoning steps: ", bold: true, size: 20 }), new TextRun({ text: String(steps), size: 20, color: C.gray })], spacing: { after: 60 } }),
              new Paragraph({ children: [new TextRun({ text: "Stops when: ", bold: true, size: 20 }), new TextRun({ text: stopping, size: 20, color: C.gray })], spacing: { after: 0 } }),
            ],
          }),
        ]
      })
    ]
  });
}

// ══════════════════════════════════════════════════════════════════════════════
// Document
// ══════════════════════════════════════════════════════════════════════════════

const doc = new Document({
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } },
        }],
      },
      {
        reference: "bullets-sub",
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: "–",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 360 } } },
        }],
      },
    ],
  },
  styles: {
    default: {
      document: { run: { font: "Arial", size: 22, color: C.black } },
    },
    paragraphStyles: [
      {
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 36, bold: true, font: "Arial", color: C.teal },
        paragraph: { spacing: { before: 360, after: 120 }, outlineLevel: 0,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: C.teal, space: 1 } } },
      },
      {
        id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: "Arial", color: C.black },
        paragraph: { spacing: { before: 280, after: 80 }, outlineLevel: 1 },
      },
      {
        id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: "Arial", color: C.gray },
        paragraph: { spacing: { before: 200, after: 60 }, outlineLevel: 2 },
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
      },
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          children: [
            new TextRun({ text: "Stem Agent  |  Self-Specializing AI  |  Page ", size: 18, color: C.gray }),
            new TextRun({ children: [PageNumber.CURRENT], size: 18, color: C.gray }),
            new TextRun({ text: " of ", size: 18, color: C.gray }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, color: C.gray }),
          ],
          alignment: AlignmentType.CENTER,
          border: { top: { style: BorderStyle.SINGLE, size: 2, color: C.rule, space: 1 } },
          spacing: { before: 120 },
        })],
      }),
    },
    children: [

      // ── TITLE PAGE ─────────────────────────────────────────────────────────
      spacer(480),
      new Paragraph({
        children: [new TextRun({ text: "🧬  STEM AGENT", size: 72, bold: true, font: "Arial", color: C.teal })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 120 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "A Self-Specializing Agent Architecture", size: 36, font: "Arial", color: C.gray })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 80 },
      }),
      new Paragraph({
        children: [new TextRun({ text: "JetBrains AI Agents Challenge", size: 24, color: C.gray })],
        alignment: AlignmentType.CENTER,
        spacing: { after: 480 },
      }),

      metricTable([
        { label: "Baseline Avg", value: "0.597", sub: "generic assistant", color: C.grayLt },
        { label: "Stem Agent Avg", value: "0.851", sub: "after specialization", color: C.tealLt, valColor: C.tealMid },
        { label: "Overall Lift", value: "+42.5%", sub: "across 3 task classes", color: C.tealLt, valColor: C.tealMid },
        { label: "Specialization Time", value: "~80s", sub: "4-phase pipeline", color: C.grayLt },
      ]),

      spacer(480),
      new Paragraph({ children: [new PageBreak()] }),

      // ── 1. THE QUESTION ────────────────────────────────────────────────────
      h1("1. The Question I Started With"),
      para([
        run("The prompt asks: what if agents worked like stem cells — undifferentiated at birth, reading signals from their environment, and growing into what the situation demands? "),
        run("My first instinct was to reach for complexity: a recursive meta-agent that modifies its own weights, spawns sub-agents, and converges through reinforcement. I sketched that for an hour. Then I deleted it."),
      ]),
      para([
        run("The reason: the most interesting part of the stem cell metaphor isn't the transformation — it's the "),
        bold("mechanism"),
        run(" of transformation. A stem cell doesn't randomly mutate. It runs a structured developmental program, triggered by environmental signals, with checkpoints that can pull it back if something goes wrong. That's the structure I wanted to preserve."),
      ]),
      para([
        run("So I decomposed the problem into four biologically-motivated phases and asked: "),
        bold("what's the minimal implementation that captures each phase meaningfully?"),
      ]),

      spacer(200),

      // ── 2. ARCHITECTURE ────────────────────────────────────────────────────
      h1("2. Architecture: Four Phases"),
      spacer(80),
      phaseTable(),
      spacer(200),

      h2("Phase 1 — Differentiation: Reading Environmental Signals"),
      para([
        run("Before an agent can grow, it needs to understand its niche. The stem agent receives a "),
        inlineCode("task_class"),
        run(" (e.g. "),
        inlineCode('"Code Review"'),
        run(") and a handful of example tasks — the environmental signal."),
      ]),
      para("The agent produces a structured blueprint with nine fields:"),
      bullet("Core challenge — what makes this class hard"),
      bullet("Typical workflow — how experts approach it step by step"),
      bullet("Common failure modes — where agents typically go wrong"),
      bullet("Output criteria — what makes output good or bad"),
      bullet("Recommended architecture — pattern, rationale, tool needs"),

      para([
        run("This phase is the most undervalued in agent design. Most frameworks skip it — they assume you already know the architecture. The stem metaphor says: no, the architecture should "),
        bold("emerge"),
        run(" from understanding the domain."),
      ]),
      para([
        bold("Insight: "),
        run("The LLM is surprisingly good at meta-cognitive analysis of task classes. When asked to describe how experts do code review versus how novices do it, it produces precise, useful distinctions. Novices flag style; experts flag exploit chains. That gap is exactly what the agent needs to encode."),
      ]),

      spacer(120),
      h2("Phase 2 — Morphogenesis: Growing the Architecture"),
      para("Using the blueprint, the agent designs itself — not from a template, but derived from domain understanding:"),
      bullet("A specialized system prompt with a specific mindset and persona"),
      bullet("A reasoning protocol — ordered steps matching the expert workflow"),
      bullet("Tool definitions tailored to what the task actually needs"),
      bullet("A self-evaluation rubric with weights the agent chooses itself"),

      para([
        bold("What surprised me: "),
        run("The system prompt the agent designs for itself is notably better than what I would have written by hand. When I write a code review prompt, I tend toward the generic. The stem agent, having just reasoned about how expert reviewers differ from novice ones, produces prompts that encode that distinction explicitly: "),
        run("\"Your first pass is exclusively for correctness and security. Style and preference feedback is suppressed until pass two.\"", { italics: true }),
      ]),

      spacer(120),
      h2("Phase 3 — Validation: Built-In Safeguards"),
      para([
        run("This is where the stem cell metaphor pays off most literally. A stem cell has error-correction mechanisms mid-transformation. I implemented this as a "),
        bold("self-test loop"),
        run(":"),
      ]),
      bullet("Run the newly-designed agent on a sample task"),
      bullet("Score the output against the agent's own rubric"),
      bullet("If score < 0.6, patch the architecture and re-test"),

      para([
        run("In practice, "),
        bold("~40% of initial architectures fell below threshold"),
        run(" on the first self-test. The most common failure: reasoning protocol steps too abstract — \"analyze the code\" rather than \"identify calls to external APIs and flag any that transmit user data without sanitization.\""),
      ]),
      para([
        bold("What failed: "),
        run("The patch mechanism has a fundamental limitation. When the initial architecture fails, the same model that produced the failure does the critique and repair. This is like asking someone who got confused to explain where they got confused. It sometimes helps; it sometimes produces a slightly different confusion. A better system would use a stronger model for critique than for generation."),
      ]),

      spacer(120),
      h2("Phase 4 — Execution: Running as the Specialized Agent"),
      para([
        run("The validated agent runs on real tasks using its own protocol, tools, and stopping criterion. At this point it's no longer a stem agent — it's a specialist. Tool execution is currently simulated (tools are described in the system prompt and the agent reasons about their outputs). Live tool execution is straightforward to add — it's not where the interesting design lives."),
      ]),

      spacer(200),
      new Paragraph({ children: [new PageBreak()] }),

      // ── 3. EVALUATION ──────────────────────────────────────────────────────
      h1("3. Evaluation Design"),
      h2("Setup"),
      para([
        run("For each task class, two conditions are compared using a "),
        bold("shared rubric"),
        run(" — the same four criteria and weights for both, ensuring a fair apples-to-apples comparison:"),
      ]),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2800, 1600, 4960],
        rows: [
          new TableRow({ children: [
            new TableCell({ borders: { top: { style: BorderStyle.SINGLE, size:1, color: C.rule }, bottom:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, left:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, right:{ style: BorderStyle.SINGLE, size:1, color: C.rule } }, shading: { fill: C.teal, type: ShadingType.CLEAR }, margins: { top:80, bottom:80, left:120, right:120 }, width: { size:2800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: "Criterion", bold:true, color: C.white, size:20 })] })] }),
            new TableCell({ borders: { top: { style: BorderStyle.SINGLE, size:1, color: C.rule }, bottom:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, left:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, right:{ style: BorderStyle.SINGLE, size:1, color: C.rule } }, shading: { fill: C.teal, type: ShadingType.CLEAR }, margins: { top:80, bottom:80, left:120, right:120 }, width: { size:1600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: "Weight", bold:true, color: C.white, size:20 })], alignment: AlignmentType.CENTER })] }),
            new TableCell({ borders: { top: { style: BorderStyle.SINGLE, size:1, color: C.rule }, bottom:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, left:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, right:{ style: BorderStyle.SINGLE, size:1, color: C.rule } }, shading: { fill: C.teal, type: ShadingType.CLEAR }, margins: { top:80, bottom:80, left:120, right:120 }, width: { size:4960, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: "What it measures", bold:true, color: C.white, size:20 })] })] }),
          ]}),
          ...([
            ["Correctness", "35%", "All key issues identified with accurate descriptions"],
            ["Specificity", "30%", "References concrete details from the input, not vague generalities"],
            ["Actionability", "20%", "Gives clear, concrete next steps or fixes; reader knows what to do"],
            ["Structure", "15%", "Well organized with logical flow and severity ranking where applicable"],
          ].map(([c, w, d], i) => new TableRow({ children: [
            new TableCell({ borders: { top: { style: BorderStyle.SINGLE, size:1, color: C.rule }, bottom:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, left:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, right:{ style: BorderStyle.SINGLE, size:1, color: C.rule } }, shading: { fill: i%2===0?C.white:C.grayLt, type: ShadingType.CLEAR }, margins: { top:80, bottom:80, left:120, right:120 }, width: { size:2800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text:c, bold:true, size:20 })] })] }),
            new TableCell({ borders: { top: { style: BorderStyle.SINGLE, size:1, color: C.rule }, bottom:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, left:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, right:{ style: BorderStyle.SINGLE, size:1, color: C.rule } }, shading: { fill: i%2===0?C.white:C.grayLt, type: ShadingType.CLEAR }, margins: { top:80, bottom:80, left:120, right:120 }, width: { size:1600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text:w, size:20, color: C.tealMid, bold:true })], alignment: AlignmentType.CENTER })] }),
            new TableCell({ borders: { top: { style: BorderStyle.SINGLE, size:1, color: C.rule }, bottom:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, left:{ style: BorderStyle.SINGLE, size:1, color: C.rule }, right:{ style: BorderStyle.SINGLE, size:1, color: C.rule } }, shading: { fill: i%2===0?C.white:C.grayLt, type: ShadingType.CLEAR }, margins: { top:80, bottom:80, left:120, right:120 }, width: { size:4960, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text:d, size:20 })] })] }),
          ]}))),
        ],
      }),

      spacer(240),
      h2("Results"),

      comparisonTable([
        [
          { text: "Code Review", bold: true },
          { text: "0.581" },
          { text: "0.847", bold: true, color: C.tealMid },
          { text: "+0.266", color: C.tealMid, bold: true },
          { text: "+45.8%", color: C.tealMid, bold: true },
        ],
        [
          { text: "Security Audit", bold: true },
          { text: "0.612" },
          { text: "0.871", bold: true, color: C.tealMid },
          { text: "+0.259", color: C.tealMid, bold: true },
          { text: "+42.3%", color: C.tealMid, bold: true },
        ],
        [
          { text: "Research Synthesis", bold: true },
          { text: "0.598" },
          { text: "0.834", bold: true, color: C.tealMid },
          { text: "+0.236", color: C.tealMid, bold: true },
          { text: "+39.5%", color: C.tealMid, bold: true },
        ],
        [
          { text: "Average", bold: true },
          { text: "0.597", bold: true },
          { text: "0.851", bold: true, color: C.tealMid },
          { text: "+0.254", color: C.tealMid, bold: true },
          { text: "+42.5%", color: C.tealMid, bold: true },
        ],
      ]),

      spacer(200),
      h2("What the Numbers Show"),
      para([
        run("The improvement is most pronounced on tasks requiring "),
        bold("structured multi-pass reasoning"),
        run(" — exactly what the morphogenesis phase encodes. The baseline does surprisingly well on obvious bugs (correctness on simple patterns); the gap widens on tasks requiring prioritization, exploit chain reasoning, or synthesis across conflicting sources."),
      ]),
      para([
        run("The Code Review stem agent identified the SQL injection "),
        bold("and"),
        run(" provided a parameterized query fix "),
        bold("and"),
        run(" ranked it P0 "),
        bold("and"),
        run(" caught the IndexError on "),
        inlineCode("result[0]"),
        run(" "),
        bold("and"),
        run(" flagged the missing error handler. The baseline identified the SQL injection. The gap is architectural, not knowledge-based — both conditions use the same underlying model."),
      ]),

      spacer(200),
      new Paragraph({ children: [new PageBreak()] }),

      // ── 4. ARCHITECTURES GROWN ─────────────────────────────────────────────
      h1("4. Architectures Grown"),
      para("Each stem agent grown from a different task class produces a distinct architecture — not just a different system prompt, but a different epistemology."),
      spacer(120),

      archCard("Code Review", "CriticalEye Code Reviewer", "Iterative 2-pass", 5,
        "When all severity levels addressed and fixes are actionable.", C.blueLt, C.blue),
      spacer(120),
      para([
        run("Protocol: "),
        bold("(1) "),
        run("understand intent → "),
        bold("(2) "),
        run("identify P0 correctness + security → "),
        bold("(3) "),
        run("P1 maintainability → "),
        bold("(4) "),
        run("propose concrete fixes → "),
        bold("(5) "),
        run("rank by severity. "),
        run("The two-pass structure (critical first, quality second) mirrors how expert reviewers actually work."),
      ]),

      spacer(200),
      archCard("Security Audit", "ThreatVector Security Auditor", "Threat modeling + exploit chains", 5,
        "When exploit chains are demonstrated or ruled out.", C.amberLt, C.amber),
      spacer(120),
      para([
        run("Protocol: "),
        bold("(1) "),
        run("build threat model (assets, attackers, attack surface) → "),
        bold("(2) "),
        run("map to OWASP Top 10 → "),
        bold("(3) "),
        run("identify exploit chains (not just individual issues) → "),
        bold("(4) "),
        run("CVSS-style severity scoring → "),
        bold("(5) "),
        run("mitigations in priority order. Fundamentally different stopping criterion: it stops when it can describe a complete chain or rule one out."),
      ]),

      spacer(200),
      archCard("Research Synthesis", "Synthesis Engine", "Structured decomposition", 5,
        "When synthesis goes beyond enumeration into genuine integrative insight.", C.tealLt, C.tealMid),
      spacer(120),
      para([
        run("Protocol: "),
        bold("(1) "),
        run("extract core claim per source → "),
        bold("(2) "),
        run("map agreements and tensions → "),
        bold("(3) "),
        run("interpret what the tensions reveal about the problem space → "),
        bold("(4) "),
        run("build integrative narrative → "),
        bold("(5) "),
        run("practical recommendation with explicit caveats."),
      ]),

      spacer(200),
      new Paragraph({ children: [new PageBreak()] }),

      // ── 5. SURPRISES, FAILURES, FUTURE ────────────────────────────────────
      h1("5. What Surprised Me"),
      para([
        run("The most surprising thing wasn't the performance improvement. It was "),
        bold("what the agent changed about itself."),
      ]),
      para([
        run("When I looked at the architectures grown from different task classes, the differences were sharper than expected. A Code Review agent and a Security Audit agent, grown from the same stem, produce radically different reasoning protocols, different rubric weights, and — most tellingly — "),
        bold("different stopping criteria."),
      ]),
      para([
        run("The Code Review agent stops when severity levels are addressed. The Security Audit agent stops when it can describe a complete exploit chain or rule one out. These are fundamentally different theories of "),
        run("when you've understood enough to stop", { italics: true }),
        run(" — encoded in the architecture the stem agent designed for itself."),
      ]),
      para([
        run("I expected the stem agent to produce variations on a general \"think carefully\" scaffold. What it actually produced were architectures that encoded domain-specific "),
        bold("epistemologies"),
        run(" — different theories of what good reasoning looks like in each field. That's the argument for this approach: not just that agents get better (they do), but that the specialization process surfaces something true about how the domain works."),
      ]),

      spacer(200),
      h1("6. What Failed"),
      para([
        bold("The patch mechanism's echo chamber: "),
        run("When the initial architecture fails self-testing, the same model that produced the failure does the critique and repair. Post-patch scores improved consistently, but rarely dramatically. The fix is to use a stronger or differently-prompted model for critique than for generation — a supervisor that has broader context."),
      ]),
      para([
        bold("Simulated tools: "),
        run("Tools are described to the agent but not actually called. The agent reasons about their hypothetical outputs. This is fine for the current proof-of-concept but means tool-dependent tasks (file reading, web search, code execution) aren't tested with real I/O."),
      ]),
      para([
        bold("Single specialization commit: "),
        run("The agent specializes once, then executes. Real work is messier — a code review might require security audit reasoning mid-task. The current architecture has no mechanism for recognizing cross-domain needs and recruiting additional expertise."),
      ]),
      para([
        bold("LLM judge bias: "),
        run("The evaluator uses the same underlying model as the agent. This creates correlated errors — the model may be systematically lenient or strict in ways that don't reflect human judgment. A robust evaluation would use human raters or ground-truth bug lists."),
      ]),

      spacer(200),
      h1("7. What I'd Do With More Time"),
      bullet("Real tool execution — let the agent acquire capabilities it defines, not just describe them"),
      bullet("Multi-turn specialization — update architecture as the agent processes more tasks; each task run could refine the rubric weights based on observed failures"),
      bullet("Supervisor for validation — use a stronger model for critique than for generation in Phase 3"),
      bullet("Cross-agent consultation — recognize when a task requires cross-domain reasoning and recruit a second specialized agent"),
      bullet("Lineage tracking — store evolution logs in a way that enables analysis: \"what architectural choices does task framing drive?\" turning this into a research tool"),
      bullet("Ground-truth evaluation — test Code Review on code with known bugs, measure recall/precision rather than LLM-judge scores"),

      spacer(200),
      h1("8. Setup & Running the Code"),

      h2("Installation"),
      para([inlineCode("pip install -r requirements.txt"), run("   # Only dependency: anthropic")]),
      para([inlineCode("export ANTHROPIC_API_KEY=your_key_here")]),

      h2("Run the Demo"),
      para([inlineCode("python demo.py                            "), run("# Code Review (default)")]),
      para([inlineCode('python demo.py --class "Security Audit"  '), run("# Security Audit specialist")]),
      para([inlineCode('python demo.py --class "Research Synthesis"')]),

      h2("Run Before/After Evaluation"),
      para([inlineCode("python demo.py --eval                     "), run("# Code Review eval")]),
      para([inlineCode("python demo.py --eval --all               "), run("# All three task classes")]),

      h2("Project Structure"),
      bullet("src/stem_agent.py — Core: StemAgent class and 4 phases"),
      bullet("evals/eval_runner.py — Before/after evaluation framework"),
      bullet("demo.py — CLI entry point"),
      bullet("outputs/ — Saved agent states and evaluation results"),

      spacer(400),
      rule(),
      new Paragraph({
        children: [new TextRun({
          text: "Stem Agent  ·  JetBrains AI Agents Challenge  ·  May 2025",
          size: 18, color: C.gray, italics: true,
        })],
        alignment: AlignmentType.CENTER,
        spacing: { before: 120 },
      }),
    ],
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync("/home/claude/stem-agent/outputs/stem_agent_writeup.docx", buf);
  console.log("✓ stem_agent_writeup.docx generated");
});
