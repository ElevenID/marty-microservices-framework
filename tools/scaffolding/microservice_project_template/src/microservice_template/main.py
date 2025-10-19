"""CLI entrypoint for the microservice template."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Iterable
from contextlib import suppress

import structlog
import uvloop
from microservice_template import __version__
from microservice_template.config import AppSettings
from microservice_template.observability import configure_logging, configure_tracer
from microservice_template.server import serve


def cli(argv: Iterable[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    settings = AppSettings()
    configure_logging(settings.service_name, settings.log_level)
    tracer_provider = configure_tracer(settings)

    if args.command == "health":
        print("ok")
        return 0

    shutdown_after = args.shutdown_after

    if sys.platform != "win32":
        with suppress(ImportError):

            uvloop.install()

    logger = structlog.get_logger(__name__)
    logger.info(
        "service.starting",
        version=__version__,
        environment=settings.environment,
        grpc_bind=settings.grpc_bind,
    )

    try:
        asyncio.run(serve(settings, shutdown_after=shutdown_after))
    finally:
        if tracer_provider is not None:
            tracer_provider.shutdown()

    logger.info("service.stopped")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Microservice Template CLI")
    subparsers = parser.add_subparsers(dest="command")

    serve_parser = subparsers.add_parser("serve", help="Run the gRPC server")
    serve_parser.set_defaults(command="serve")
    serve_parser.add_argument(
        "--shutdown-after",
        type=float,
        default=None,
        help="Gracefully stop the server after N seconds (useful for tests)",
    )

    health_parser = subparsers.add_parser("health", help="Quick CLI health probe")
    health_parser.set_defaults(command="health")

    parser.set_defaults(command="serve")
    return parser


if __name__ == "__main__":
    raise SystemExit(cli())
