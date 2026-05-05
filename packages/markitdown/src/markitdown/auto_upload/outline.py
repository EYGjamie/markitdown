from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


class OutlineError(RuntimeError):
    """Raised when the Outline API returns an unusable response."""


@dataclass
class OutlineClient:
    base_url: str
    api_token: str
    session: Any | None = None
    timeout: float = 30.0

    def __post_init__(self) -> None:
        if self.session is None:
            self.session = requests.Session()

    def resolve_collection_id(self, collection_name: str) -> str:
        payload = self._post("collections.list", {"query": collection_name})
        for collection in payload.get("data", []):
            if collection.get("name") == collection_name:
                return collection["id"]
        raise OutlineError(
            f"Could not find Outline collection named '{collection_name}'."
        )

    def create_document(
        self,
        *,
        title: str,
        markdown: str,
        collection_id: str,
    ) -> dict[str, Any]:
        payload = self._post(
            "documents.create",
            {
                "title": title,
                "text": markdown,
                "collectionId": collection_id,
                "publish": True,
            },
        )
        return payload.get("data", {})

    def _post(self, method: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(
            f"{self.base_url}/api/{method}",
            json=payload,
            headers={
                "Authorization": f"Bearer {self.api_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            timeout=self.timeout,
        )
        body = response.json()
        if response.status_code >= 400 or not body.get("ok", True):
            error = body.get("error") or response.text
            raise OutlineError(
                f"Outline API call '{method}' failed with status "
                f"{response.status_code}: {error}"
            )
        return body
