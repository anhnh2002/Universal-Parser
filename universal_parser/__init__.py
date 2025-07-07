"""
DeepWiki Parser: A tool for extracting structured information from codebases.

This package provides functionality to parse repositories and extract nodes and edges
representing code structure, dependencies, and relationships.
"""

__version__ = "0.1.0"
__author__ = "Your Name"
__email__ = "your.email@example.com"

from .parse_repository import RepositoryParser, parse_repository_main
from .schema import Node, Edge

__all__ = [
    "RepositoryParser",
    "parse_repository_main", 
    "Node",
    "Edge"
] 