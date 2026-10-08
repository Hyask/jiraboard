# release-milestones

Generate a static, kanban-style HTML report showing the status of every direct
child issue of a given Jira task — Epics under an Objective, Tasks/Stories under
an Epic, or sub-tasks under any issue.

Children are found by querying the issue `parent` field
(`GET /rest/api/3/search/jql?jql=parent = "<KEY>"`) and following
`nextPageToken` pagination. Results are deliberately *not* filtered by issue
type, so every hierarchy level is tracked by the same code path. Unassigned
issues are collected into a leading **Unassigned** column; the rest are grouped
into three workflow columns — **To Do**, **In Progress**, **Done** — based on
their Jira status category. Each card links back to Jira and shows the issue
type, exact status, priority, assignee and due date.

## Requirements

Python 3.10+ with `requests` and `Jinja2` (standard library for everything else):

```bash
sudo apt install python3-requests python3-jinja2
```

## Authentication

Credentials use HTTP basic auth with an Atlassian account email and an API
token, per
[Basic auth for REST APIs](https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/).

Provide them either:

- in a file with a single `email:api_token` line (default: `./.jira-token`,
  git-ignored), or
- via the `JIRA_EMAIL` and `JIRA_API_TOKEN` environment variables.

The site URL defaults to `https://warthogs.atlassian.net` and can be overridden
with `--base-url` or `JIRA_BASE_URL`.

The token only needs read access. No call to `/myself` (`/me`) is made.

## Usage

```bash
python3 -m jiraboard ADT-1589
# -> out/ADT-1589-board.html

python3 -m jiraboard ADT-1589 -o report.html
python3 -m jiraboard ADT-1589 --base-url https://example.atlassian.net --token-file /path/.jira-token
```

`<KEY>` is the task whose children are reported (e.g. `ADT-1589`). Children are
found via the `parent` field, so it works the same whether `<KEY>` is an
Objective (children are Epics) or an Epic (children are Stories/Tasks/Bugs).

## Development

```bash
python3 -m unittest discover -s tests -v
```

## Layout

```
jiraboard/
  __main__.py     CLI entry point (python -m jiraboard)
  config.py       credential/token loading and validation
  client.py       read-only Jira REST v3 client (basic auth + search pagination)
  models.py       Status / Issue dataclasses
  board.py        parent query, child fetching and kanban grouping
  render.py       Jinja environment and report writer
  templates/
    board.html.j2 self-contained kanban board
tests/            stdlib unittest suite
```

## Notes

- Children are enumerated with a `parent = "<KEY>"` search. The issue resource
  exposes no children collection (its `subtasks` field only covers sub-task
  issues), so a parent-scoped query is the only read-only way to find both
  **Epics under an Objective** and **Tasks under an Epic**. The CLI warns when
  nothing matches.
- API errors are surfaced with Jira's `errorMessages`/`errors` text. A 404 on
  the task usually means the token cannot see that project.
