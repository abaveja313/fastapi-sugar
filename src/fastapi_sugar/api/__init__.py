import textwrap
from typing import Callable

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_sugar.api.exception_handlers import register_exc_handlers
from fastapi_sugar.api.logging_context_middleware import LoggingContextMiddleware
from fastapi_sugar.logging import logger
from fastapi_sugar.settings import AppSettings
from fastapi_sugar.utils import global_manager
from fastapi_utils.timing import add_timing_middleware


def create_fastapi_app(
    title: str,
    description: str,
    additional_routers=None,
    startup_hook: Callable[[], None] = None,
    shutdown_hook: Callable[[], None] = None
):
    app = FastAPI(
        title=title,
        description=description,
    )

    register_exc_handlers(app)
    add_timing_middleware(app, record=logger.debug, exclude="health")

    app.add_middleware(
        middleware_class=CORSMiddleware,
        allow_origins=[],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"]
    )

    app.add_middleware(
        middleware_class=LoggingContextMiddleware
    )

    # Include additional routers if provided
    if additional_routers:
        for router in additional_routers:
            app.include_router(router)

    def format_configuration():
        conf = f"""
        Service Name: {title}
        Service Description: {description}
        Service Version: {global_manager.get(AppSettings).version}
        Debug: {global_manager.get(AppSettings).debug}
        Number of Routes: {len(app.routes)}
        """
        return textwrap.dedent(conf)

    @app.on_event('startup')
    def on_startup():
        logger.info(f"Starting Application '{title}'...")
        global_manager.startup()
        logger.info("Initialized Global Dependencies")
        logger.info("Configuration:\n" + format_configuration())

        app_settings = global_manager.get(AppSettings)
        app.version = app_settings.version
        app.debug = app_settings.debug

        if startup_hook:
            logger.info("Running custom startup hook...")
            startup_hook()

    @app.on_event('shutdown')
    def on_shutdown():
        global_manager.shutdown()
        logger.info("Shutdown Global Dependencies")

        if shutdown_hook:
            logger.info("Running custom shutdown hook...")
            shutdown_hook()

    @app.get("/health", tags=["health"])
    async def health_check():
        """
        Health check endpoint
        :return: A simple JSON response
        """
        return {"status": "ok"}

    return app
