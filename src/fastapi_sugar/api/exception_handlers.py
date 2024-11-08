from typing import Union

from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY


def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
    """
    Handles HTTPExceptions by returning a JSON response with error details.
    """
    return JSONResponse(
        {"errors": [exc.detail]},
        status_code=exc.status_code
    )


def http422_error_handler(
    _: Request,
    exc: Union[RequestValidationError, ValidationError],
) -> JSONResponse:
    """
    Handles RequestValidationError and ValidationError by returning a JSON response with error details.
    """
    return JSONResponse(
        {"errors": exc.errors()},
        status_code=HTTP_422_UNPROCESSABLE_ENTITY,
    )


def register_exc_handlers(app):
    app.add_exception_handler(HTTPException, http_error_handler)
    app.add_exception_handler(RequestValidationError, http422_error_handler)

