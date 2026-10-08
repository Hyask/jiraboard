from __future__ import annotations

from typing import Any, Iterator

import requests


class JiraError(RuntimeError):
    """Raised for any non-successful Jira REST API response."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(f"Jira API error {status_code}: {message}")
        self.status_code = status_code
        self.message = message


class JiraClient:
    """A thin, read-only wrapper around the Jira Cloud REST API v3.

    Authentication uses HTTP basic auth with the account email and an API
    token, as documented at
    https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/
    """

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        session: requests.Session | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.auth = (email, api_token)
        self.session.headers.update({"Accept": "application/json"})

    def _url(self, path: str) -> str:
        return f"{self.base_url}/rest/api/3/{path.lstrip('/')}"

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = self.session.get(self._url(path), params=params, timeout=self.timeout)
        if response.status_code >= 400:
            raise JiraError(response.status_code, self._error_message(response))
        return response.json()

    @staticmethod
    def _error_message(response: requests.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return (response.text or response.reason or "").strip()[:500]
        messages = list(payload.get("errorMessages") or [])
        messages += [f"{field}: {msg}" for field, msg in (payload.get("errors") or {}).items()]
        return "; ".join(messages) or (response.reason or "unknown error")

    def get_issue(self, key: str, fields: str) -> dict[str, Any]:
        return self.get(f"issue/{key}", params={"fields": fields})

    def search(self, jql: str, fields: str, page_size: int = 100) -> Iterator[dict[str, Any]]:
        """Yield every issue matching ``jql``, following ``nextPageToken``."""
        params: dict[str, Any] = {"jql": jql, "maxResults": page_size, "fields": fields}
        next_page_token: str | None = None
        while True:
            page_params = dict(params)
            if next_page_token:
                page_params["nextPageToken"] = next_page_token
            page = self.get("search/jql", params=page_params)
            yield from page.get("issues", [])
            next_page_token = page.get("nextPageToken")
            if page.get("isLast") or not next_page_token:
                return
