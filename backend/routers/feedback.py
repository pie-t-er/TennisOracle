"""POST /api/feedback — create a GitHub issue from in-app feedback form."""
import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

router = APIRouter(prefix="/api")

_REPO = "pie-t-er/TennisOracle"
_GH_API = f"https://api.github.com/repos/{_REPO}/issues"

_TYPE_TITLE = {
    "bug":     "Bug",
    "feature": "Feature request",
    "insight": "User insight",
}
_TYPE_LABELS = {
    "bug":     ["bug"],
    "feature": ["enhancement"],
    "insight": [],
}


class FeedbackRequest(BaseModel):
    type: str
    description: str

    @field_validator("type")
    @classmethod
    def valid_type(cls, v: str) -> str:
        if v not in _TYPE_TITLE:
            raise ValueError(f"type must be one of {list(_TYPE_TITLE)}")
        return v

    @field_validator("description")
    @classmethod
    def non_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("description cannot be empty")
        return v


@router.post("/feedback")
async def submit_feedback(body: FeedbackRequest):
    """
    Create a GitHub issue from in-app feedback.
    Requires GITHUB_TOKEN env var (PAT with public_repo scope).
    """
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        raise HTTPException(503, "Feedback is not configured on this server")

    prefix   = _TYPE_TITLE[body.type]
    truncated = body.description[:72] + ("…" if len(body.description) > 72 else "")
    title    = f"{prefix}: {truncated}"
    labels   = _TYPE_LABELS[body.type]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            _GH_API,
            json={"title": title, "body": body.description, "labels": labels},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10.0,
        )

    if not resp.is_success:
        try:
            gh_message = resp.json().get("message", resp.text)
        except Exception:
            gh_message = resp.text
        raise HTTPException(502, f"GitHub API error {resp.status_code}: {gh_message}")

    data = resp.json()
    return {"issue_url": data["html_url"], "issue_number": data["number"]}
