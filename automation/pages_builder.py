from __future__ import annotations

import argparse
import html
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List

try:
    import tomllib  # Python 3.11+
except ModuleNotFoundError:  # pragma: no cover - fallback for older environments
    tomllib = None


@dataclass(frozen=True)
class SiteSection:
    """Metadata that describes how to publish a single section of the GitHub Pages site."""

    title: str
    source: Path
    kind: str
    destination: Path
    description: str = ""

    def validate(self) -> None:
        if self.kind not in {
            "markdown",
            "static_dir",
            "rust_manifest",
            "java_source",
            "calendar_workspace",
        }:
            raise ValueError(f"Unsupported site section kind: {self.kind}")
        if not self.source.exists():
            raise ValueError(f"Source path does not exist: {self.source}")


def markdown_to_html(markdown_text: str) -> str:
    """Render minimal Markdown (headings and paragraphs) into HTML."""
    html_lines: List[str] = []
    for raw_line in markdown_text.splitlines():
        line = raw_line.strip()
        if not line:
            html_lines.append("<p></p>")
            continue
        if line.startswith("#"):
            level = len(line) - len(line.lstrip("#"))
            content = line.lstrip("#").strip()
            level = min(level, 6)
            html_lines.append(f"<h{level}>{html.escape(content)}</h{level}>")
            continue
        html_lines.append(f"<p>{html.escape(line)}</p>")
    if not html_lines:
        html_lines.append("<p></p>")
    return "\n".join(html_lines)


def write_html_page(title: str, body_html: str, output_path: Path, nav_links: Iterable[tuple[str, str]]) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    nav_markup = "\n".join(
        f'<li><a href="{href}">{html.escape(link_title)}</a></li>' for link_title, href in nav_links
    )
    skeleton = f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{html.escape(title)}</title>
    <style>
      body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 1.5rem; }}
      nav ul {{ list-style: none; padding: 0; display: flex; flex-wrap: wrap; gap: 0.75rem; }}
      nav a {{ text-decoration: none; color: #0a5ddb; }}
      nav a:hover {{ text-decoration: underline; }}
      pre {{ background: #f8f8f8; padding: 1rem; overflow-x: auto; }}
      code {{ background: #f0f0f0; padding: 0.2rem 0.4rem; }}
      .card {{ border: 1px solid #e0e0e0; border-radius: 8px; padding: 1rem; margin-bottom: 1rem; }}
    </style>
  </head>
  <body>
    <nav>
      <ul>
        {nav_markup}
      </ul>
    </nav>
    <main>
      <h1>{html.escape(title)}</h1>
      {body_html}
    </main>
  </body>
</html>
"""
    output_path.write_text(skeleton, encoding="utf-8")
    return output_path


def _render_calendar_workspace(section: SiteSection, output_path: Path, nav_links: Iterable[tuple[str, str]]) -> Path:
    teamconfig = section.source / "teamconfig.json"
    meetings_root = section.source / "meetings"
    details: List[str] = []
    if teamconfig.exists():
        config = json.loads(teamconfig.read_text(encoding="utf-8"))
        agent_count = len(config.get("agents", []))
        details.append(f"<p>Team configuration lists <strong>{agent_count}</strong> agents.</p>")
    if meetings_root.exists():
        meetings = sorted([path.name for path in meetings_root.iterdir() if path.is_dir()])
        preview = ", ".join(meetings[:5]) if meetings else "None yet"
        details.append(f"<p>Meetings available: {len(meetings)} (showing: {html.escape(preview)})</p>")
    body_html = "\n".join(details) or "<p>No CalendarApp workspace details found.</p>"
    return write_html_page(section.title, body_html, output_path, nav_links)


def _render_rust_manifest(section: SiteSection, output_path: Path, nav_links: Iterable[tuple[str, str]]) -> Path:
    if tomllib is None:
        raise RuntimeError("tomllib is required to read the Rust client manifest")
    manifest = tomllib.loads(section.source.read_text(encoding="utf-8"))
    package = manifest.get("package", {})
    name = package.get("name", "rust_client")
    version = package.get("version", "unknown")
    authors = ", ".join(package.get("authors", []))
    deps = manifest.get("dependencies", {})
    if deps:
        deps_list = "".join(f"<li>{html.escape(key)}: {html.escape(str(value))}</li>" for key, value in deps.items())
        deps_html = f"<ul>{deps_list}</ul>"
    else:
        deps_html = "<p>No dependencies listed.</p>"
    body_html = "\n".join(
        [
            f"<p>Package: <strong>{html.escape(name)}</strong></p>",
            f"<p>Version: {html.escape(version)}</p>",
            f"<p>Authors: {html.escape(authors or 'Not specified')}</p>",
            "<div class='card'><h2>Dependencies</h2>" + deps_html + "</div>",
        ]
    )
    return write_html_page(section.title, body_html, output_path, nav_links)


def _render_java_source(section: SiteSection, output_path: Path, nav_links: Iterable[tuple[str, str]]) -> Path:
    java_files = sorted(section.source.glob("*.java"))
    if not java_files:
        body_html = "<p>No Java sources found.</p>"
        return write_html_page(section.title, body_html, output_path, nav_links)
    cards: List[str] = []
    for java_file in java_files:
        content = java_file.read_text(encoding="utf-8")
        class_line = next((line for line in content.splitlines() if "class " in line), "class details unavailable")
        cards.append(
            "<div class='card'>"
            f"<h2>{html.escape(java_file.name)}</h2>"
            f"<pre>{html.escape(class_line.strip())}</pre>"
            "</div>"
        )
    body_html = "\n".join(cards)
    return write_html_page(section.title, body_html, output_path, nav_links)


def _render_markdown(section: SiteSection, output_path: Path, nav_links: Iterable[tuple[str, str]]) -> Path:
    markdown_html = markdown_to_html(section.source.read_text(encoding="utf-8"))
    description_html = f"<p>{html.escape(section.description)}</p>" if section.description else ""
    return write_html_page(section.title, description_html + markdown_html, output_path, nav_links)


def _copy_static_dir(section: SiteSection, output_root: Path) -> Path:
    destination_dir = output_root / section.destination
    if destination_dir.exists():
        shutil.rmtree(destination_dir)
    shutil.copytree(section.source, destination_dir)
    return destination_dir


DEFAULT_SECTIONS: List[SiteSection] = [
    SiteSection(
        title="Project Overview",
        source=Path("README.md"),
        kind="markdown",
        destination=Path("project/index.html"),
        description="High-level overview of Big Daisy Swarm.",
    ),
    SiteSection(
        title="User Guide",
        source=Path("userguide.md"),
        kind="markdown",
        destination=Path("project/userguide/index.html"),
        description="User guide for getting started with the platform.",
    ),
    SiteSection(
        title="Calendar CLI Client",
        source=Path("calendar_cli_client/userguide.md"),
        kind="markdown",
        destination=Path("calendar_cli_client/index.html"),
        description="Command line client for interacting with calendar data.",
    ),
    SiteSection(
        title="Web Client",
        source=Path("web_client"),
        kind="static_dir",
        destination=Path("web_client"),
        description="Static assets for the Calendar web client.",
    ),
    SiteSection(
        title="Rust Client",
        source=Path("rust_client/Cargo.toml"),
        kind="rust_manifest",
        destination=Path("rust_client/index.html"),
        description="Rust client metadata and dependencies.",
    ),
    SiteSection(
        title="Swing Client",
        source=Path("swing/src/calendarapp/swing"),
        kind="java_source",
        destination=Path("swing/index.html"),
        description="Swing desktop client sources.",
    ),
    SiteSection(
        title="CalendarApp Workspace",
        source=Path("CalendarApp"),
        kind="calendar_workspace",
        destination=Path("CalendarApp/index.html"),
        description="CalendarApp meetings and team configuration summary.",
    ),
]


def build_site(output_root: Path, sections: Iterable[SiteSection] | None = None) -> list[Path]:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    selected_sections = list(sections) if sections is not None else DEFAULT_SECTIONS
    for section in selected_sections:
        section.validate()
    nav_links = [(section.title, str(section.destination)) for section in selected_sections]

    produced: list[Path] = []
    for section in selected_sections:
        output_path = output_root / section.destination
        if section.kind == "markdown":
            produced.append(_render_markdown(section, output_path, nav_links))
        elif section.kind == "static_dir":
            produced.append(_copy_static_dir(section, output_root))
        elif section.kind == "rust_manifest":
            produced.append(_render_rust_manifest(section, output_path, nav_links))
        elif section.kind == "java_source":
            produced.append(_render_java_source(section, output_path, nav_links))
        elif section.kind == "calendar_workspace":
            produced.append(_render_calendar_workspace(section, output_path, nav_links))
    index_links = "\n".join(
        f'<li><a href="{href}">{html.escape(title)}</a> — {html.escape(section.description)}</li>'
        for title, href, section in zip(
            [section.title for section in selected_sections],
            [str(section.destination) for section in selected_sections],
            selected_sections,
        )
    )
    index_body = f"<ul>{index_links}</ul>"
    write_html_page("Big Daisy Swarm Pages", index_body, output_root / "index.html", nav_links)
    (output_root / ".nojekyll").write_text("", encoding="utf-8")
    return produced


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build GitHub Pages site for Big Daisy Swarm and subprojects.")
    parser.add_argument("--output", type=Path, default=Path("public"), help="Output directory for generated pages.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_site(args.output)


if __name__ == "__main__":
    main()
