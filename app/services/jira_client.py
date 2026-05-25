from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

import httpx


JIRA_FIELDS = "summary,description,status,priority,duedate,issuetype,project,assignee"


@dataclass
class JiraIssue:
    key: str
    url: str
    summary: str
    description_text: Optional[str]
    status_category: Optional[str]
    status_name: Optional[str]
    priority_name: Optional[str]
    due_date: Optional[date]
    project_key: Optional[str]
    issue_type: Optional[str]
    raw: dict[str, Any] = field(default_factory=dict)


class JiraAuthError(RuntimeError):
    pass


class JiraApiError(RuntimeError):
    pass


def _adf_to_plain_text(node: Any) -> str:
    if node is None:
        return ""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_adf_to_plain_text(child) for child in node)
    if not isinstance(node, dict):
        return ""

    node_type = node.get("type")
    if node_type == "text":
        return node.get("text", "")
    if node_type == "hardBreak":
        return "\n"

    rendered = _adf_to_plain_text(node.get("content"))

    if node_type in {"paragraph", "heading", "bulletList", "orderedList", "listItem", "blockquote", "codeBlock"}:
        rendered = rendered + "\n"
    return rendered


def _parse_date(value: Any) -> Optional[date]:
    if not value or not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


class JiraClient:
    def __init__(self, base_url: str, email: str, api_token: str, timeout: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(email, api_token)
        self._timeout = timeout

    async def __aenter__(self) -> "JiraClient":
        self._client = httpx.AsyncClient(
            auth=self._auth,
            timeout=self._timeout,
            headers={"Accept": "application/json"},
        )
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self._client.aclose()

    async def whoami(self) -> dict[str, Any]:
        resp = await self._client.get(f"{self.base_url}/rest/api/3/myself")
        if resp.status_code in (401, 403):
            raise JiraAuthError(f"Credenciales rechazadas por Jira ({resp.status_code})")
        if resp.status_code >= 400:
            raise JiraApiError(f"Jira /myself devolvió {resp.status_code}: {resp.text[:300]}")
        return resp.json()

    async def search_issues(self, jql: str) -> list[JiraIssue]:
        issues: list[dict[str, Any]] = []
        next_token: Optional[str] = None

        while True:
            params: dict[str, Any] = {"jql": jql, "fields": JIRA_FIELDS, "maxResults": 100}
            if next_token:
                params["nextPageToken"] = next_token

            resp = await self._client.get(f"{self.base_url}/rest/api/3/search/jql", params=params)

            if resp.status_code == 404 or resp.status_code == 410:
                return await self._search_issues_legacy(jql)

            if resp.status_code in (401, 403):
                raise JiraAuthError(f"Credenciales rechazadas por Jira ({resp.status_code})")
            if resp.status_code >= 400:
                raise JiraApiError(f"Jira search devolvió {resp.status_code}: {resp.text[:300]}")

            payload = resp.json()
            issues.extend(payload.get("issues", []))

            if payload.get("isLast", True):
                break
            next_token = payload.get("nextPageToken")
            if not next_token:
                break

        return [self._to_issue(raw) for raw in issues]

    async def _search_issues_legacy(self, jql: str) -> list[JiraIssue]:
        issues: list[dict[str, Any]] = []
        start_at = 0
        page_size = 100

        while True:
            params = {
                "jql": jql,
                "fields": JIRA_FIELDS,
                "startAt": start_at,
                "maxResults": page_size,
            }
            resp = await self._client.get(f"{self.base_url}/rest/api/3/search", params=params)
            if resp.status_code in (401, 403):
                raise JiraAuthError(f"Credenciales rechazadas por Jira ({resp.status_code})")
            if resp.status_code >= 400:
                raise JiraApiError(f"Jira search (legacy) devolvió {resp.status_code}: {resp.text[:300]}")

            payload = resp.json()
            batch = payload.get("issues", [])
            issues.extend(batch)
            total = payload.get("total", 0)
            start_at += len(batch)
            if not batch or start_at >= total:
                break

        return [self._to_issue(raw) for raw in issues]

    def _to_issue(self, raw: dict[str, Any]) -> JiraIssue:
        key = raw.get("key", "")
        fields = raw.get("fields") or {}
        status = fields.get("status") or {}
        status_category = (status.get("statusCategory") or {}).get("key")
        priority = fields.get("priority") or {}
        project = fields.get("project") or {}
        issue_type = fields.get("issuetype") or {}

        description_text = _adf_to_plain_text(fields.get("description")).strip() or None

        return JiraIssue(
            key=key,
            url=f"{self.base_url}/browse/{key}",
            summary=fields.get("summary") or "",
            description_text=description_text,
            status_category=status_category,
            status_name=status.get("name"),
            priority_name=priority.get("name"),
            due_date=_parse_date(fields.get("duedate")),
            project_key=project.get("key"),
            issue_type=issue_type.get("name"),
            raw=raw,
        )
