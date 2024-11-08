"""
Logging Configuration for Python-based Services
"""
import logging
from sys import stdout
from typing import Optional

from fastapi_sugar.logging.conf import PRODUCTION_FORMAT
from fastapi_sugar.settings import AppSettings
from fastapi_sugar.utils import register_global_object, GlobalObjectProxy
from loguru import logger as loguru_logger
from rich.logging import RichHandler

# Global logger instance we can import in other modules
logger = loguru_logger.bind(request_id=None, method=None)


class InterceptHandler(logging.Handler):
    """
    Intercept FastAPI logging calls (with standard logging) into our Loguru Sink
    See: https://github.com/Delgan/loguru#entirely-compatible-with-standard-logging
    """

    def emit(self, record):
        """
        Intercept a record into the loguru sink

        :param record: The log record to intercept
        :return: None
        """
        level = loguru_logger.level(record.levelname).name
        frame, depth = logging.currentframe(), 2
        while frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        log = loguru_logger.bind(request_id="app")
        log.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


@register_global_object(dependencies=[AppSettings])
class Logger(GlobalObjectProxy):
    """
    Custom Logger that intercepts existing logging calls to simplify configuration options
    """

    def __init__(self, app_settings: AppSettings):
        """
        Initialize the Logger with application settings

        :param app_settings: Application settings containing logging configuration
        """
        super().__init__()
        self.settings = app_settings
        self.standard_targets = set(app_settings.get('logging_standard_targets', set()))
        self.suppress_targets = set(app_settings.get('logging_suppress_targets', set()))
        self.all_targets = self.standard_targets.union(self.suppress_targets)

    @staticmethod
    def rich_handler():
        class CustomHandler(RichHandler):
            def handle(self, record):
                record.msg = record.msg.replace('[', '\[')
                super().handle(record)

        return CustomHandler(markup=True, rich_tracebacks=True, omit_repeated_times=False)

    def _setup_proxy_impl(self) -> None:
        """
        Setup the logger instance

        :return: None
        """
        loguru_logger.remove()

        # Production Logging Configuration
        if not self.settings.debug:
            loguru_logger.add(
                stdout,
                format=PRODUCTION_FORMAT,
                level=self.settings.get("logging_level", "INFO"),

            )
        else:
            loguru_logger.add(
                self.rich_handler(),
                level=self.settings.get("logging_level", "DEBUG"),
                format="{message}"
            )

        logging.basicConfig(handlers=[InterceptHandler()], level=logging.DEBUG)

        for module in self.all_targets:
            module_logger = logging.getLogger(module)
            if module in self.suppress_targets:
                module_logger.setLevel(logging.WARNING)  # Suppress Verbose Output
            module_logger.propagate = False
            module_logger.handlers = [InterceptHandler()]

        self._instance = logger

    @classmethod
    def param_name(cls) -> Optional[str]:
        # Skip injection of the logger as we are making it globally available
        return None
