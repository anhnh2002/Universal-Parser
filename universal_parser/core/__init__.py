"""Core functionality for the universal parser."""

from .models import Node, Edge
from .config import update_config, LLM_API_KEY, LLM_MODEL, LLM_BASE_URL

__all__ = [
    "Node",
    "Edge", 
    "update_config",
    "LLM_API_KEY",
    "LLM_MODEL", 
    "LLM_BASE_URL"
] 