"""
This module provides a global object for application settings. It uses Dynaconf to load settings from a TOML file,
environment variables, and AWS SSM parameters.
"""
import os
from typing import Any

from cogento_core.exceptions import ConfigurationError
from cogento_core.utils import register_global_object, GlobalObjectProxy
from dynaconf import Dynaconf


@register_global_object()
class AppSettings(GlobalObjectProxy):
    def __init__(self, settings_files=("../settings.toml", "../.secrets.toml")):
        super().__init__()
        self.prefix = os.environ.get('APP_NAME', 'app').upper()
        self.settings_files = settings_files

    def _setup_proxy_impl(self):
        self._instance = Dynaconf(
            environments=False,
            envvar_prefix=self.prefix,
            settings_files=self.settings_files,
            LOADERS_FOR_DYNACONF=[
                "dynaconf.loaders.toml_loader",
                "dynaconf.loaders.env_loader"
            ]
        )

    def _generate_error_message(self, key: str) -> str:
        return (
            f"Setting '{key}' not found in configuration.\n"
            f"Please check the following:\n"
            f"1. The setting is defined in one of these files: {', '.join(self.settings_files)}\n"
            f"\tExample: {key} = 'value'\n"
            f"2. If it's an environment variable, ensure it's prefixed with '{self.prefix}_'\n"
            f"\tExample: export {self.prefix.upper()}_{key.upper()}='value'\n"
            f"3. Check for typos in the setting name\n"
            f"If the setting is optional, consider using the .get() method with a default value."
        )

    def __getattr__(self, name: str) -> Any:
        try:
            return super().__getattr__(name)
        except AttributeError:
            raise ConfigurationError(self._generate_error_message(name)) from None

    def __getitem__(self, item: str) -> Any:
        try:
            return super().__getitem__(item)
        except KeyError:
            raise ConfigurationError(self._generate_error_message(item)) from None
