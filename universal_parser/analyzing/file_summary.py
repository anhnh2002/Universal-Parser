"""
File summary analyzer for code graphs.

This module provides functionality to generate file summaries showing only
the first line of each node with elide messages for the remaining content.
"""

from typing import List, Optional
from pathlib import Path
import os

from .graph_analyzer import GraphAnalyzer
from ..core.models import Node
from ..utils.logger import logger


class FileSummary:
    """Container for file summary analysis results."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nodes: List[Node] = []
        self.total_lines: Optional[int] = None
        self.file_exists: bool = False
    
    def add_node(self, node: Node):
        """Add a node to the summary."""
        self.nodes.append(node)
    
    def get_total_nodes(self) -> int:
        """Get total number of nodes in the file."""
        return len(self.nodes)


class FileSummaryAnalyzer:
    """Analyzer for generating file summaries."""
    
    def __init__(self, graph_analyzer: GraphAnalyzer):
        """
        Initialize the file summary analyzer.
        
        Args:
            graph_analyzer: The base graph analyzer instance
        """
        self.graph = graph_analyzer
    
    def analyze_file_summary(
        self, 
        file_path: str
    ) -> FileSummary:
        """
        Analyze a file and generate a summary.
        
        Args:
            file_path: Path to the file to analyze (relative to repo or absolute)
            repo_path: Optional absolute path to the repository root
            
        Returns:
            FileSummary containing the analysis results
            
        Raises:
            ValueError: If the file is not found in the graph
        """
        # Normalize the file path
        normalized_path = self._normalize_file_path(file_path)
        
        logger.debug(f"Analyzing file summary for: {normalized_path}")
        
        # Get nodes in the file
        nodes_in_file = self.graph.get_nodes_in_file(normalized_path)
        
        if not nodes_in_file:
            # Try to find the file with different path formats
            possible_paths = self._find_possible_file_paths(file_path)
            for possible_path in possible_paths:
                nodes_in_file = self.graph.get_nodes_in_file(possible_path)
                if nodes_in_file:
                    normalized_path = possible_path
                    break
            
            if not nodes_in_file:
                available_files = self.graph.get_files_list()
                raise ValueError(
                    f"File '{file_path}' not found in graph. "
                    f"Available files: {', '.join(available_files[:10])}{'...' if len(available_files) > 10 else ''}"
                )
        
        # Create the summary
        summary = FileSummary(normalized_path)
        
        for node in nodes_in_file:
            summary.add_node(node)
        
        logger.debug(f"Found {summary.get_total_nodes()} nodes in file: {normalized_path}")
        return summary
    
    def _normalize_file_path(self, file_path: str, repo_path: Optional[str] = None) -> str:
        """Normalize file path for consistent lookup."""
        # Remove leading slashes and normalize
        normalized = file_path.lstrip('/')
        
        # If absolute path provided and repo_path given, make it relative to repo
        if file_path.startswith('/') and repo_path:
            repo_path_obj = Path(repo_path).resolve()
            file_path_obj = Path(file_path).resolve()
            try:
                normalized = str(file_path_obj.relative_to(repo_path_obj))
            except ValueError:
                # File is not under repo_path, use as-is
                pass
        
        return normalized
    
    def _find_possible_file_paths(self, file_path: str) -> List[str]:
        """Find possible file paths that might match the given path."""
        available_files = self.graph.get_files_list()
        possible_paths = []
        
        # Normalize the search path
        search_path = file_path.lstrip('/')
        search_name = os.path.basename(search_path)
        
        for available_file in available_files:
            # Exact match
            if available_file == search_path:
                possible_paths.append(available_file)
            # Filename match
            elif os.path.basename(available_file) == search_name:
                possible_paths.append(available_file)
            # Suffix match
            elif available_file.endswith(search_path):
                possible_paths.append(available_file)
        
        return possible_paths
    
    def format_file_summary(
        self, 
        summary: FileSummary,
        k: int = 5
    ) -> str:
        """
        Format the file summary as a readable string with elide messages.
        
        Args:
            summary: The file summary result
            k: Number of first lines to show
            
        Returns:
            Formatted string representation
        """
        lines = []
        
        if not summary.nodes:
            lines.append("No nodes found in this file.")
            return '\n'.join(lines)
        
        # Sort nodes by start line (should already be sorted from graph_analyzer)
        sorted_nodes = sorted(summary.nodes, key=lambda n: n.start_line)
        
        current_line = 1
        
        for i, node in enumerate(sorted_nodes):
            
            # Show the node's first lines with line numbers
            k_first_lines = node.get_k_first_line(k=k)
            numbered_lines = []
            for line_idx, line in enumerate(k_first_lines):
                line_number = node.start_line + line_idx + 1
                numbered_lines.append(f"{line_number:6}\t{line}")
            k_first_line = "\n".join(numbered_lines)
            
            lines.append(node.__repr__(include_absolute_path=False))
            lines.append(f"{k_first_line}")
            
            # Show elide message for remaining lines in this node (if any)
            if node.end_line > node.start_line + k:
                elided_in_node = node.end_line - node.start_line - k
                lines.append(f"\t... eliding {elided_in_node} more lines ...")
            
            lines.append("")  # Empty line between nodes
            
            # Update current line position
            current_line = node.end_line + 1
        
        # Show elide message for any remaining lines in the file
        if summary.total_lines and current_line <= summary.total_lines:
            elided_at_end = summary.total_lines - current_line + 1
            if elided_at_end > 0:
                lines.append(f"... eliding lines {current_line}–{summary.total_lines} ...")
        
        return '\n'.join(lines)
    
    def get_available_files(self) -> List[str]:
        """Get list of all files available for analysis."""
        return self.graph.get_files_list()
    
    @classmethod
    def from_aggregated_results(cls, aggregated_results_path: str) -> "FileSummaryAnalyzer":
        """
        Create a FileSummaryAnalyzer from an aggregated results file.
        
        Args:
            aggregated_results_path: Path to the aggregated results JSON file
            
        Returns:
            FileSummaryAnalyzer instance
        """
        graph_analyzer = GraphAnalyzer(aggregated_results_path)
        return cls(graph_analyzer) 