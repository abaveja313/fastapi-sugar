import uuid

import fastapi_sugar.logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


class LoggingContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Generate a unique request ID
        request_id = str(uuid.uuid4())
        request_path = request.url.path
        # Bind the request ID to the logger's context
        fastapi_sugar.logging.logger = fastapi_sugar.logging.logger.bind(request_id=request_id, path=request_path)
        request.state.request_id = request_id

        response = await call_next(request)
        fastapi_sugar.logging.logger = fastapi_sugar.logging.logger.bind(request_id=None, path=None)

        response.headers["X-Request-ID"] = request_id
        return response
