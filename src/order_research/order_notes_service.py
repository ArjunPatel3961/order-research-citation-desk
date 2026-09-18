import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request

from .citation_collector import CitationCollector
from .infrai_gateway import InfraiError, InfraiGateway
from .models import CollectRequest, CollectResult


@asynccontextmanager
async def lifespan(app: FastAPI):
    gateway = InfraiGateway()
    app.state.gateway = gateway
    app.state.collector = CitationCollector(
        gateway,
        collection=os.getenv("INFRAI_VECTOR_COLLECTION", "order-research-citations"),
    )
    yield
    await gateway.close()


service = FastAPI(title="Order Research Citation Desk", lifespan=lifespan)


def get_collector(request: Request) -> CitationCollector:
    return request.app.state.collector


@service.post("/citations/collect", response_model=CollectResult)
async def collect_citations(
    payload: CollectRequest,
    collector: CitationCollector = Depends(get_collector),
) -> CollectResult:
    try:
        return await collector.collect(payload)
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "detail": exc.detail},
        ) from exc

