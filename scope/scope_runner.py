from scope.scope_config import ScopeConfig
from scope.scope_session import run_scope_session


def run_scope(config: ScopeConfig) -> None:
    run_scope_session(config)