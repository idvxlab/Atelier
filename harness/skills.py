"""
Shared skill and persona loading logic.
Used by both the CLI (cli.py) and the REST API (api/rest.py).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


# ── Paths ─────────────────────────────────────────────────────────────

SKILLS_DIR   = Path("skills")
PERSONAS_DIR = Path("personas")
SKILLS_YAML  = SKILLS_DIR / "skills.yaml"   # kept for legacy compat


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
    """
    Load a skill by name.
    Priority: skills/{name}/SKILL.md  ->  skills/{name}.md (legacy)  ->  ValueError
    """
    folder_md = SKILLS_DIR / name / "SKILL.md"
    if folder_md.exists():
        return parse_skill_md(folder_md)

    legacy_md = SKILLS_DIR / f"{name}.md"
    if legacy_md.exists():
        return parse_skill_md(legacy_md)

    available = [s["name"] for s in list_skills()]
    raise ValueError(
        f"Skill '{name}' not found. "
        f"Available: {available}. "
        f"Create: skills/{name}/SKILL.md"
    )


def load_skill_content(name: str) -> str:
    """Return the instruction body (markdown) of a skill."""
    return load_skill(name).get("system_prompt", "")


def list_skills() -> list[dict[str, str]]:
    """Return [{name, description, source}] for all available skills."""
    results: list[dict[str, str]] = []
    seen: set[str] = set()

    if not SKILLS_DIR.exists():
        return results

    # Folder-based skills (each subfolder with SKILL.md)
    for item in sorted(SKILLS_DIR.iterdir()):
        if item.is_dir() and item.name != "template":
            skill_md = item / "SKILL.md"
            if skill_md.exists():
                try:
                    meta = parse_skill_md(skill_md)
                    name = str(meta.get("name") or item.name)
                    if name in seen:
                        continue
                    seen.add(name)
                    results.append({
                        "name":        name,
                        "description": str(meta.get("description", "")),
                        "source":      "folder",
                    })
                except Exception:
                    pass

    # Legacy single .md files
    for md_file in sorted(SKILLS_DIR.glob("*.md")):
        if md_file.stem == "template":
            continue
        try:
            meta = parse_skill_md(md_file)
            name = str(meta.get("name") or md_file.stem)
            if name in seen:
                continue
            seen.add(name)
            results.append({
                "name":        name,
                "description": str(meta.get("description", "")),
                "source":      "md",
            })
        except Exception:
            pass

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
