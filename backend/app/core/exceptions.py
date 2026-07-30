"""Domain-level errors and the handlers that translate them into HTTP responses.

Services raise these instead of `HTTPException`, so business logic stays free of
web-framework concerns while routes still return correct status codes.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)


class AppError(Exception):
    """Base class for expected, client-facing failures."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    detail: str = "Request could not be processed."

    def __init__(self, detail: str | None = None) -> None:
        if detail:
            self.detail = detail
        super().__init__(self.detail)


class InvalidCredentialsError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Incorrect email or password."


class NotAuthenticatedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    detail = "Not authenticated."


class EmailAlreadyRegisteredError(AppError):
    status_code = status.HTTP_409_CONFLICT
    detail = "An account with this email already exists."


class DocumentNotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    detail = "Document not found."


class UnsupportedFileTypeError(AppError):
    status_code = status.HTTP_415_UNSUPPORTED_MEDIA_TYPE
    detail = "Unsupported file type. Upload a PDF, DOCX, or TXT file."


class FileTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    detail = "File is too large."


class EmptyFileError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "The uploaded file is empty."


class TextExtractionError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "No readable text could be extracted from this file."


class NoDocumentsError(AppError):
    status_code = status.HTTP_400_BAD_REQUEST
    detail = "Upload and process a document before asking questions."


class LLMUnavailableError(AppError):
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    detail = "The AI service is temporarily unavailable. Please try again."


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_error(request: Request, exc: StarletteHTTPException):
        return await http_exception_handler(request, exc)

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Log the real cause but never leak internals to the client.
        logger.exception("Unhandled error: %s", exc)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An unexpected error occurred."},
        )
