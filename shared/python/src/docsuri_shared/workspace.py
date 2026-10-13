"""Canonical workspace wire types from the pinned shared binding generation."""
from ._generated.dtos import workspace_schema as wire
from ._generated.events import execution_schema as execution

__all__ = ['wire', 'execution']
