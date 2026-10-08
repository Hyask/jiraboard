from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .board import build_board
from .client import JiraClient, JiraError
from .config import ConfigError, read_credentials, resolve_base_url
from .render import write_index, write_report

DEFAULT_BOARDS_FILE = "boards.txt"
DEFAULT_OUTPUT_DIR = "out"


@dataclass(frozen=True)
class Report:
    """One generated (or failed) report, as listed on the index page."""

    key: str
    title: str
    filename: str
    total: int
    generated_at: str
    error: str | None = None


def read_board_keys(path: str | Path) -> list[str]:
    """Read the hard-coded board keys, one per line, ignoring blanks/comments."""
    keys: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key = line.upper()
        if key not in keys:
            keys.append(key)
    return keys


def generate_site(
    client: JiraClient,
    keys: list[str],
    output_dir: str | Path,
    now: datetime | None = None,
) -> list[Report]:
    """Write one self-contained board per key plus an ``index.html``.

    A key that cannot be fetched is recorded on the index with its error rather
    than aborting the rest of the site.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")

    reports: list[Report] = []
    for key in keys:
        filename = f"{key}-board.html"
        try:
            board = build_board(client, key, now=now)
        except JiraError as error:
            reports.append(
                Report(
                    key=key,
                    title=key,
                    filename="",
                    total=0,
                    generated_at=generated_at,
                    error=str(error),
                )
            )
            continue
        write_report(board, output_dir / filename)
        reports.append(
            Report(
                key=key,
                title=board.milestone.summary,
                filename=filename,
                total=board.total,
                generated_at=board.generated_at,
            )
        )

    write_index(reports, output_dir / "index.html")
    (output_dir / ".nojekyll").write_text("", encoding="utf-8")
    return reports


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jiraboard.site",
        description=(
            "Generate a kanban board for every key in a boards file and an index "
            "page linking them, ready to publish as a static site."
        ),
    )
    parser.add_argument(
        "--boards-file",
        default=DEFAULT_BOARDS_FILE,
        help=f"file with one Jira issue key per line (default: {DEFAULT_BOARDS_FILE})",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        default=DEFAULT_OUTPUT_DIR,
        help=f"directory to write the site into (default: {DEFAULT_OUTPUT_DIR})",
    )
    parser.add_argument(
        "--base-url",
        default=None,
        help="Jira site base URL (default: $JIRA_BASE_URL or the warthogs site)",
    )
    parser.add_argument(
        "--token-file",
        default=None,
        help="path to the 'email:api_token' file (default: .jira-token)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    try:
        keys = read_board_keys(args.boards_file)
    except OSError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2
    if not keys:
        print(f"no board keys found in {args.boards_file}", file=sys.stderr)
        return 2

    try:
        email, api_token = read_credentials(args.token_file)
    except ConfigError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2

    client = JiraClient(resolve_base_url(args.base_url), email, api_token)
    reports = generate_site(client, keys, args.output_dir)

    output_dir = Path(args.output_dir)
    for report in reports:
        if report.error:
            print(f"failed {report.key}: {report.error}", file=sys.stderr)
        else:
            print(f"wrote {output_dir / report.filename} ({report.total} child issues)")
    print(f"wrote {output_dir / 'index.html'} ({len(reports)} reports)")

    failures = [report for report in reports if report.error]
    return 1 if failures and len(failures) == len(reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())