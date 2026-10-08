from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from jiraboard.board import build_board, group_into_columns
from jiraboard.config import ConfigError, read_credentials
from jiraboard.models import Issue, Status

BASE = "https://warthogs.atlassian.net"


def make_issue(key, status_name, category_key, category_name, **extra):
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
    return Issue.from_json({"key": key, "fields": fields}, BASE)


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
        epics = [
            make_issue("DPE-3", "Done", "done", "Done"),
            make_issue("DPE-1", "Untriaged", "new", "To Do"),
            make_issue("DPE-2", "In Progress", "indeterminate", "In Progress"),
        ]
        columns = group_into_columns(epics)
        self.assertEqual([c.key for c in columns], ["new", "indeterminate", "done"])
        self.assertEqual([c.title for c in columns], ["To Do", "In Progress", "Done"])
        self.assertEqual([c.count for c in columns], [1, 1, 1])

    def test_empty_columns_are_still_rendered(self):
        columns = group_into_columns([])
        self.assertEqual([c.key for c in columns], ["new", "indeterminate", "done"])
        self.assertTrue(all(c.count == 0 for c in columns))

    def test_unknown_category_is_appended(self):
        epics = [make_issue("DPE-9", "Blocked", "blocked", "Blocked")]
        columns = group_into_columns(epics)
        self.assertEqual([c.key for c in columns], ["new", "indeterminate", "done", "blocked"])
        self.assertEqual(columns[-1].title, "Blocked")


class FakeClient:
    base_url = BASE

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_issue(self, key, fields):
        self.calls.append((key, fields))
        return self.payload


class BuildBoardTest(unittest.TestCase):
    @staticmethod
    def _subtask(key, status_name, category_key, category_name):
        return {
            "key": key,
            "fields": {
                "summary": f"Subtask {key}",
                "issuetype": {"name": "Sub-task"},
                "priority": {"name": "Medium"},
                "status": {
                    "name": status_name,
                    "statusCategory": {"key": category_key, "name": category_name},
                },
            },
        }

    def test_builds_board_from_embedded_subtasks(self):
        payload = {
            "key": "DPE-11116",
            "fields": {
                "summary": "Migrate refresh logic",
                "issuetype": {"name": "Story"},
                "status": {
                    "name": "In Progress",
                    "statusCategory": {"key": "indeterminate", "name": "In Progress"},
                },
                "subtasks": [
                    self._subtask("DPE-1", "In Review", "indeterminate", "In Progress"),
                    self._subtask("DPE-2", "Done", "done", "Done"),
                ],
            },
        }
        client = FakeClient(payload)
        board = build_board(
            client, "DPE-11116", now=datetime(2026, 1, 2, tzinfo=timezone.utc)
        )

        self.assertEqual(client.calls, [("DPE-11116", "summary,status,issuetype,subtasks")])
        self.assertEqual(board.milestone.key, "DPE-11116")
        self.assertEqual(board.total, 2)
        self.assertEqual([c.count for c in board.columns], [0, 1, 1])
        self.assertEqual(board.generated_at, "2026-01-02 00:00 UTC")

    def test_issue_without_subtasks_yields_empty_board(self):
        payload = {
            "key": "DPE-9999",
            "fields": {
                "summary": "No children",
                "issuetype": {"name": "Objective"},
                "status": {
                    "name": "To Do",
                    "statusCategory": {"key": "new", "name": "To Do"},
                },
            },
        }
        board = build_board(FakeClient(payload), "DPE-9999")
        self.assertEqual(board.total, 0)
        self.assertEqual([c.key for c in board.columns], ["new", "indeterminate", "done"])


if __name__ == "__main__":
    unittest.main()
