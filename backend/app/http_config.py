from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import Settings


def configure_cors(app: FastAPI, settings: Settings) -> None:
    # Origins are explicit: CORS is browser policy, not API authentication.
    # Bearer tokens travel in the Authorization header, never in cookies.
    if "*" in settings.cors_origins:
        raise ValueError("CORS_ORIGINS must list explicit origins, not '*'")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["Accept", "Authorization", "Content-Type"],
    )
