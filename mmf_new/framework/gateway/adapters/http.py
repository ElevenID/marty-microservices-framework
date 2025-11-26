"""
FastAPI Adapter for Gateway
"""

from fastapi import APIRouter, Request, Response
from ..ports.input import RequestHandlerPort
from ..domain.models import GatewayRequest, HTTPMethod

class FastAPIAdapter:
    """FastAPI adapter for the gateway."""

    def __init__(self, handler: RequestHandlerPort):
        self.handler = handler
        self.router = APIRouter()
        self.router.add_api_route("/{path:path}", self.handle, methods=["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"])

    async def handle(self, path: str, request: Request) -> Response:
        """Handle incoming FastAPI request."""
        # Convert FastAPI Request to GatewayRequest
        body = await request.body()

        # Handle query params - convert from QueryParams to dict[str, list[str]]
        query_params = {}
        for key, value in request.query_params.multi_items():
            if key not in query_params:
                query_params[key] = []
            query_params[key].append(value)

        gateway_request = GatewayRequest(
            method=HTTPMethod(request.method),
            path=f"/{path}",
            query_params=query_params,
            headers=dict(request.headers),
            body=body,
            client_ip=request.client.host if request.client else None
        )

        # Handle request
        gateway_response = await self.handler.handle_request(gateway_request)

        # Convert GatewayResponse to FastAPI Response
        return Response(
            content=gateway_response.body,
            status_code=gateway_response.status_code,
            headers=gateway_response.headers
        )
