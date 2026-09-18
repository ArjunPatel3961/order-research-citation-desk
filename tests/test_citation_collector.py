import asyncio
from collections.abc import Mapping
from typing import Any

from order_research.citation_collector import CitationCollector
from order_research.models import CollectRequest


class MemoryStore:
    def __init__(self) -> None:
        self.queries = 0
        self.writes: list[str] = []

    async def embed(self, text: str) -> list[float]:
        return [0.1, 0.2]

    async def query(
        self, collection: str, embedding: list[float], order_id: str
    ) -> list[Mapping[str, Any]]:
        self.queries += 1
        if self.queries == 2:
            return [{"id": "cite_existing", "score": 0.96}]
        return []

    async def upsert(
        self,
        collection: str,
        citation_id: str,
        embedding: list[float],
        metadata: dict[str, str],
    ) -> None:
        self.writes.append(citation_id)


def test_collects_one_source_and_rejects_url_and_semantic_duplicates() -> None:
    asyncio.run(run_duplicate_scenario())


async def run_duplicate_scenario() -> None:
    store = MemoryStore()
    collector = CitationCollector(store)
    request = CollectRequest.model_validate(
        {
            "order_id": "order_1042",
            "moment": "fulfillment",
            "note": "Carrier handoff research for the customer update.",
            "citations": [
                {
                    "url": "https://shop.example/packing?utm_source=notes",
                    "title": "Packing guidance",
                    "excerpt": "Seal the parcel before carrier handoff.",
                },
                {
                    "url": "https://shop.example/packing",
                    "title": "Same packing page",
                    "excerpt": "A second clipping from the packing page.",
                },
                {
                    "url": "https://carrier.example/handoff",
                    "title": "Carrier handoff",
                    "excerpt": "Equivalent guidance already stored for this order.",
                },
            ],
        }
    )

    result = await collector.collect(request)

    assert result.accepted == 1
    assert result.duplicates == 2
    assert [item.status for item in result.decisions] == [
        "accepted",
        "duplicate",
        "duplicate",
    ]
    assert result.decisions[1].duplicate_of == result.decisions[0].citation_id
    assert result.decisions[2].duplicate_of == "cite_existing"
    assert len(store.writes) == 1
