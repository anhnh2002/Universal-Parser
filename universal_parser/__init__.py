"""
DeepWiki Parser: A tool for extracting structured information from codebases.

This package provides functionality to parse repositories and extract nodes and edges
representing code structure, dependencies, and relationships.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .parsing.repository import RepositoryParser, parse_repository_incremental_main
from .core.models import Node, Edge

__all__ = [
    "RepositoryParser",
    "parse_repository_incremental_main", 
    "Node",
    "Edge"
] 