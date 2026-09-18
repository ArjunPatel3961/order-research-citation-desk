import hashlib
from collections.abc import Mapping
from typing import Any, Protocol
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import CitationDecision, CollectRequest, CollectResult


class CitationStore(Protocol):
    async def embed(self, text: str) -> list[float]:
        raise AssertionError("CitationStore is a typing protocol")

    async def query(
        self, collection: str, embedding: list[float], order_id: str
    ) -> list[Mapping[str, Any]]:
        raise AssertionError("CitationStore is a typing protocol")

    async def upsert(
        self,
        collection: str,
        citation_id: str,
        embedding: list[float],
        metadata: dict[str, str],
    ) -> None:
        raise AssertionError("CitationStore is a typing protocol")


def canonical_url(raw_url: str) -> str:
    parts = urlsplit(raw_url)
    kept_query = [(key, value) for key, value in parse_qsl(parts.query) if not key.startswith("utm_")]
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path, urlencode(kept_query), ""))


def citation_id(order_id: str, url: str) -> str:
    digest = hashlib.sha256(f"{order_id}:{url}".encode()).hexdigest()[:24]
    return f"cite_{digest}"


class CitationCollector:
    def __init__(
        self,
        store: CitationStore,
        collection: str = "order-research-citations",
        duplicate_threshold: float = 0.92,
    ) -> None:
        self.store = store
        self.collection = collection
        self.duplicate_threshold = duplicate_threshold

    async def collect(self, request: CollectRequest) -> CollectResult:
        decisions: list[CitationDecision] = []
        seen: dict[str, str] = {}

        for draft in request.citations:
            url = canonical_url(str(draft.url))
            current_id = citation_id(request.order_id, url)
            if url in seen:
                decisions.append(
                    CitationDecision(
                        url=draft.url,
                        citation_id=current_id,
                        status="duplicate",
                        duplicate_of=seen[url],
                    )
                )
                continue

            text = f"{draft.title}\n{draft.excerpt}\nResearch note: {request.note}"
            embedding = await self.store.embed(text)
            matches = await self.store.query(
                self.collection, embedding, request.order_id
            )
            duplicate = self._closest_duplicate(matches)
            if duplicate:
                decisions.append(
                    CitationDecision(
                        url=draft.url,
                        citation_id=current_id,
                        status="duplicate",
                        duplicate_of=duplicate,
                    )
                )
                seen[url] = duplicate
                continue

            await self.store.upsert(
                self.collection,
                current_id,
                embedding,
                {
                    "order_id": request.order_id,
                    "moment": request.moment.value,
                    "url": url,
                    "title": draft.title,
                },
            )
            seen[url] = current_id
            decisions.append(
                CitationDecision(
                    url=draft.url, citation_id=current_id, status="accepted"
                )
            )

        accepted = sum(item.status == "accepted" for item in decisions)
        return CollectResult(
            order_id=request.order_id,
            moment=request.moment,
            accepted=accepted,
            duplicates=len(decisions) - accepted,
            decisions=decisions,
        )

    def _closest_duplicate(self, matches: list[Mapping[str, Any]]) -> str | None:
        if not matches:
            return None
        match = matches[0]
        score = float(match.get("score", 0.0))
        match_id = match.get("id")
        return str(match_id) if match_id and score >= self.duplicate_threshold else None
