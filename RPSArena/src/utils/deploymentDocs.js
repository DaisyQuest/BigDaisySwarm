import { mkdir, writeFile } from "fs/promises";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export const deploymentGuide = {
  title: "RPS Arena Deployment Playbook",
  intro:
    "Deploy the ultra-fast competitive RPS Arena server with confidence. This guide covers configuration, local validation, and production rollout steps. Both the Markdown and HTML outputs are generated from this shared source so the guidance stays consistent.",
  metadata: {
    generatedNotice: "This file is generated from src/utils/deploymentDocs.js. Update the source, not the outputs.",
    repoRoot: path.join(__dirname, "../.."),
  },
  sections: [
    {
      heading: "Architecture snapshot",
      body: [
        "The Node.js HTTP server (src/server.js) serves the API and static assets from /public.",
        "Data persistence is optional. If MONGODB_URI is unset, the server falls back to an in-memory store. Production deployments should always provide a MongoDB connection string.",
        "Matchmaking, unlockables, and leaderboards depend on the same backing store, so storage outages affect the full experience.",
      ],
      bullets: [
        "API base: /api/* endpoints for registration, login, matchmaking, leaderboards, highscores, news, and match history.",
        "Static content: served from /public with index.html, styles.css, and client scripts.",
        "Process model: single Node.js process bound to PORT (defaults to 3000).",
      ],
    },
    {
      heading: "Prerequisites",
      body: [
        "Node.js 22+ installed on the host or base image.",
        "Network access to MongoDB if you want persistent storage.",
        "A deployment environment capable of setting environment variables for secrets.",
      ],
      bullets: [
        "`PORT` (optional): HTTP port; defaults to 3000.",
        "`MONGODB_URI` (recommended): MongoDB connection string. If omitted, the server runs in-memory and loses data on restart.",
        "`MONGODB_DB` (optional): Database name; defaults to `rpsarena`.",
        "`NODE_ENV` (optional): Set to `production` to align with hardened hosting defaults.",
      ],
    },
    {
      heading: "Local validation",
      body: [
        "Validate the build and APIs locally before promoting to shared environments.",
        "Use a local MongoDB instance if you want persistence; otherwise the in-memory store works for smoke tests.",
      ],
      steps: [
        {
          title: "Install dependencies",
          details: "Install npm dependencies from the project root.",
          commands: ["npm install"],
          outcome: "Dependencies installed with lockfile alignment.",
        },
        {
          title: "Run automated tests",
          details: "Enforce 100% coverage for the Node suite and run the Python tests that back shared tooling.",
          commands: ["npm test", "pytest --maxfail=1"],
          outcome: "All suites green before deployment.",
        },
        {
          title: "Launch the server",
          details:
            "Start the server with or without Mongo. When MONGODB_URI is set, indexes and news seeds are created automatically.",
          commands: [
            "MONGODB_URI=\"mongodb://localhost:27017\" npm start",
            "# or run in-memory\nnpm start",
          ],
          outcome: "HTTP server listening on the configured port.",
        },
        {
          title: "Smoke check APIs",
          details: "Ensure core endpoints respond before packaging.",
          commands: [
            "curl -i http://localhost:3000/api/news",
            "curl -i \"http://localhost:3000/api/leaderboard?limit=5\"",
          ],
          outcome: "200 responses with JSON payloads confirm the server is reachable.",
        },
      ],
    },
    {
      heading: "Production deployment",
      body: [
        "Provide MongoDB credentials and a stable PORT binding. The server is single-process and stateless aside from its storage connection.",
        "Rotate credentials safely. Avoid hardcoding secrets in images; inject them through your platform's configuration layer.",
      ],
      steps: [
        {
          title: "Build or package the app",
          details:
            "Package the server into a container or artifact that runs `npm start`. Keep the working directory at the repository root so static assets resolve correctly.",
          commands: [
            "# Example Dockerfile snippet",
            "FROM node:22-alpine\nWORKDIR /app\nCOPY package*.json ./\nRUN npm ci\nCOPY . .\nENV NODE_ENV=production\nCMD [\"npm\", \"start\"]",
          ],
          outcome: "Runnable artifact that starts the Node.js server.",
        },
        {
          title: "Configure environment",
          details:
            "Bind PORT, supply MONGODB_URI and MONGODB_DB, and set NODE_ENV=production. Ensure outbound connectivity to MongoDB.",
          commands: [
            "PORT=3000",
            "MONGODB_URI=mongodb+srv://<user>:<password>@<cluster>/rpsarena?retryWrites=true&w=majority",
            "MONGODB_DB=rpsarena",
          ],
          outcome: "Runtime configured with durable storage and predictable port binding.",
        },
        {
          title: "Smoke test after deploy",
          details:
            "Hit the same endpoints used locally. Expect seeded news to appear and empty collections for players/matches until traffic arrives.",
          commands: [
            "curl -sS https://<host>/api/news",
            "curl -sS \"https://<host>/api/highscores?variant=ranked&page=1&pageSize=10\"",
          ],
          outcome: "Healthy JSON responses indicate the deployment is ready for traffic.",
        },
      ],
    },
    {
      heading: "Operational checklist",
      body: [
        "Track the following items each time you roll out to keep environments consistent.",
      ],
      bullets: [
        "Backups: ensure MongoDB backups or snapshots are enabled.",
        "Scaling: run at least two replicas if your platform supports it; the server is stateless aside from MongoDB.",
        "Logging: ship stdout/stderr to your logging pipeline for API call traces and errors.",
        "TLS: terminate TLS at the platform or a reverse proxy in front of the Node process.",
        "Static assets: confirm /public is being served; a blank homepage often means the working directory is wrong.",
      ],
    },
  ],
  checklist: {
    title: "Production readiness checklist",
    items: [
      "Environment variables set: PORT, MONGODB_URI, MONGODB_DB, NODE_ENV=production.",
      "MongoDB reachable from the app host and credentials validated.",
      "npm test and pytest --maxfail=1 have both been executed successfully.",
      "Smoke checks on /api/news and /api/leaderboard succeed post-deploy.",
      "Backups, logging, and TLS termination documented for the environment.",
    ],
  },
  references: [
    {
      label: "Server entrypoint",
      value: "src/server.js",
    },
    {
      label: "Mongo persistence",
      value: "src/data/mongoStore.js",
    },
    {
      label: "Static assets",
      value: "public/index.html and supporting files",
    },
  ],
};

const ESCAPE_MAP = {
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  "\"": "&quot;",
};

function escapeHtml(value) {
  const safeValue = value ?? "";
  return String(safeValue).replace(/[&<>"]/g, (char) => ESCAPE_MAP[char]);
}

function ensureSections(sections) {
  if (Array.isArray(sections) && sections.length > 0) {
    return sections;
  }
  return [
    {
      heading: "Content pending",
      body: ["No sections defined yet. Update src/utils/deploymentDocs.js to add guidance."],
    },
  ];
}

function renderList(items, bullet = "- ") {
  if (!items || items.length === 0) return "";
  return items.map((item) => `${bullet}${item}`).join("\n");
}

function renderCommands(commands) {
  if (!commands || commands.length === 0) return "";
  return commands.map((line) => `    ${line}`).join("\n");
}

export function renderMarkdownFromGuide(guide = deploymentGuide) {
  const parts = [];
  parts.push(`# ${guide.title}`);
  if (guide.metadata?.generatedNotice) {
    parts.push(`_${guide.metadata.generatedNotice}_`);
  }
  if (guide.intro) {
    parts.push("", guide.intro);
  }

  for (const section of ensureSections(guide.sections)) {
    parts.push("", `## ${section.heading}`);
    if (section.body && section.body.length) {
      parts.push(...section.body);
    }
    const bullets = renderList(section.bullets || []);
    if (bullets) {
      parts.push("", bullets);
    }
    for (const step of section.steps || []) {
      parts.push("", `### ${step.title}`, step.details || "");
      const commands = renderCommands(step.commands);
      if (commands) {
        parts.push("", "```bash", commands, "```");
      }
      if (step.outcome) {
        parts.push(`**Outcome:** ${step.outcome}`);
      }
    }
  }

  if (guide.checklist) {
    const checklist = renderList(guide.checklist.items);
    parts.push("", `## ${guide.checklist.title}`);
    if (checklist) {
      parts.push(checklist);
    }
  }

  if (guide.references && guide.references.length) {
    parts.push("", "## References");
    for (const reference of guide.references) {
      parts.push(`- **${reference.label}:** ${reference.value}`);
    }
  }

  return parts.join("\n");
}

function renderHtmlList(items) {
  if (!items || items.length === 0) return "";
  const listItems = items.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  return `<ul>${listItems}</ul>`;
}

function renderHtmlCommands(commands) {
  if (!commands || commands.length === 0) return "";
  const escaped = commands.map((line) => escapeHtml(line)).join("\n");
  return `<pre><code>${escaped}</code></pre>`;
}

export function renderHtmlFromGuide(guide = deploymentGuide) {
  const sections = ensureSections(guide.sections)
    .map((section) => {
      const body = section.body?.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("") || "";
      const bullets = renderHtmlList(section.bullets);
      const steps =
        section.steps?.map((step) => {
          const commands = renderHtmlCommands(step.commands);
          const outcome = step.outcome ? `<p><strong>Outcome:</strong> ${escapeHtml(step.outcome)}</p>` : "";
          const detail = step.details ? `<p>${escapeHtml(step.details)}</p>` : "";
          return `<div class="step"><h3>${escapeHtml(step.title)}</h3>${detail}${commands}${outcome}</div>`;
        }).join("") || "";
      return `<section><h2>${escapeHtml(section.heading)}</h2>${body}${bullets}${steps}</section>`;
    })
    .join("");

  const checklist = guide.checklist
    ? `<section><h2>${escapeHtml(guide.checklist.title)}</h2>${renderHtmlList(guide.checklist.items)}</section>`
    : "";

  const references = guide.references
    ? `<section><h2>References</h2><ul>${guide.references
        .map((reference) => `<li><strong>${escapeHtml(reference.label)}:</strong> ${escapeHtml(reference.value)}</li>`)
        .join("")}</ul></section>`
    : "";

  const notice = guide.metadata?.generatedNotice
    ? `<p class="notice">${escapeHtml(guide.metadata.generatedNotice)}</p>`
    : "";

  return [
    "<!doctype html>",
    "<html>",
    "<head>",
    `<meta charset="utf-8">`,
    `<title>${escapeHtml(guide.title)}</title>`,
    `<style>
      body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; color: #1f2937; }
      h1, h2, h3 { color: #111827; }
      .notice { font-style: italic; color: #6b7280; }
      code { background: #f3f4f6; padding: 2px 4px; border-radius: 4px; }
      pre { background: #111827; color: #e5e7eb; padding: 12px; border-radius: 6px; overflow-x: auto; }
      section { margin-bottom: 28px; }
      .step { border-left: 4px solid #2563eb; padding-left: 12px; margin-top: 12px; }
    </style>`,
    "</head>",
    "<body>",
    `<h1>${escapeHtml(guide.title)}</h1>`,
    notice,
    guide.intro ? `<p>${escapeHtml(guide.intro)}</p>` : "",
    sections,
    checklist,
    references,
    "</body>",
    "</html>",
  ].join("\n");
}

export async function writeDeploymentDocs({ markdownPath, htmlPath } = {}) {
  const markdownTarget = markdownPath || path.join(deploymentGuide.metadata.repoRoot, "docs", "deployment.md");
  const htmlTarget = htmlPath || path.join(deploymentGuide.metadata.repoRoot, "public", "deployment.html");

  await mkdir(path.dirname(markdownTarget), { recursive: true });
  await mkdir(path.dirname(htmlTarget), { recursive: true });

  const markdown = renderMarkdownFromGuide(deploymentGuide);
  const html = renderHtmlFromGuide(deploymentGuide);

  await writeFile(markdownTarget, `${markdown}\n`, "utf8");
  await writeFile(htmlTarget, `${html}\n`, "utf8");

  return { markdownTarget, htmlTarget };
}

function isExecutedDirectly() {
  const entryPoint = process.argv[1];
  if (!entryPoint) return false;
  return path.resolve(entryPoint) === path.resolve(__filename);
}

export async function runWhenExecutedDirectly({ writer = writeDeploymentDocs } = {}) {
  if (!isExecutedDirectly()) return false;
  try {
    await writer();
    return true;
  } catch (error) {
    console.error("Failed to write deployment docs", error);
    process.exitCode = 1;
    return false;
  }
}

runWhenExecutedDirectly();
