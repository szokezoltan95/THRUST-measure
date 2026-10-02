from collections.abc import Callable
from typing import Any

from simple.simple_config import SimpleConfig
from simple.simple_session import SimpleSessionResult, run_simple_session


def run_simple(
    config: SimpleConfig,
    runtime: dict[str, Any],
    *,
    participant: str,
    profile_name: str,
    log_callback: Callable[[str], None] | None = None,
    state_callback: Callable[[str], None] | None = None,
) -> SimpleSessionResult:
    return run_simple_session(
        config, runtime, participant=participant, profile_name=profile_name,
        log_callback=log_callback,
        state_callback=state_callback,
    )
