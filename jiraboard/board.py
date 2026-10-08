from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from .client import JiraClient
from .models import (
    STATUS_CATEGORY_LABELS,
    STATUS_CATEGORY_ORDER,
    Issue,
)

# The task itself needs only enough to render the header.
ISSUE_FIELDS = "summary,status,issuetype"
# Children can be any type: Epics under an Objective, Tasks/Stories/Bugs under
# an Epic, or sub-tasks under any issue. The ``parent`` field is what links
# them, so results are intentionally not filtered by issue type.
CHILD_FIELDS = "summary,status,issuetype,assignee,priority,duedate,parent"


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


def children_jql(task_key: str) -> str:
    """JQL selecting every issue whose ``parent`` is the given task.

    This deliberately covers all issue types so that Epics under an Objective
    and Tasks/Stories under an Epic are tracked by the same code path.
    """
    return f'parent = "{task_key}" ORDER BY status ASC, key ASC'


def fetch_children(client: JiraClient, task_key: str) -> list[Issue]:
    return [
        Issue.from_json(issue, client.base_url)
        for issue in client.search(children_jql(task_key), fields=CHILD_FIELDS)
    ]


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
    task_key: str,
    now: datetime | None = None,
) -> Board:
    """Build a board from the task and its direct children (via ``parent``)."""
    milestone = Issue.from_json(
        client.get_issue(task_key, fields=ISSUE_FIELDS), client.base_url
    )
    children = fetch_children(client, task_key)
    generated = now or datetime.now(timezone.utc)
    return Board(
        milestone=milestone,
        columns=group_into_columns(children),
        generated_at=generated.strftime("%Y-%m-%d %H:%M UTC"),
    )
