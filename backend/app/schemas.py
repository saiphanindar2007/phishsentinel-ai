"""
PhishSentinel AI — API Schemas
--------------------------------
Pydantic models define (and enforce) the request/response contracts.
Every field that accepts attacker-controlled text has an explicit size
limit, and enumerated fields are real enums — bad input is rejected with
a clean 422 before it reaches any detector or the database.
"""
import re
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from app.config import MAX_BATCH_SIZE
from app.services.lists import normalize_domain

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
Verdict = Literal["safe", "suspicious", "phishing"]


def _clean_url(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("must not be empty")
    if _CTRL.search(v) or any(c.isspace() for c in v):
        raise ValueError("must not contain whitespace or control characters")
    if len(v) > 2048:
        raise ValueError("must be at most 2048 characters")
    return v


class URLAnalyzeRequest(BaseModel):
    url: str = Field(..., min_length=1, max_length=2048, description="The raw URL to analyze")

    @field_validator("url")
    @classmethod
    def _v(cls, v: str) -> str:
        return _clean_url(v)


class BatchAnalyzeRequest(BaseModel):
    urls: List[str] = Field(..., min_length=1, max_length=MAX_BATCH_SIZE, description="URLs to scan in one call")

    @field_validator("urls")
    @classmethod
    def _v(cls, urls: List[str]) -> List[str]:
        cleaned, seen = [], set()
        for u in urls:
            u = _clean_url(u)
            if u.lower() not in seen:           # de-duplicate, keep order
                seen.add(u.lower())
                cleaned.append(u)
        return cleaned


class EmailAnalyzeRequest(BaseModel):
    sender: str = Field(..., min_length=3, max_length=320, description="Sender email address")
    recipient: Optional[str] = Field(None, max_length=320, description="Recipient address (for the reputation graph)")
    subject: str = Field("", max_length=998, description="Email subject line")
    body: str = Field(..., max_length=200_000, description="Plain-text email body")
    html_body: Optional[str] = Field(None, max_length=400_000, description="HTML body, for link/form analysis")
    raw_headers: Optional[str] = Field(None, max_length=50_000, description="Raw RFC 5322 headers, for SPF/DKIM/DMARC analysis")
    url: Optional[str] = Field(None, max_length=2048, description="Primary URL (links are also extracted from the body automatically)")
    screenshot_base64: Optional[str] = Field(None, max_length=7_000_000, description="Base64 screenshot of a landing page")
    claimed_brand: Optional[str] = Field(None, max_length=64, pattern=r"^[A-Za-z0-9._-]+$", description="Brand the page claims to be")

    @field_validator("url")
    @classmethod
    def _v(cls, v: Optional[str]) -> Optional[str]:
        return _clean_url(v) if v else None


class SignalBreakdown(BaseModel):
    url_score: float
    nlp_score: float
    visual_score: float
    reputation_score: float


class VerdictResponse(BaseModel):
    verdict_id: str
    verdict: Verdict
    confidence: float
    breakdown: SignalBreakdown
    top_reasons: List[str]
    explanation: str
    override: Optional[Literal["allowlist", "denylist"]] = Field(None, description="Set when an org list decided the verdict")
    authentication: Optional[Dict[str, Optional[str]]] = Field(None, description="SPF/DKIM/DMARC + domain alignment, when headers were supplied")
    analyzed_urls: Optional[List[str]] = Field(None, description="Every URL scored for an email")
    confidence_detail: Optional[Dict] = Field(None, description="Confidence level + which signals had no usable evidence")
    counterfactual: Optional[Dict] = Field(None, description="Minimal signal change that would flip the verdict")
    evidence_graph: Optional[Dict] = Field(None, description="Nodes/edges: verdict -> signals -> individual evidence")
    storyline: Optional[Dict] = Field(None, description="Narrative redirect/attack-chain reconstruction, for emails with multiple links")


class FlagForReviewRequest(BaseModel):
    verdict_id: str = Field(..., min_length=1, max_length=64)
    note: Optional[str] = Field(None, max_length=500)
    source: Literal["web", "extension", "api"] = "web"


class ReviewResolveRequest(BaseModel):
    outcome: Literal["upheld", "overturned"] = Field(..., description="Analyst's final call on the flagged verdict")
    actual_label: Optional[Verdict] = Field(None, description="Required when outcome is 'overturned'")
    note: Optional[str] = Field(None, max_length=500)


class BatchItem(BaseModel):
    input: str
    verdict_id: str
    verdict: Verdict
    confidence: float
    top_reasons: List[str]
    override: Optional[Literal["allowlist", "denylist"]] = None


class BatchResponse(BaseModel):
    count: int
    summary: Dict[str, int]
    results: List[BatchItem]


class FeedbackRequest(BaseModel):
    verdict_id: str = Field(..., min_length=1, max_length=64)
    is_correct: bool
    actual_label: Optional[Verdict] = Field(None, description="If the verdict was wrong, what it should have been")
    source: Literal["web", "extension", "api"] = "web"


class FeedbackResponse(BaseModel):
    status: str
    message: str


class ListEntryCreate(BaseModel):
    kind: Literal["allow", "deny"]
    domain: str = Field(..., min_length=1, max_length=300)
    note: Optional[str] = Field(None, max_length=200)

    @field_validator("domain")
    @classmethod
    def _v(cls, v: str) -> str:
        d = normalize_domain(v)
        if not d:
            raise ValueError("not a valid domain or IP address")
        return d


class ListEntryOut(BaseModel):
    id: int
    kind: str
    domain: str
    note: Optional[str] = None
    created_by: Optional[str] = None
    created_at: Optional[str] = None
