from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .board import build_board
from .client import JiraClient, JiraError
from .config import ConfigError, JiraConfig
from .render import write_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jiraboard",
        description=(
            "Generate a static kanban-style HTML report of the child issues of a "
            "Jira task (linked through the parent field)."
        ),
    )
    parser.add_argument(
        "task_key",
        help="Jira issue key of the task, e.g. an Objective, Epic or Story (ADT-1589)",
    )
    parser.add_argument(
        "-o",
        "--output",
        default=None,
        help="output HTML path (default: out/<KEY>-board.html)",
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
    output = Path(args.output) if args.output else Path("out") / f"{args.task_key.strip().upper()}-board.html"

    try:
        config = JiraConfig.load(
            task_key=args.task_key,
            output=output,
            base_url=args.base_url,
            token_file=args.token_file,
        )
        client = JiraClient(config.base_url, config.email, config.api_token)
        board = build_board(client, config.task_key)
        path = write_report(board, config.output)
        if board.total == 0:
            print(
                f"warning: no issues have parent = {config.task_key}",
                file=sys.stderr,
            )
    except ConfigError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2
    except JiraError as error:
        print(error, file=sys.stderr)
        if error.status_code == 404:
            print(
                f"hint: the token cannot see {args.task_key} (or it does not exist)",
                file=sys.stderr,
            )
        return 1

    print(f"wrote {path} ({board.total} child issues)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
