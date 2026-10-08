from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .client import JiraClient
from .models import (
    STATUS_CATEGORY_LABELS,
    STATUS_CATEGORY_ORDER,
    Issue,
)

# A single issue lookup is all that is needed: Jira embeds the direct subtasks
# of the requested issue in the ``subtasks`` field, so no search query runs.
ISSUE_FIELDS = "summary,status,issuetype,subtasks"


@dataclass(frozen=True)
class Column:
    key: str
    title: str
    issues: list[Issue] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.issues)


@dataclass(frozen=True)
class Board:
    milestone: Issue
    columns: list[Column]
    generated_at: str

    @property
    def total(self) -> int:
        return sum(column.count for column in self.columns)


def group_into_columns(issues: list[Issue]) -> list[Column]:
    """Group issues into kanban columns by Jira status category.

    The three canonical categories are always shown, in workflow order, even
    when empty; any unexpected category is appended afterwards.
    """
    by_category: dict[str, list[Issue]] = {}
    for issue in issues:
        by_category.setdefault(issue.status.category_key, []).append(issue)

    ordered_keys = list(STATUS_CATEGORY_ORDER)
    ordered_keys += [key for key in by_category if key not in ordered_keys]

    columns: list[Column] = []
    for key in ordered_keys:
        issues = sorted(
            by_category.get(key, []),
            key=lambda issue: (issue.status.name, issue.key),
        )
        title = STATUS_CATEGORY_LABELS.get(key) or issues[0].status.category
        columns.append(Column(key=key, title=title, issues=issues))
    return columns


def build_board(
    client: JiraClient,
    milestone_key: str,
    now: datetime | None = None,
) -> Board:
    """Build a board from the milestone issue and its embedded subtasks."""
    data = client.get_issue(milestone_key, fields=ISSUE_FIELDS)
    fields = data.get("fields") or {}
    milestone = Issue.from_json(data, client.base_url)
    subtasks = [
        Issue.from_json(subtask, client.base_url)
        for subtask in fields.get("subtasks") or []
    ]
    generated = now or datetime.now(timezone.utc)
    return Board(
        milestone=milestone,
        columns=group_into_columns(subtasks),
        generated_at=generated.strftime("%Y-%m-%d %H:%M UTC"),
    )
