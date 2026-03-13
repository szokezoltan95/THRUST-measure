from collections.abc import Callable

from scope.scope_config import ScopeConfig
from scope.scope_session import run_scope_session


def run_scope(config: ScopeConfig, log_callback: Callable[[str], None] | None = None) -> None:
    run_scope_session(config, log_callback=log_callback)