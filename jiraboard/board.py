from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .client import JiraClient
from .models import (
    STATUS_CATEGORY_LABELS,
    STATUS_CATEGORY_ORDER,
    Issue,
)

MILESTONE_FIELDS = "summary,status,issuetype"
EPIC_FIELDS = "summary,status,issuetype,assignee,priority,duedate,parent"


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


def epic_jql(milestone_key: str) -> str:
    """JQL selecting every epic whose parent is the milestone issue."""
    return f'parent = "{milestone_key}" AND issuetype = Epic ORDER BY status ASC, key ASC'


def fetch_epics(client: JiraClient, milestone_key: str) -> list[Issue]:
    return [
        Issue.from_json(issue, client.base_url)
        for issue in client.search(epic_jql(milestone_key), fields=EPIC_FIELDS)
    ]


def group_into_columns(epics: list[Issue]) -> list[Column]:
    """Group epics into kanban columns by Jira status category.

    The three canonical categories are always shown, in workflow order, even
    when empty; any unexpected category is appended afterwards.
    """
    by_category: dict[str, list[Issue]] = {}
    for epic in epics:
        by_category.setdefault(epic.status.category_key, []).append(epic)

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
    milestone = Issue.from_json(
        client.get_issue(milestone_key, fields=MILESTONE_FIELDS), client.base_url
    )
    epics = fetch_epics(client, milestone_key)
    generated = now or datetime.now(timezone.utc)
    return Board(
        milestone=milestone,
        columns=group_into_columns(epics),
        generated_at=generated.strftime("%Y-%m-%d %H:%M UTC"),
    )
