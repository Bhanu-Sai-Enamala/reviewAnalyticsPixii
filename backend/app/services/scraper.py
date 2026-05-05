from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ScrapedProduct:
    url: str
    asin: Optional[str] = None
    title: Optional[str] = None
    price: Optional[float] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    reviews: list[str] = field(default_factory=list)


async def scrape_product(url: str, review_limit: int = 1000) -> ScrapedProduct:
    """Placeholder for Playwright or Bright Data scraping implementation."""
    return ScrapedProduct(url=url, reviews=[])
