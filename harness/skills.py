"""
Shared skill and persona loading logic.
Used by both the CLI (cli.py) and the REST API (api/rest.py).

Skill discovery priority (high → low):
  1. .myharness/skills/         — project-installed
  2. ~/.myharness/skills/       — user-global installed
  3. .claude/skills/            — Claude Code ecosystem compat
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml


# ── Paths ─────────────────────────────────────────────────────────────

SKILLS_DIR         = Path(".myharness/skills")   # where skill CRUD writes to
PERSONAS_DIR       = Path(".myharness/personas")

def _get_skill_scan_dirs() -> list[tuple[Path, str]]:
    """Return [(directory, source_label), ...] in priority order."""
    home = Path(os.environ.get("HOME", os.environ.get("USERPROFILE", "~")))

    return [
        (Path(".myharness/skills"), "project"),
        (home / ".myharness" / "skills", "global"),
        (Path(".claude/skills"), "project-claude"),
        (home / ".claude" / "skills", "global-claude"),
    ]


# ── Persona helpers ────────────────────────────────────────────────────

def parse_persona_md(path: Path) -> dict[str, Any]:
    """Parse YAML frontmatter + Markdown body from a persona file.

    Returns dict with: name, description, system_prompt, allowed_tools, provider.
    Legacy files (no frontmatter) are treated as pure system-prompt text.
    """
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if m:
        meta: dict[str, Any] = yaml.safe_load(m.group(1)) or {}
        meta["system_prompt"] = m.group(2).strip()
    else:
        meta = {"system_prompt": text.strip()}
    meta.setdefault("name", path.stem)
    meta.setdefault("description", "")
    meta.setdefault("allowed_tools", None)
    meta.setdefault("provider", "")
    return meta


def load_persona(name: str) -> dict[str, Any]:
    """Load personas/{name}.md -> dict with system_prompt, allowed_tools, etc."""
    md = PERSONAS_DIR / f"{name}.md"
    if not md.exists():
        available = [p["name"] for p in list_personas()]
        raise ValueError(
            f"Persona '{name}' not found. "
            f"Available: {available}. "
            f"Create: personas/{name}.md"
        )
    return parse_persona_md(md)


def list_personas() -> list[dict[str, str]]:
    """Return sorted list of {name, description} dicts (excludes README)."""
    if not PERSONAS_DIR.exists():
        return []
    results = []
    for p in sorted(PERSONAS_DIR.glob("*.md")):
        if p.stem.upper() == "README":
            continue
        try:
            meta = parse_persona_md(p)
            results.append({
                "name":        str(meta.get("name") or p.stem),
                "description": str(meta.get("description", "")),
            })
        except Exception:
            results.append({"name": p.stem, "description": ""})
    return results


# ── Skill helpers (folder-based) ───────────────────────────────────────

def parse_skill_md(path: Path) -> dict[str, Any]:
    """Parse a YAML-frontmatter + Markdown-body skill file (SKILL.md)."""
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", text, re.DOTALL)
    if not m:
        raise ValueError(
            f"{path.name}: missing frontmatter. "
            "File must start with --- markers. See skills/template/SKILL.md."
        )
    meta: dict[str, Any] = yaml.safe_load(m.group(1)) or {}
    body = m.group(2).strip()
    meta["system_prompt"] = body
    meta.setdefault("_source_file", str(path))
    return meta


def load_skill(name: str) -> dict[str, Any]:
    """Load a skill by name, searching all directories in priority order.

    Priority: .myharness/skills/ > ~/.myharness/skills/ > .claude/skills/

    For each directory, looks for ``{name}/SKILL.md`` first, then ``{name}.md`` (legacy).
    """
    for scan_dir, source in _get_skill_scan_dirs():
        if not scan_dir.exists():
            continue

        # Folder-based: {dir}/{name}/SKILL.md
        folder_md = scan_dir / name / "SKILL.md"
        if folder_md.exists():
            meta = parse_skill_md(folder_md)
            meta.setdefault("_source", source)
            return meta

        # Legacy flat: {dir}/{name}.md
        legacy_md = scan_dir / f"{name}.md"
        if legacy_md.exists():
            meta = parse_skill_md(legacy_md)
            meta.setdefault("_source", source)
            return meta

    available = [s["name"] for s in list_skills()]
    raise ValueError(
        f"Skill '{name}' not found. "
        f"Available: {available}. "
        f"Create: .myharness/skills/{name}/SKILL.md"
    )


def load_skill_content(name: str) -> str:
    """Return the instruction body (markdown) of a skill."""
    return load_skill(name).get("system_prompt", "")


def _scan_skill_dir(scan_dir: Path, source: str) -> list[dict[str, Any]]:
    """Scan a single directory for skills, returning [{name, description, source}, ...]."""
    results: list[dict[str, Any]] = []
    if not scan_dir.exists():
        return results

    # Folder-based skills (each subfolder with SKILL.md)
    for item in sorted(scan_dir.iterdir()):
        if not item.is_dir() or item.name.startswith(".") or item.name == "template":
            continue
        skill_md = item / "SKILL.md"
        if skill_md.exists():
            try:
                meta = parse_skill_md(skill_md)
                results.append({
                    "name":        str(meta.get("name") or item.name),
                    "description": str(meta.get("description", "")),
                    "source":      source,
                })
            except Exception:
                pass

    # Legacy flat .md files
    for md_file in sorted(scan_dir.glob("*.md")):
        if md_file.stem == "template":
            continue
        try:
            meta = parse_skill_md(md_file)
            results.append({
                "name":        str(meta.get("name") or md_file.stem),
                "description": str(meta.get("description", "")),
                "source":      source,
            })
        except Exception:
            pass

    return results


def list_skills() -> list[dict[str, str]]:
    """Return [{name, description, source}] for all skills across all directories.

    Sources: "system" (built-in), "project" (.myharness/), "global" (~/.myharness/),
    "claude" (.claude/ compat).

    Higher-priority directories override lower-priority skills with the same name.
    """
    seen: set[str] = set()
    results: list[dict[str, str]] = []

    # Scan in priority order, skip seen names (first match = highest priority)
    for scan_dir, source in _get_skill_scan_dirs():
        for entry in _scan_skill_dir(scan_dir, source):
            if entry["name"] in seen:
                continue
            seen.add(entry["name"])
            results.append(entry)

    return results


def build_skill_system_addendum(skills: list[dict[str, str]]) -> str:
    """Build text appended to system prompt listing available skills.

    Skill descriptions let the agent decide when to call use_skill().
    Full skill content is only loaded on demand.
    """
    if not skills:
        return ""
    lines = [
        "",
        "## Skills (Workflow Presets)",
        "Skills are predefined workflow instructions, NOT executable tools.",
        "A skill tells you *how* to approach a certain type of task.",
        "To activate a skill, call the `use_skill` function tool with the skill name.",
        "Your actual executable tools (read_file, shell, web_search, etc.) are",
        "listed separately in your function-calling interface.",
        "",
    ]
    for s in skills:
        lines.append(f"- **{s['name']}**: {s.get('description', '')}")
    return "\n".join(lines)


# ── Config file read/write ─────────────────────────────────────────────

def read_file_safe(path: Path) -> str:
    """Read a text file; return empty string if not found."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_file_safe(path: Path, content: str) -> None:
    """Write content to path, creating parent dirs as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
