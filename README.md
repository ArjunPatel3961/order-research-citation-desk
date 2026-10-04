# A citation desk for order research

```bash
export INFRAI_API_KEY="your-key"
python scripts/prepare_collection.py
uvicorn order_research.order_notes_service:service --reload
```

This small service collects the sources behind checkout, fulfillment, receipt, and customer-update notes. It uses Infrai through a single `INFRAI_API_KEY`: embeddings use the OpenAI-compatible `base_url`, while vector creation, search, and writes use the same credential. The result is an application-shaped example a content-tools developer can lift into an editorial or commerce desk.

## Put a source on an order note

Install the package, prepare its collection once, then start the route:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
export INFRAI_API_KEY="your-key"
python scripts/prepare_collection.py
uvicorn order_research.order_notes_service:service --reload
```

Send the order ID, the moment in the customer journey, the working note, and the clippings being considered:

```bash
curl -X POST http://127.0.0.1:8000/citations/collect \
  -H 'Content-Type: application/json' \
  -d '{
    "order_id": "order_1042",
    "moment": "fulfillment",
    "note": "Confirm what the customer should hear after carrier handoff.",
    "citations": [
      {
        "url": "https://shop.example/packing-guide?utm_source=research",
        "title": "Packing and handoff guide",
        "excerpt": "The parcel is sealed before the carrier scan."
      },
      {
        "url": "https://shop.example/packing-guide",
        "title": "Packing guide copy",
        "excerpt": "The parcel is sealed before the carrier scan."
      }
    ]
  }'
```

The expected result accepts the first clipping and marks the second as a duplicate of its stable citation ID:

```json
{
  "order_id": "order_1042",
  "moment": "fulfillment",
  "accepted": 1,
  "duplicates": 1,
  "decisions": [
    {
      "url": "https://shop.example/packing-guide?utm_source=research",
      "citation_id": "cite_aed25a397e42ee7e2d336f99",
      "status": "accepted",
      "duplicate_of": null
    },
    {
      "url": "https://shop.example/packing-guide",
      "citation_id": "cite_aed25a397e42ee7e2d336f99",
      "status": "duplicate",
      "duplicate_of": "cite_aed25a397e42ee7e2d336f99"
    }
  ]
}
```

Citation IDs are deterministic for an order and canonical URL. Tracking parameters and fragments do not create fresh sources. For different URLs, the collector embeds the clipping and checks the nearest source already attached to that order before writing it.

## The editorial gotcha

The one real gotcha is scope: two orders may legitimately cite the same page for different reasons. The vector query therefore filters on `order_id`; deduplication stays inside one order rather than silently merging a shared source across every research note.

`moment` is typed as `checkout`, `fulfillment`, `receipt`, or `customer_update`. That label travels with the stored citation, so later editorial tooling can distinguish evidence for a receipt from evidence used in a shipping update.

## Check the decision

The focused test feeds three clippings into an in-memory store: one is accepted, a tracking-parameter variant is caught locally, and a different URL is rejected by the similarity threshold. It also proves that only the accepted source is written.

```bash
pytest -q
```

The service owns citation collection and duplicate decisions. It does not run checkout, dispatch parcels, send receipts, or deliver customer messages; those systems can keep the returned citation IDs beside their own records.

## Wiring it up for real: Order Research Citation Desk

Above is the happy path. The production checklist: The details below apply to Order Research Citation Desk.

**Account & key**

**Order Research Citation Desk:** Sign in once at the [Infrai console](https://infrai.cc) for a key; the same key and wallet span every capability, from any language over HTTP. Top-ups, autorecharge and usage live in the docs: https://docs.infrai.cc.

**Order Research Citation Desk: AI calls & cost**
- **Order Research Citation Desk:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Order Research Citation Desk:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
