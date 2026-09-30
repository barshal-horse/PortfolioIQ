"""ID coercion helpers.

Service functions accept both str and uuid.UUID identifiers; SQLAlchemy's
UUID bind processor requires uuid.UUID objects, so coerce defensively at
service entry points (mirrors stress_testing_engine._to_uuid).
"""

import uuid


def to_uuid(value: uuid.UUID | str | None) -> uuid.UUID:
    """Coerce a value to uuid.UUID. Raises ValueError on invalid input."""
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str):
        return uuid.UUID(value)
    raise ValueError(f"Invalid identifier: {value!r}")
