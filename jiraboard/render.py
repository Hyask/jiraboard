from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .board import Board

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_NAME = "board.html.j2"
INDEX_TEMPLATE_NAME = "index.html.j2"


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["or_dash"] = lambda value: value if value else "\u2014"
    return env


def render_board(board: Board) -> str:
    return _environment().get_template(TEMPLATE_NAME).render(board=board)


def render_index(reports: list) -> str:
    return _environment().get_template(INDEX_TEMPLATE_NAME).render(reports=reports)


def _write(text: str, output: Path) -> Path:
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")
    return output


def write_report(board: Board, output: Path) -> Path:
    return _write(render_board(board), output)


def write_index(reports: list, output: Path) -> Path:
    return _write(render_index(reports), output)
