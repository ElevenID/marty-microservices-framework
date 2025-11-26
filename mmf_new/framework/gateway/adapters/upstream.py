"""
Upstream Adapter for Gateway
"""

import aiohttp
from ..ports.output import UpstreamClientPort
from ..domain.models import GatewayRequest, GatewayResponse, UpstreamServer

class AIOHTTPUpstreamAdapter(UpstreamClientPort):
    """AIOHTTP implementation of UpstreamClientPort."""

    async def send_request(self, server: UpstreamServer, request: GatewayRequest) -> GatewayResponse:
        url = f"{server.url}{request.path}"

        # Convert query params to list of tuples for aiohttp
        params = []
        for key, values in request.query_params.items():
            for value in values:
                params.append((key, value))

        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=request.method.value,
                url=url,
                headers=request.headers,
                params=params,
                data=request.body
            ) as response:
                body = await response.read()
                return GatewayResponse(
                    status_code=response.status,
                    headers=dict(response.headers),
                    body=body
                )
