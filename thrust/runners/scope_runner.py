from collections.abc import Callable

from scope.scope_config import ScopeConfig
from scope.scope_session import ScopeSessionResult, run_scope_session


def run_scope(
    config: ScopeConfig,
    log_callback: Callable[[str], None] | None = None,
    state_callback: Callable[[str], None] | None = None,
) -> ScopeSessionResult:
    return run_scope_session(config, log_callback=log_callback, state_callback=state_callback)
