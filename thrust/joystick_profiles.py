"""Stable local profile identifiers for joystick-specific axis assignments."""
from __future__ import annotations

import hashlib


def joystick_profile_key(guid: str | None, name: str | None) -> str | None:
    """Return a settings-safe key based on a joystick GUID or its published name."""
    guid_value = str(guid or "").strip().casefold()
    name_value = str(name or "").strip().casefold()
    identity = f"guid:{guid_value}" if guid_value else f"name:{name_value}"
    if identity in {"guid:", "name:"}:
        return None
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()[:24]
