import { strict as assert } from "node:assert";
import { mkdtemp, readFile, rm } from "node:fs/promises";
import path from "node:path";
import { tmpdir } from "node:os";
import test from "node:test";
import { fileURLToPath } from "node:url";

import {
  deploymentGuide,
  renderHtmlFromGuide,
  renderMarkdownFromGuide,
  runWhenExecutedDirectly,
  writeDeploymentDocs,
} from "../src/utils/deploymentDocs.js";

test("renders markdown and html from the shared deployment guide", async () => {
  const markdown = renderMarkdownFromGuide(deploymentGuide);
  const html = renderHtmlFromGuide(deploymentGuide);

  assert.match(markdown, /RPS Arena Deployment Playbook/);
  assert.match(markdown, /MONGODB_URI/);
  assert.match(markdown, /WEBSITES_PORT/);
  assert.match(markdown, /MONGODB_TLS/);
  assert.match(markdown, /Smoke check APIs/);
  assert.match(markdown, /Production readiness checklist/);

  assert.match(html, /<h1>RPS Arena Deployment Playbook/);
  assert.match(html, /MONGODB_URI/);
  assert.match(html, /WEBSITES_PORT/);
  assert.match(html, /Smoke test after deploy/);
  assert.match(html, /Production readiness checklist/);
});

test("falls back gracefully when optional fields are missing", () => {
  const customGuide = { title: "Bare", sections: [] };
  const markdown = renderMarkdownFromGuide(customGuide);
  const html = renderHtmlFromGuide(customGuide);

  assert.match(markdown, /Content pending/);
  assert.ok(!markdown.includes("generated from"), "notice is omitted when metadata is missing");
  assert.match(html, /Content pending/);
  assert.ok(!html.includes("generated from"), "HTML omits notice when metadata is missing");
});

test("renders steps without commands and empty checklists while escaping HTML", () => {
  const customGuide = {
    title: "Escaped",
    intro: "Intro with <danger> tags & symbols.",
    metadata: {},
    sections: [
      {
        heading: "No commands section",
        body: ["Details with <tags> to escape", undefined],
        steps: [
          {
            title: "Missing commands",
            details: "No command block here",
            outcome: "Covers branch without commands",
          },
        ],
      },
      {
        heading: "Skeleton",
        steps: [{ title: "No details or outcomes" }],
      },
    ],
    checklist: { title: "Empty checklist", items: [] },
    references: null,
  };

  const markdown = renderMarkdownFromGuide(customGuide);
  const html = renderHtmlFromGuide(customGuide);

  assert.match(markdown, /Missing commands/);
  assert.match(markdown, /Empty checklist/);
  assert.ok(!markdown.includes("```bash"), "no command block emitted");

  assert.match(html, /Intro with &lt;danger&gt;/);
  assert.match(html, /Details with &lt;tags&gt; to escape/);
  assert.match(html, /Skeleton/);
  assert.match(html, /No details or outcomes/);
  assert.match(html, /Missing commands/);
  assert.ok(!html.includes("<code>"), "no command block emitted");
  assert.ok(!html.includes("References"), "references section omitted");
});

test("writes deployment docs to both default and custom locations", async () => {
  const tempDir = await mkdtemp(path.join(tmpdir(), "rps-deploy-"));
  const markdownPath = path.join(tempDir, "deploy.md");
  const htmlPath = path.join(tempDir, "deploy.html");

  const customResult = await writeDeploymentDocs({ markdownPath, htmlPath });
  const customMarkdown = await readFile(customResult.markdownTarget, "utf8");
  const customHtml = await readFile(customResult.htmlTarget, "utf8");

  assert.ok(customMarkdown.includes("generated from src/utils/deploymentDocs.js"));
  assert.match(customHtml, /<html>/);

  const defaultResult = await writeDeploymentDocs();
  const defaultMarkdown = await readFile(defaultResult.markdownTarget, "utf8");
  const defaultHtml = await readFile(defaultResult.htmlTarget, "utf8");

  assert.match(defaultMarkdown, /RPS Arena Deployment Playbook/);
  assert.match(defaultHtml, /RPS Arena Deployment Playbook/);

  await rm(tempDir, { recursive: true, force: true });
});

test("runWhenExecutedDirectly respects argv matching and failure handling", async () => {
  const originalArgv = process.argv.slice();
  const originalError = console.error;
  const originalExitCode = process.exitCode;
  const scriptPath = fileURLToPath(new URL("../src/utils/deploymentDocs.js", import.meta.url));
  let errorMessage = "";

  console.error = (...args) => {
    errorMessage = args.join(" ");
  };

  process.argv = [process.argv[0]];
  const skipped = await runWhenExecutedDirectly();
  assert.equal(skipped, false);

  process.argv = [process.argv[0], scriptPath];
  const ranSuccessfully = await runWhenExecutedDirectly({ writer: async () => {} });
  assert.equal(ranSuccessfully, true);

  errorMessage = "";
  const ranWithFailure = await runWhenExecutedDirectly({
    writer: async () => {
      throw new Error("failure");
    },
  });

  assert.equal(ranWithFailure, false);
  assert.match(errorMessage, /Failed to write deployment docs/);
  assert.equal(process.exitCode, 1);

  process.argv = originalArgv;
  console.error = originalError;
  process.exitCode = originalExitCode;
});
