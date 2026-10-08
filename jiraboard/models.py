from __future__ import annotations

from dataclasses import dataclass
from typing import Any

# Jira's status categories in workflow order. ``key`` values come straight from
# the API; the label is what humans expect to see on a kanban column.
STATUS_CATEGORY_ORDER = ("new", "indeterminate", "done")
STATUS_CATEGORY_LABELS = {
    "new": "To Do",
    "indeterminate": "In Progress",
    "done": "Done",
}


@dataclass(frozen=True)
class Status:
    name: str
    category: str
    category_key: str
    color: str

    @classmethod
    def from_json(cls, data: dict[str, Any]) -> "Status":
        category = data.get("statusCategory") or {}
        return cls(
            name=data.get("name") or "Unknown",
            category=category.get("name") or "Unknown",
            category_key=category.get("key") or "new",
            color=category.get("colorName") or "blue-gray",
        )


@dataclass(frozen=True)
class Issue:
    key: str
    summary: str
    issue_type: str
    status: Status
    url: str
    assignee: str | None = None
    priority: str | None = None
    due_date: str | None = None
    parent_key: str | None = None

    @classmethod
    def from_json(cls, data: dict[str, Any], base_url: str) -> "Issue":
        fields = data.get("fields") or {}
        key = data.get("key") or "UNKNOWN"
        parent = fields.get("parent") or {}
        assignee = fields.get("assignee") or {}
        priority = fields.get("priority") or {}
        return cls(
            key=key,
            summary=fields.get("summary") or key,
            issue_type=(fields.get("issuetype") or {}).get("name") or "Issue",
            status=Status.from_json(fields.get("status") or {}),
            url=f"{base_url.rstrip('/')}/browse/{key}",
            assignee=assignee.get("displayName"),
            priority=priority.get("name"),
            due_date=fields.get("duedate"),
            parent_key=parent.get("key"),
        )
