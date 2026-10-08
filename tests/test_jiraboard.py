from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jiraboard.board import build_board, children_jql, group_into_columns
from jiraboard.config import ConfigError, read_credentials
from jiraboard.models import Issue, Status

BASE = "https://warthogs.atlassian.net"


def make_issue_json(key, status_name, category_key, category_name, **extra):
    fields = {
        "summary": f"Summary for {key}",
        "issuetype": {"name": extra.pop("issue_type", "Epic")},
        "status": {
            "name": status_name,
            "statusCategory": {
                "key": category_key,
                "name": category_name,
                "colorName": "blue-gray",
            },
        },
    }
    fields.update(extra)
    return {"key": key, "fields": fields}


def make_issue(key, status_name, category_key, category_name, **extra):
    return Issue.from_json(
        make_issue_json(key, status_name, category_key, category_name, **extra), BASE
    )


class ReadCredentialsTest(unittest.TestCase):
    def test_reads_email_and_token_from_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / ".jira-token"
            token_file.write_text("user@example.com:secret-token\n", encoding="utf-8")
            self.assertEqual(
                read_credentials(str(token_file)), ("user@example.com", "secret-token")
            )

    def test_token_with_colon_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            token_file = Path(tmp) / ".jira-token"
            token_file.write_text("user@example.com:aa:bb:cc", encoding="utf-8")
            self.assertEqual(read_credentials(str(token_file)), ("user@example.com", "aa:bb:cc"))

    def test_missing_file_raises(self):
        with self.assertRaises(ConfigError):
            read_credentials("/nonexistent/.jira-token")

    def test_env_vars_take_precedence(self):
        original = dict(os.environ)
        os.environ["JIRA_EMAIL"] = "env@example.com"
        os.environ["JIRA_API_TOKEN"] = "env-token"
        try:
            self.assertEqual(read_credentials("/nonexistent"), ("env@example.com", "env-token"))
        finally:
            os.environ.clear()
            os.environ.update(original)


class IssueParsingTest(unittest.TestCase):
    def test_from_json_maps_fields(self):
        issue = Issue.from_json(
            {
                "key": "DPE-1",
                "fields": {
                    "summary": "An epic",
                    "issuetype": {"name": "Epic"},
                    "status": {
                        "name": "In Progress",
                        "statusCategory": {"key": "indeterminate", "name": "In Progress"},
                    },
                    "assignee": {"displayName": "Ada Lovelace"},
                    "priority": {"name": "High"},
                    "duedate": "2026-07-24",
                    "parent": {"key": "DPE-9855"},
                },
            },
            BASE,
        )
        self.assertEqual(issue.url, f"{BASE}/browse/DPE-1")
        self.assertEqual(issue.assignee, "Ada Lovelace")
        self.assertEqual(issue.priority, "High")
        self.assertEqual(issue.due_date, "2026-07-24")
        self.assertEqual(issue.parent_key, "DPE-9855")
        self.assertEqual(issue.status.category_key, "indeterminate")

    def test_status_defaults_when_missing(self):
        status = Status.from_json({})
        self.assertEqual(status.category_key, "new")
        self.assertEqual(status.name, "Unknown")


class GroupingTest(unittest.TestCase):
    def test_columns_are_in_workflow_order_and_always_present(self):
        issues = [
            make_issue("DPE-3", "Done", "done", "Done", assignee={"displayName": "Ada"}),
            make_issue("DPE-1", "Untriaged", "new", "To Do", assignee={"displayName": "Ada"}),
            make_issue("DPE-2", "In Progress", "indeterminate", "In Progress", assignee={"displayName": "Ada"}),
        ]
        columns = group_into_columns(issues)
        self.assertEqual([c.key for c in columns], ["unassigned", "new", "indeterminate", "done"])
        self.assertEqual(
            [c.title for c in columns], ["Unassigned", "To Do", "In Progress", "Done"]
        )
        self.assertEqual([c.count for c in columns], [0, 1, 1, 1])

    def test_empty_columns_are_still_rendered(self):
        columns = group_into_columns([])
        self.assertEqual([c.key for c in columns], ["unassigned", "new", "indeterminate", "done"])
        self.assertTrue(all(c.count == 0 for c in columns))

    def test_unknown_category_is_appended(self):
        issues = [make_issue("DPE-9", "Blocked", "blocked", "Blocked", assignee={"displayName": "Ada"})]
        columns = group_into_columns(issues)
        self.assertEqual(
            [c.key for c in columns], ["unassigned", "new", "indeterminate", "done", "blocked"]
        )
        self.assertEqual(columns[-1].title, "Blocked")

    def test_unassigned_issues_get_their_own_leading_column(self):
        issues = [
            make_issue("DPE-1", "In Progress", "indeterminate", "In Progress"),
            make_issue("DPE-2", "In Progress", "indeterminate", "In Progress", assignee={"displayName": "Ada"}),
        ]
        columns = group_into_columns(issues)
        by_key = {column.key: column for column in columns}
        self.assertEqual(columns[0].key, "unassigned")
        self.assertEqual([issue.key for issue in by_key["unassigned"].issues], ["DPE-1"])
        self.assertEqual([issue.key for issue in by_key["indeterminate"].issues], ["DPE-2"])


class FakeClient:
    base_url = BASE

    def __init__(self, milestone, children):
        self.milestone = milestone
        self.children = children
        self.calls = []

    def get_issue(self, key, fields):
        self.calls.append(("get_issue", key, fields))
        return self.milestone

    def search(self, jql, fields):
        self.calls.append(("search", jql, fields))
        return iter(self.children)


def make_milestone(key="DPE-9855"):
    return {
        "key": key,
        "fields": {
            "summary": "Milestone",
            "issuetype": {"name": "Objective"},
            "status": {
                "name": "To Do",
                "statusCategory": {"key": "new", "name": "To Do"},
            },
        },
    }


class BuildBoardTest(unittest.TestCase):
    def test_tracks_mixed_children_of_parent(self):
        children = [
            make_issue_json("DPE-1", "In Review", "indeterminate", "In Progress", issue_type="Story", assignee={"displayName": "Ada"}),
            make_issue_json("DPE-2", "Done", "done", "Done", issue_type="Bug", assignee={"displayName": "Ada"}),
            make_issue_json("DPE-3", "Untriaged", "new", "To Do", issue_type="Epic"),
        ]
        client = FakeClient(make_milestone(), children)
        board = build_board(
            client, "DPE-9855", now=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )

        self.assertEqual(board.milestone.key, "DPE-9855")
        self.assertEqual(board.total, 3)
        self.assertEqual([c.key for c in board.columns], ["unassigned", "new", "indeterminate", "done"])
        self.assertEqual([c.count for c in board.columns], [1, 0, 1, 1])
        self.assertEqual(board.generated_at, "2026-01-02 00:00 UTC")
        self.assertEqual([call[0] for call in client.calls], ["get_issue", "search"])
        self.assertEqual(
            client.calls[1][1], 'parent = "DPE-9855" ORDER BY status ASC, key ASC'
        )

    def test_issue_without_children_yields_empty_board(self):
        board = build_board(FakeClient(make_milestone("DPE-9999"), []), "DPE-9999")
        self.assertEqual(board.total, 0)
        self.assertEqual(
            [c.key for c in board.columns], ["unassigned", "new", "indeterminate", "done"]
        )


class ChildrenJqlTest(unittest.TestCase):
    def test_children_jql_uses_parent_and_does_not_filter_type(self):
        jql = children_jql("ADT-1589")
        self.assertIn('parent = "ADT-1589"', jql)
        self.assertNotIn("issuetype", jql)


if __name__ == "__main__":
    unittest.main()
