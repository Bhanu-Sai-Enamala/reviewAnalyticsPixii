from typing import Optional

from pydantic import BaseModel, Field, HttpUrl


class AnalysisRequest(BaseModel):
    product_url: HttpUrl
    competitor_urls: list[HttpUrl] = Field(default_factory=list, max_length=9)
    review_limit: int = Field(default=1000, ge=100, le=5000)


class PurchaseCriterion(BaseModel):
    name: str
    importance: float
    evidence: list[str]


class GeneratedListing(BaseModel):
    title: str
    bullets: list[str]
    description: str


class AnalysisResponse(BaseModel):
    product_url: str
    competitor_count: int
    review_limit: int
    purchase_criteria: list[PurchaseCriterion]
    hooks: list[str]
    estimated_monthly_revenue: Optional[float]
    generated_listing: GeneratedListing
