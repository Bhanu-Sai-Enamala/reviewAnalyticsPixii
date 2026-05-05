from fastapi import APIRouter

from backend.app.schemas.analysis import AnalysisRequest, AnalysisResponse
from backend.app.services.analysis import analyze_product

router = APIRouter()


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "healthy"}


@router.post("/analyze", response_model=AnalysisResponse)
async def create_analysis(request: AnalysisRequest) -> AnalysisResponse:
    return await analyze_product(request)
