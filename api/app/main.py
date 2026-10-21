from fastapi import FastAPI

from app.routes import health

app = FastAPI(title="laila-majnu API", docs_url=None, redoc_url=None, openapi_url=None)
app.include_router(health.router, prefix="/v1")
