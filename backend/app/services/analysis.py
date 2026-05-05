from backend.app.schemas.analysis import AnalysisRequest, AnalysisResponse, GeneratedListing, PurchaseCriterion


async def analyze_product(request: AnalysisRequest) -> AnalysisResponse:
    """Placeholder analysis pipeline for the initial scaffold."""
    return AnalysisResponse(
        product_url=str(request.product_url),
        competitor_count=len(request.competitor_urls),
        review_limit=request.review_limit,
        purchase_criteria=[
            PurchaseCriterion(
                name="Durability",
                importance=0.91,
                evidence=["Built to last", "Feels sturdy", "Held up after daily use"],
            ),
            PurchaseCriterion(
                name="Ease of use",
                importance=0.84,
                evidence=["Simple setup", "Works right out of the box"],
            ),
        ],
        hooks=[
            "Built for everyday use",
            "Simple setup in minutes",
            "Premium feel without the premium hassle",
        ],
        estimated_monthly_revenue=None,
        generated_listing=GeneratedListing(
            title="Optimized Amazon Product Title Placeholder",
            bullets=[
                "Built around the purchase criteria customers mention most.",
                "Designed to address common objections found in competitor reviews.",
                "Positioned with customer-language hooks for stronger conversion.",
            ],
            description="Listing copy generation will be powered by Claude once the analysis service is connected.",
        ),
    )
