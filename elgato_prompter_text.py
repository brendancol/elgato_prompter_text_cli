#!/usr/bin/env python3
"""
elgato-prompter-text: Manage a directory of teleprompter JSON files.

Mostly vibe-coded :()

Close the CameraHub App when running this...
Set the ELGATO_PROMPTER_DIR environment variable
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Tuple, Dict, Any


from pydantic_ai import Agent


DEFAULT_DIR = Path.cwd()  # override with --dir or $ELGATO_PROMPTER_DIR
ENV_DIR = os.environ.get("ELGATO_PROMPTER_DIR")

SETTINGS_KEY = "applogic.prompter.libraryList"


def slugify(value: str, max_len: int = 48) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    value = value.strip("-")
    if len(value) > max_len:
        value = value[:max_len].rstrip("-")
    return value or "prompt"


def read_lines(path: Path) -> List[str]:
    with path.open("r", encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def iter_prompt_files(dir_path: Path) -> Iterable[Path]:
    yield from sorted(dir_path.glob("*.json"))


def load_prompt(path: Path) -> Optional[dict]:
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        required = {"GUID", "chapters", "friendlyName", "index"}
        if not required.issubset(data):
            return None
        return data
    except Exception:
        return None


def next_index(dir_path: Path) -> int:
    max_idx = 0
    for p in iter_prompt_files(dir_path):
        data = load_prompt(p)
        if not data:
            continue
        try:
            i = int(data.get("index", 0))
            if i > max_idx:
                max_idx = i
        except Exception:
            continue
    return max_idx + 1


def ensure_dir(dir_path: Path) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)


def choose_dir(cli_dir: Optional[str]) -> Path:
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    if ENV_DIR:
        return Path(ENV_DIR).expanduser().resolve()
    return DEFAULT_DIR.resolve()


def generate_guid() -> str:
    return str(uuid.uuid4()).upper()


# ---------- AppSettings helpers (one directory up from Texts dir) ----------

def get_appsettings_path(texts_dir: Path) -> Path:
    # AppSettings.json lives at parent of the Texts directory
    return (texts_dir.parent / "AppSettings.json").resolve()


def load_settings(settings_path: Path) -> Dict[str, Any]:
    if not settings_path.exists():
        return {}
    with settings_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
        if isinstance(data, dict):
            return data
        return {}

def save_settings(settings_path: Path, data: Dict[str, Any]) -> None:
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = settings_path.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    tmp.replace(settings_path)


def settings_add_guid(texts_dir: Path, guid: str) -> Path:
    spath = get_appsettings_path(texts_dir)
    settings = load_settings(spath)
    lst = settings.get(SETTINGS_KEY)
    if not isinstance(lst, list):
        lst = []
    guid_up = guid.upper()
    if guid_up not in lst:
        lst.append(guid_up)
    settings[SETTINGS_KEY] = lst
    save_settings(spath, settings)
    return spath


def settings_remove_guids(texts_dir: Path, guids: List[str]) -> Path:
    spath = get_appsettings_path(texts_dir)
    settings = load_settings(spath)
    lst = settings.get(SETTINGS_KEY)
    if not isinstance(lst, list):
        lst = []
    to_remove = {g.upper() for g in guids}
    lst = [g for g in lst if str(g).upper() not in to_remove]
    settings[SETTINGS_KEY] = lst
    save_settings(spath, settings)
    return spath


# ----------------------------- CLI datatypes -------------------------------

@dataclass
class AddArgs:
    friendly_name: str
    chapters: List[str]
    index: Optional[int]
    guid: Optional[str]
    dir: Path
    dry_run: bool


@dataclass
class DelArgs:
    guid: Optional[str]
    friendly_name: Optional[str]
    filename: Optional[str]
    dir: Path
    yes: bool


@dataclass
class LsArgs:
    dir: Path
    columns: List[str]
    sort: str
    reverse: bool
    limit: Optional[int]
    pandas: bool
    show_chapters: bool


# ----------------------------- File helpers --------------------------------

def write_prompt_file(dir_path: Path, data: dict) -> Path:
    slug = slugify(str(data["friendlyName"]))
    idx = int(data["index"])
    guid = str(data["GUID"]).upper()
    filename = f"{guid}.json"
    out_path = dir_path / filename
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")
    return out_path


def find_matches(dir_path: Path, guid: Optional[str], friendly_name: Optional[str], filename: Optional[str]) -> List[Tuple[Path, dict]]:
    matches = []
    guid_norm = guid.upper() if guid else None
    filename_norm = filename if filename else None
    name_norm = friendly_name.strip().lower() if friendly_name else None

    for p in iter_prompt_files(dir_path):
        data = load_prompt(p)
        if not data:
            continue
        ok = False
        if guid_norm and str(data.get("GUID", "")).upper() == guid_norm:
            ok = True
        if filename_norm and p.name == filename_norm:
            ok = True
        if name_norm and str(data.get("friendlyName", "")).strip().lower() == name_norm:
            ok = True
        if ok:
            matches.append((p, data))
    return matches


# ----------------------------- Subcommands ---------------------------------

def cmd_add(a: AddArgs) -> int:
    ensure_dir(a.dir)

    chapters = a.chapters
    if not chapters:
        print("ERROR: You must provide at least one chapter (use --chapter, --chapters-file, or --from-stdin).", file=sys.stderr)
        return 2

    idx = a.index if a.index is not None else next_index(a.dir)
    guid = (a.guid or generate_guid()).upper()

    data = {
        "GUID": guid,
        "chapters": chapters,
        "friendlyName": a.friendly_name,
        "index": int(idx),
    }

    if a.dry_run:
        print(json.dumps(data, indent=4, ensure_ascii=False))
        return 0

    out_path = write_prompt_file(a.dir, data)
    # Update AppSettings.json one directory up
    spath = settings_add_guid(a.dir, guid)
    print(f"Created: {out_path}")
    print(f"Updated AppSettings: {spath}  (+{guid})")
    return 0


def cmd_del(a: DelArgs) -> int:
    ensure_dir(a.dir)

    if not (a.guid or a.friendly_name or a.filename):
        print("ERROR: Provide one of --guid, --name, or --file to delete.", file=sys.stderr)
        return 2

    matches = find_matches(a.dir, a.guid, a.friendly_name, a.filename)
    if not matches:
        print("No matching prompts found.")
        return 1

    if a.friendly_name:
        unique_names = {d.get("friendlyName") for _, d in matches}
        if len(matches) > 1 and len(unique_names) > 1 and not a.yes:
            print("Multiple prompts share that name. Re-run with --yes to delete all matches or delete by --guid/--file.", file=sys.stderr)
            for p, d in matches:
                print(f"  {p.name}  index={d.get('index')}  GUID={d.get('GUID')}  name={d.get('friendlyName')}")
            return 3

    deleted = 0
    removed_guids: List[str] = []
    for p, d in matches:
        try:
            p.unlink()
            g = str(d.get("GUID", "")).upper()
            print(f"Deleted: {p.name}  (GUID={g}, index={d.get('index')}, name={d.get('friendlyName')})")
            deleted += 1
            if g:
                removed_guids.append(g)
        except Exception as e:
            print(f"ERROR deleting {p.name}: {e}", file=sys.stderr)

    # Reflect deletions in AppSettings.json
    if removed_guids:
        spath = settings_remove_guids(a.dir, removed_guids)
        print(f"Updated AppSettings: {spath}  (-{', '.join(removed_guids)})")

    return 0 if deleted else 1


def _collect_rows(dir_path: Path, include_chapters: bool) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for p in iter_prompt_files(dir_path):
        data = load_prompt(p)
        if not data:
            continue
        row: Dict[str, Any] = {
            "file": p.name,
            "index": int(data.get("index", 0)),
            "friendlyName": data.get("friendlyName", ""),
            "GUID": str(data.get("GUID", "")).upper(),
            "chaptersCount": len(data.get("chapters", [])),
        }
        if include_chapters:
            row["chapters"] = " | ".join(map(str, data.get("chapters", [])))
        rows.append(row)
    return rows


def _print_table_pandas(rows: List[Dict[str, Any]], columns: List[str], sort: str, reverse: bool, limit: Optional[int]) -> int:
    try:
        import pandas as pd  # type: ignore
    except Exception:
        print("pandas is not installed. Install with `pip install pandas` or omit --pandas.", file=sys.stderr)
        return 2

    if not rows:
        print("No prompts found.")
        return 0

    df = pd.DataFrame(rows)
    if columns:
        missing = [c for c in columns if c not in df.columns]
        if missing:
            print(f"Unknown column(s): {', '.join(missing)}", file=sys.stderr)
            return 2
        df = df[columns]
    else:
        default_cols = [c for c in ["index", "friendlyName", "GUID", "chaptersCount", "file", "chapters"] if c in df.columns]
        df = df[default_cols]

    if sort:
        if sort not in df.columns:
            print(f"Unknown sort column: {sort}", file=sys.stderr)
            return 2
        df = df.sort_values(by=sort, ascending=not reverse, kind="mergesort")

    if limit is not None:
        df = df.head(limit)

    with pd.option_context("display.max_colwidth", 200, "display.width", 160):
        print(df.to_string(index=False))
    return 0


def _print_table_plain(rows: List[Dict[str, Any]], columns: List[str], sort: str, reverse: bool, limit: Optional[int]) -> int:
    if not rows:
        print("No prompts found.")
        return 0

    cols = columns if columns else ["index", "friendlyName", "GUID", "chaptersCount", "file"]
    if any("chapters" in r for r in rows) and "chapters" not in cols:
        cols.append("chapters")

    if sort:
        try:
            rows.sort(key=lambda r: r.get(sort, ""), reverse=reverse)
        except Exception:
            print(f"Unable to sort by {sort}", file=sys.stderr)

    if limit is not None:
        rows = rows[:limit]

    def cell(v: Any) -> str:
        return "" if v is None else str(v)

    widths = {c: max(len(c), *(len(cell(r.get(c))) for r in rows)) for c in cols}
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    sep = "  ".join("-" * widths[c] for c in cols)
    print(header)
    print(sep)
    for r in rows:
        print("  ".join(cell(r.get(c)).ljust(widths[c]) for c in cols))
    return 0


def cmd_ls(a: LsArgs) -> int:
    ensure_dir(a.dir)
    rows = _collect_rows(a.dir, include_chapters=a.show_chapters)
    if a.pandas:
        return _print_table_pandas(rows, a.columns, a.sort, a.reverse, a.limit)
    try:
        import pandas as _pd  # noqa: F401
        return _print_table_pandas(rows, a.columns, a.sort, a.reverse, a.limit)
    except Exception:
        return _print_table_plain(rows, a.columns, a.sort, a.reverse, a.limit)



# Define the agent with your chosen model
agent = Agent("openai:gpt-4o-mini")

# Define a function that uses the agent to generate the script
def gen_prompter_script(topic: str) -> str:
    result = agent.run_sync(
        f"""Write a short script with some decent talking points for the following topic: {topic}

         ## NOTE
         -------
         - The content will be displayed on the Elgato Prompter which uses newlines the delineate chapters.
         - Don't use markdown because the Elgato Prompter just uses unicode
        """
    )
    return result.output

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="elgato-prompter-text",
        description="Manage Elgato Prompter JSON scripts.",
    )
    p.add_argument("--dir", help="Directory for prompt JSON files (default: $ELGATO_PROMPTER_DIR or current directory)")
    sub = p.add_subparsers(dest="cmd", required=True)

    # add
    a = sub.add_parser("add", help="Create a new prompt JSON file")
    a.add_argument("--name", required=True, help="friendlyName for the prompt")
    a.add_argument("--chapter", action="append", default=[], help="Add a chapter (repeat for multiple)")
    a.add_argument("--chapters-file", type=str, help="Path to a text file, one chapter per line")
    a.add_argument("--from-stdin", action="store_true", help="Read chapters from stdin (one chapter per line)")
    a.add_argument("--index", type=int, help="Index value; defaults to (max existing index + 1)")
    a.add_argument("--guid", type=str, help="Use a specific GUID instead of generating one")
    a.add_argument("--dry-run", action="store_true",
                   help="Print JSON to stdout without writing a file")

    # del
    d = sub.add_parser("del", help="Delete prompt JSON file(s)")
    d.add_argument("--guid", help="Delete by GUID")
    d.add_argument("--name", help="Delete by exact friendlyName (case-insensitive)")
    d.add_argument("--file", help="Delete by exact filename in the directory")
    d.add_argument("-y", "--yes", action="store_true", help="Do not ask for confirmation when multiple matches")

    # gen
    g = sub.add_parser("gen", help="Generate and add a new prompt script using LLM")
    g.add_argument("topic", help="Topic for the generated prompt script")
    
    # ls
    l = sub.add_parser("ls", help="List prompt JSON files as a table")
    l.add_argument("--columns", nargs="+", default=[], help="Subset/reorder columns (e.g. --columns index friendlyName GUID)")
    l.add_argument("--sort", default="index", help="Column to sort by (default: index)")
    l.add_argument("--reverse", action="store_true", help="Reverse sort order")
    l.add_argument("--limit", type=int, help="Limit number of rows")
    l.add_argument("--pandas", action="store_true", help="Force using pandas (error if not installed)")
    l.add_argument("--show-chapters", action="store_true", help="Include a 'chapters' column (joined with ' | ')")

    return p

from restarter import AppRestarter


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    ns = parser.parse_args(argv)
    dir_path = choose_dir(ns.dir)

    if ns.cmd == "add":

        with AppRestarter("Camera Hub"):
            chapters: List[str] = []
            chapters.extend(ns.chapter or [])
            if ns.chapters_file:
                chapters.extend(read_lines(Path(ns.chapters_file)))
            if ns.from_stdin:
                stdin_lines = [line.rstrip("\n") for line in sys.stdin if line.strip()]
                chapters.extend(stdin_lines)

            args = AddArgs(
                friendly_name=ns.name,
                chapters=chapters,
                index=ns.index,
                guid=ns.guid,
                dir=dir_path,
                dry_run=ns.dry_run,
            )
            return cmd_add(args)

    elif ns.cmd == "del":
        with AppRestarter("Camera Hub"):
            args = DelArgs(
                guid=ns.guid,
                friendly_name=ns.name,
                filename=ns.file,
                dir=dir_path,
                yes=ns.yes,
            )
            return cmd_del(args)

    elif ns.cmd == "ls":
        args = LsArgs(
            dir=dir_path,
            columns=ns.columns,
            sort=ns.sort,
            reverse=ns.reverse,
            limit=ns.limit,
            pandas=ns.pandas,
            show_chapters=ns.show_chapters,
        )
        return cmd_ls(args)

    elif ns.cmd == "gen":
        with AppRestarter("Camera Hub"):
            # Generate prompt script using LLM
            script = gen_prompter_script(str(ns.topic))
            
            chapters = [line for line in script.split("\n") if line.strip()]
            args = AddArgs(
                friendly_name=f"Generated prompt for {ns.topic}",
                chapters=chapters,
                index=None,
                guid=None,
                dir=choose_dir(ns.dir),
                dry_run=False
            )
            return cmd_add(args)
    else:
        parser.print_help()
        return 2


if __name__ == "__main__":
    sys.exit(main())
