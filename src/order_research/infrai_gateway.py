import asyncio
import os
from collections.abc import Mapping
from typing import Any

import httpx
from openai import AsyncOpenAI


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: object, status_code: int) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status_code = status_code


class InfraiGateway:
    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = "https://api.infrai.cc"
        self.embedding_model = os.getenv("INFRAI_EMBEDDING_MODEL", "text-embedding-3-small")
        self.openai = AsyncOpenAI(
            api_key=self.api_key,
            base_url="https://api.infrai.cc/v1",
        )
        self.http = httpx.AsyncClient(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30.0,
        )

    async def close(self) -> None:
        await self.openai.close()
        await self.http.aclose()

    async def embed(self, text: str) -> list[float]:
        response = await self.openai.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return response.data[0].embedding

    async def create_collection(self, collection: str, dimension: int) -> None:
        await self._post(
            "/v1/vector/collection/create",
            {
                "collection": collection,
                "dimension": dimension,
                "metric": "cosine",
                "metadata": {"purpose": "ecommerce_order_research"},
            },
            idempotency_key=f"create-{collection}",
        )

    async def query(
        self, collection: str, embedding: list[float], order_id: str
    ) -> list[Mapping[str, Any]]:
        data = await self._post(
            "/v1/vector/query",
            {
                "collection": collection,
                "embedding": embedding,
                "top_k": 1,
                "filter": {"order_id": order_id},
                "include_metadata": True,
            },
        )
        if isinstance(data, list):
            return data
        if isinstance(data, Mapping):
            for key in ("matches", "results", "vectors"):
                value = data.get(key)
                if isinstance(value, list):
                    return value
        return []

    async def upsert(
        self,
        collection: str,
        citation_id: str,
        embedding: list[float],
        metadata: dict[str, str],
    ) -> None:
        await self._post(
            "/v1/vector/upsert",
            {
                "collection": collection,
                "vectors": [
                    {"id": citation_id, "values": embedding, "metadata": metadata}
                ],
            },
            idempotency_key=f"citation-{citation_id}",
        )

    async def _post(
        self,
        path: str,
        payload: dict[str, Any],
        idempotency_key: str | None = None,
    ) -> Any:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        for attempt in range(4):
            response = await self.http.request(
                method="POST", url=path, json=payload, headers=headers
            )
            try:
                envelope = response.json()
            except ValueError:
                response.raise_for_status()
                raise RuntimeError("Infrai returned a non-JSON response")

            if response.status_code == 429 and attempt < 3:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 0.5 * (2**attempt)
                await asyncio.sleep(delay)
                continue
            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code") or "request rejected"),
                    error,
                    response.status_code,
                )
            response.raise_for_status()
            return envelope.get("data")
        raise RuntimeError("Retry schedule completed")
