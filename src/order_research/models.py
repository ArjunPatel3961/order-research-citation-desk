from enum import StrEnum

try:
    from pydantic import BaseModel, Field, HttpUrl
except ModuleNotFoundError:  # Keep the focused collector usable without optional runtime deps.
    from dataclasses import dataclass
    from urllib.parse import urlsplit

    class HttpUrl(str):
        def __new__(cls, value: str):
            parsed = urlsplit(value)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc:
                raise ValueError("URL must include an http(s) scheme and host")
            return str.__new__(cls, value)

    class BaseModel:
        @classmethod
        def model_validate(cls, value):
            return cls(**value)

    def Field(default=None, **_constraints):
        return default


class OrderMoment(StrEnum):
    CHECKOUT = "checkout"
    FULFILLMENT = "fulfillment"
    RECEIPT = "receipt"
    CUSTOMER_UPDATE = "customer_update"


if BaseModel.__module__ == "pydantic.main":
    class CitationDraft(BaseModel):
        url: HttpUrl
        title: str = Field(min_length=1, max_length=240)
        excerpt: str = Field(min_length=1, max_length=2_000)

    class CollectRequest(BaseModel):
        order_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
        moment: OrderMoment
        note: str = Field(min_length=1, max_length=2_000)
        citations: list[CitationDraft] = Field(min_length=1, max_length=25)

    class CitationDecision(BaseModel):
        url: HttpUrl
        citation_id: str
        status: str
        duplicate_of: str | None = None

    class CollectResult(BaseModel):
        order_id: str
        moment: OrderMoment
        accepted: int
        duplicates: int
        decisions: list[CitationDecision]
else:
    @dataclass
    class CitationDraft(BaseModel):
        url: HttpUrl
        title: str
        excerpt: str

    @dataclass
    class CollectRequest(BaseModel):
        order_id: str
        moment: OrderMoment
        note: str
        citations: list[CitationDraft]

        def __init__(self, order_id, moment, note, citations):
            if not isinstance(moment, OrderMoment):
                moment = OrderMoment(moment)
            self.order_id, self.moment, self.note = order_id, moment, note
            self.citations = [c if isinstance(c, CitationDraft) else CitationDraft(HttpUrl(c["url"]), c["title"], c["excerpt"]) for c in citations]

    @dataclass
    class CitationDecision(BaseModel):
        url: HttpUrl
        citation_id: str
        status: str
        duplicate_of: str | None = None

    @dataclass
    class CollectResult(BaseModel):
        order_id: str
        moment: OrderMoment
        accepted: int
        duplicates: int
        decisions: list[CitationDecision]
