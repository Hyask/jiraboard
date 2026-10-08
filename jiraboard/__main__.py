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
            "Generate a static kanban-style HTML report of every epic under a "
            "Jira milestone issue."
        ),
    )
    parser.add_argument(
        "milestone_key",
        help="Jira issue key of the milestone/objective, e.g. ADT-1589",
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
    output = Path(args.output) if args.output else Path("out") / f"{args.milestone_key.strip().upper()}-board.html"

    try:
        config = JiraConfig.load(
            milestone_key=args.milestone_key,
            output=output,
            base_url=args.base_url,
            token_file=args.token_file,
        )
        client = JiraClient(config.base_url, config.email, config.api_token)
        board = build_board(client, config.milestone_key)
        path = write_report(board, config.output)
    except ConfigError as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2
    except JiraError as error:
        print(error, file=sys.stderr)
        if error.status_code == 404:
            print(
                f"hint: the token cannot see {args.milestone_key} (or it does not exist)",
                file=sys.stderr,
            )
        return 1

    print(f"wrote {path} ({board.total} epics)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
