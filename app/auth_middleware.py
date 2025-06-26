import os
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv
# Load environment variables
load_dotenv()
from app.custom_logging import logger
class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # List of public paths that do not require authentication
        public_paths = ['/', '/health', '/docs', '/openapi.json']
        if request.url.path in public_paths:
            return await call_next(request)
        auth_token = os.getenv("AUTH_TOKEN")
        headers_lower = {k.lower(): v for k, v in request.headers.items()}
        header_token = headers_lower.get("authorization")
        if not auth_token or header_token != auth_token:
            logger.warning("Unauthorized access attempt")
            return JSONResponse(status_code=401, content={"detail": "Unauthorized"})
        response = await call_next(request)
        return response
