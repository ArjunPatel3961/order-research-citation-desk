import asyncio
import os

from order_research.infrai_gateway import InfraiGateway


async def main() -> None:
    gateway = InfraiGateway()
    try:
        collection = os.getenv("INFRAI_VECTOR_COLLECTION", "order-research-citations")
        dimension = int(os.getenv("INFRAI_EMBEDDING_DIMENSION", "1536"))
        await gateway.create_collection(collection, dimension)
        print(f"Collection ready: {collection} ({dimension} dimensions)")
    finally:
        await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())

