from pathlib import Path

import pytest

from automation import DEFAULT_SECTIONS, SiteSection, build_site, markdown_to_html


def test_markdown_to_html_parses_headings_and_paragraphs():
    html = markdown_to_html("# Title\n\nContent line\n## Subheading\nMore text")
    assert "<h1>Title</h1>" in html
    assert "<h2>Subheading</h2>" in html
    assert html.count("<p>") >= 2


def test_site_section_validation_rejects_missing_or_unknown(tmp_path):
    missing_source = SiteSection(
        title="Missing",
        source=tmp_path / "missing.md",
        kind="markdown",
        destination=Path("missing/index.html"),
    )
    with pytest.raises(ValueError):
        missing_source.validate()

    existing = tmp_path / "existing.md"
    existing.write_text("ok", encoding="utf-8")
    unknown_kind = SiteSection(
        title="Unknown",
        source=existing,
        kind="unsupported",
        destination=Path("unknown/index.html"),
    )
    with pytest.raises(ValueError):
        unknown_kind.validate()


def test_build_site_supports_multiple_section_types(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()

    markdown_file = sources / "doc.md"
    markdown_file.write_text("# Hello\nParagraph", encoding="utf-8")

    static_dir = sources / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<p>Static</p>", encoding="utf-8")

    rust_manifest = sources / "Cargo.toml"
    rust_manifest.write_text(
        "[package]\nname = \"demo\"\nversion = \"0.1.0\"\nauthors = [\"Example <example@example.com>\"]\n"
        "[dependencies]\nserde = \"1.0\"\n",
        encoding="utf-8",
    )

    java_dir = sources / "java"
    java_dir.mkdir()
    (java_dir / "Example.java").write_text("public class Example { }", encoding="utf-8")

    workspace = sources / "CalendarApp"
    workspace.mkdir()
    teamconfig = workspace / "teamconfig.json"
    teamconfig.write_text('{"agents": [{"id": "A", "type": "Architect"}]}', encoding="utf-8")
    meetings = workspace / "meetings"
    meetings.mkdir()
    (meetings / "0001-demo").mkdir()

    sections = [
        SiteSection("Doc", markdown_file, "markdown", Path("docs/index.html")),
        SiteSection("Static", static_dir, "static_dir", Path("static")),
        SiteSection("Rust", rust_manifest, "rust_manifest", Path("rust/index.html")),
        SiteSection("Java", java_dir, "java_source", Path("java/index.html")),
        SiteSection("Workspace", workspace, "calendar_workspace", Path("workspace/index.html")),
    ]

    output = tmp_path / "site"
    produced = build_site(output, sections)

    assert (output / ".nojekyll").exists()
    assert (output / "index.html").exists()
    assert (output / "docs/index.html").read_text(encoding="utf-8").startswith("<!doctype html>")
    assert (output / "static/index.html").read_text(encoding="utf-8") == "<p>Static</p>"
    rust_page = (output / "rust/index.html").read_text(encoding="utf-8")
    assert "demo" in rust_page and "serde" in rust_page
    java_page = (output / "java/index.html").read_text(encoding="utf-8")
    assert "Example.java" in java_page
    workspace_page = (output / "workspace/index.html").read_text(encoding="utf-8")
    assert "Meetings available: 1" in workspace_page
    assert produced, "Expected build_site to return produced outputs"


def test_default_sections_target_existing_paths():
    for section in DEFAULT_SECTIONS:
        assert section.source.exists(), f"{section.source} missing for section {section.title}"


def test_build_site_handles_rebuilds_and_empty_java_directory(tmp_path):
    sources = tmp_path / "sources"
    sources.mkdir()

    static_dir = sources / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<p>Static</p>", encoding="utf-8")

    empty_java_dir = sources / "java"
    empty_java_dir.mkdir()

    sections = [
        SiteSection("Static", static_dir, "static_dir", Path("static")),
        SiteSection("Java", empty_java_dir, "java_source", Path("java/index.html")),
    ]

    output = tmp_path / "site"
    build_site(output, sections)
    # Rebuild to ensure the static directory gets refreshed without errors
    (output / "static" / "stale.txt").write_text("remove me", encoding="utf-8")
    build_site(output, sections)

    java_page = (output / "java/index.html").read_text(encoding="utf-8")
    assert "No Java sources found." in java_page
    assert not (output / "static/stale.txt").exists()
