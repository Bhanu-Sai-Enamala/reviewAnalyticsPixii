from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.routes import router
from backend.app.core.config import settings


app = FastAPI(
    title="Review Analytics API",
    version="0.1.0",
    description="Scrape Amazon listings, analyze reviews, and generate optimized listing copy.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/")
def root() -> dict[str, str]:
    return {"status": "ok", "service": "review-analytics-api"}
