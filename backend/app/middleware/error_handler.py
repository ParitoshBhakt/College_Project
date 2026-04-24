import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.utils.exceptions import SentiFaceError


logger = logging.getLogger("sentiface.errors")


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(SentiFaceError)
    async def sentiface_exception_handler(_: Request, exc: SentiFaceError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"success": False, "error": {"code": exc.code, "message": exc.message}},
        )

    @app.exception_handler(Exception)
    async def unexpected_handler(_: Request, exc: Exception):
        logger.exception("Unhandled exception", exc_info=exc)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {"code": "INTERNAL_SERVER_ERROR", "message": "Unexpected server error."},
            },
        )