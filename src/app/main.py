"""Unified CLI Entrypoint for JARVIS AI Agent.

Starts the FastAPI server and optional GUI window/browser.
"""

import argparse
import sys
import uvicorn
from config.settings import settings, get_logger
from src.app.api import app
from src.app.ui import launch_desktop_window, open_browser_delayed

logger = get_logger("Main")


def parse_args():
    parser = argparse.ArgumentParser(description="JARVIS AI Agent Application")
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind (default: 8000)"
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run API server only without launching UI"
    )
    parser.add_argument(
        "--desktop",
        action="store_true",
        help="Launch desktop window via PyWebView if available"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable uvicorn auto-reload for local development"
    )
    return parser.parse_args()


def main():
    args = parse_args()
    url = f"http://{args.host}:{args.port}"

    logger.info("=" * 60)
    logger.info("  🚀 Starting JARVIS AI Agent (Python Architecture v2.0)")
    logger.info(f"  Active Model: {settings.llm.default_model}")
    logger.info(f"  API & UI URL: {url}")
    logger.info("=" * 60)

    if not args.headless:
        if args.desktop:
            # Desktop window will run in main thread, so run uvicorn in a background thread
            import threading
            server_config = uvicorn.Config(app=app, host=args.host, port=args.port, log_level="warning")
            server = uvicorn.Server(server_config)
            server_thread = threading.Thread(target=server.run, daemon=True)
            server_thread.start()

            # Start desktop window
            launch_desktop_window(url, title="Jarvis - AI Assistant")
            return
        else:
            open_browser_delayed(url, delay_seconds=1.2)

    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
