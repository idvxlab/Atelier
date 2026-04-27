#!/usr/bin/env python3
"""
LOC (Lines of Code) counter for MyHarnessPy.

Usage:
    python scripts/loc.py              # table by module
    python scripts/loc.py --csv        # CSV output
    python scripts/loc.py --sort size  # sort by line count (default: path)
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).parent.parent
INCLUDE_GLOBS = ["harness/**/*.py", "api/**/*.py", "tests/**/*.py",
                 "scripts/**/*.py", "static/**/*.html", "static/**/*.js"]
EXCLUDE_DIRS  = {"__pycache__", ".git", "*.egg-info", "node_modules"}


# ── Counting ──────────────────────────────────────────────────────────────────

@dataclass
class FileStats:
    path: Path
    total: int = 0
    code:  int = 0      # non-blank, non-comment
    blank: int = 0
    comment: int = 0


def count_py(path: Path) -> FileStats:
    s = FileStats(path)
    in_docstring = False
    dq = '"""'
    sq = "'''"
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s.total += 1
        line = raw.strip()
        if not line:
            s.blank += 1
            continue
        # crude docstring toggle (good enough for counting purposes)
        if dq in line or sq in line:
            delim = dq if dq in line else sq
            opens = line.count(delim)
            if in_docstring:
                in_docstring = opens % 2 == 0   # even → closed
                s.comment += 1
                continue
            else:
                if opens >= 2:           # opens and closes on same line
                    s.comment += 1
                    continue
                in_docstring = True
                s.comment += 1
                continue
        if in_docstring:
            s.comment += 1
            continue
        if line.startswith("#"):
            s.comment += 1
        else:
            s.code += 1
    return s


def count_html(path: Path) -> FileStats:
    s = FileStats(path)
    in_comment = False
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s.total += 1
        line = raw.strip()
        if not line:
            s.blank += 1
            continue
        if in_comment:
            s.comment += 1
            if "-->" in line:
                in_comment = False
            continue
        if "<!--" in line:
            s.comment += 1
            if "-->" not in line:
                in_comment = True
            continue
        s.code += 1
    return s


def count_file(path: Path) -> FileStats:
    if path.suffix == ".py":
        return count_py(path)
    return count_html(path)


# ── Grouping ──────────────────────────────────────────────────────────────────

def module_of(path: Path) -> str:
    """Return a short module label like 'harness/engine' or 'api'."""
    rel = path.relative_to(ROOT)
    parts = rel.parts
    if len(parts) <= 2:
        return parts[0]
    return "/".join(parts[:2])


@dataclass
class ModuleStats:
    name: str
    files: int = 0
    total: int = 0
    code: int  = 0
    blank: int = 0
    comment: int = 0
    file_list: list[FileStats] = field(default_factory=list)

    def add(self, fs: FileStats) -> None:
        self.files   += 1
        self.total   += fs.total
        self.code    += fs.code
        self.blank   += fs.blank
        self.comment += fs.comment
        self.file_list.append(fs)


# ── Collection ────────────────────────────────────────────────────────────────

def collect(sort_by: str) -> tuple[list[ModuleStats], FileStats]:
    modules: dict[str, ModuleStats] = {}
    grand = FileStats(ROOT)

    paths: list[Path] = []
    for glob in INCLUDE_GLOBS:
        for p in ROOT.glob(glob):
            # skip excluded dirs
            if any(ex in p.parts for ex in EXCLUDE_DIRS):
                continue
            if p not in paths:
                paths.append(p)

    for path in sorted(paths):
        fs = count_file(path)
        mod = module_of(path)
        if mod not in modules:
            modules[mod] = ModuleStats(mod)
        modules[mod].add(fs)
        grand.total   += fs.total
        grand.code    += fs.code
        grand.blank   += fs.blank
        grand.comment += fs.comment

    mods = list(modules.values())
    if sort_by == "size":
        mods.sort(key=lambda m: -m.code)
    elif sort_by == "name":
        mods.sort(key=lambda m: m.name)
    return mods, grand


# ── Formatting ────────────────────────────────────────────────────────────────

COL = {
    "Module":   22,
    "Files":     5,
    "Total":     7,
    "Code":      7,
    "Blank":     6,
    "Comment":   8,
    "%Code":     7,
}

def hdr() -> str:
    return "  ".join(k.ljust(v) for k, v in COL.items())

def sep() -> str:
    return "  ".join("-" * v for k, v in COL.items())

def row(name: str, files: int, total: int, code: int,
        blank: int, comment: int) -> str:
    pct = f"{code/total*100:.1f}%" if total else "—"
    cells = [name, str(files), str(total), str(code), str(blank), str(comment), pct]
    widths = list(COL.values())
    return "  ".join(c.ljust(w) for c, w in zip(cells, widths))


def print_table(mods: list[ModuleStats], grand: FileStats,
                detail: bool = False) -> None:
    print(hdr())
    print(sep())
    total_files = 0
    for m in mods:
        total_files += m.files
        print(row(m.name, m.files, m.total, m.code, m.blank, m.comment))
        if detail:
            for fs in sorted(m.file_list, key=lambda f: -f.code):
                name = "  " + fs.path.relative_to(ROOT).as_posix()
                pct = f"{fs.code/fs.total*100:.1f}%" if fs.total else "—"
                cells = [name, "", str(fs.total), str(fs.code),
                         str(fs.blank), str(fs.comment), pct]
                widths = list(COL.values())
                print("  ".join(c.ljust(w) for c, w in zip(cells, widths)))
    print(sep())
    print(row("TOTAL", total_files, grand.total, grand.code, grand.blank, grand.comment))


def print_csv(mods: list[ModuleStats], grand: FileStats) -> None:
    w = csv.writer(sys.stdout)
    w.writerow(["module", "files", "total", "code", "blank", "comment", "pct_code"])
    for m in mods:
        pct = f"{m.code/m.total*100:.1f}" if m.total else "0"
        w.writerow([m.name, m.files, m.total, m.code, m.blank, m.comment, pct])
    pct = f"{grand.code/grand.total*100:.1f}" if grand.total else "0"
    w.writerow(["TOTAL", sum(m.files for m in mods),
                grand.total, grand.code, grand.blank, grand.comment, pct])


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description="LOC counter for MyHarnessPy")
    ap.add_argument("--sort",   choices=["name", "size"], default="name",
                    help="Sort modules by name (default) or line count")
    ap.add_argument("--csv",    action="store_true", help="CSV output")
    ap.add_argument("--detail", action="store_true", help="List individual files")
    args = ap.parse_args()

    mods, grand = collect(args.sort)

    if args.csv:
        print_csv(mods, grand)
    else:
        print_table(mods, grand, detail=args.detail)


if __name__ == "__main__":
    main()
