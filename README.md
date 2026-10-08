# release-milestones

Generate a static, kanban-style HTML report showing the status of every **epic**
under a Jira milestone issue (e.g. `ADT-1589`).

The report groups epics into three workflow columns — **To Do**, **In Progress**,
**Done** — based on their Jira status category. Each card links back to Jira and
shows the epic's exact status, priority, assignee and due date.

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

`ADT-1589` must be the parent milestone/objective; the tool searches for issues
matching `parent = "<KEY>" AND issuetype = Epic`.

## Development

```bash
python3 -m unittest discover -s tests -v
```

## Layout

```
jiraboard/
  __main__.py     CLI entry point (python -m jiraboard)
  config.py       credential/token loading and validation
  client.py       read-only Jira REST v3 client (basic auth + pagination)
  models.py       Status / Issue dataclasses
  board.py        JQL, epic fetching and kanban grouping
  render.py       Jinja environment and report writer
  templates/
    board.html.j2 self-contained kanban board
tests/            stdlib unittest suite
```

## Notes

- Search uses the current `GET /rest/api/3/search/jql` endpoint and follows
  `nextPageToken` pagination.
- API errors are surfaced with Jira's `errorMessages`/`errors` text. A 404 on
  the milestone usually means the token cannot see that project.
