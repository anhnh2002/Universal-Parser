"""
File summary analyzer for code graphs.

This module provides functionality to generate file summaries showing only
the first line of each node with elide messages for the remaining content.
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from pathlib import Path
import os

from .graph_analyzer import GraphAnalyzer, GraphNode
from ..utils.logger import logger


class FileSummary:
    """Container for file summary analysis results."""
    
    def __init__(self, file_path: str, repo_path: Optional[str] = None):
        self.file_path = file_path
        self.repo_path = repo_path
        self.nodes: List[GraphNode] = []
        self.total_lines: Optional[int] = None
        self.file_exists: bool = False
    
    def add_node(self, node: GraphNode):
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
        file_path: str, 
        repo_path: Optional[str] = None
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
        normalized_path = self._normalize_file_path(file_path, repo_path)
        
        logger.info(f"Analyzing file summary for: {normalized_path}")
        
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
        summary = FileSummary(normalized_path, repo_path)
        
        for node in nodes_in_file:
            summary.add_node(node)
        
        # Try to get actual file line count if file exists
        if repo_path:
            full_file_path = Path(repo_path) / normalized_path
            if full_file_path.exists():
                summary.file_exists = True
                try:
                    with open(full_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                        summary.total_lines = sum(1 for _ in f)
                except Exception as e:
                    logger.warning(f"Could not read file {full_file_path}: {e}")
        
        logger.info(f"Found {summary.get_total_nodes()} nodes in file: {normalized_path}")
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
        show_line_numbers: bool = True,
        show_node_types: bool = True,
    ) -> str:
        """
        Format the file summary as a readable string with elide messages.
        
        Args:
            summary: The file summary result
            show_line_numbers: Whether to show line numbers
            show_node_types: Whether to show node types
            
        Returns:
            Formatted string representation
        """
        lines = []
        lines.append(f"File Summary: {summary.file_path}")
        lines.append(f"Total Nodes: {summary.get_total_nodes()}")
        if summary.total_lines:
            lines.append(f"Total File Lines: {summary.total_lines}")
        lines.append("=" * 60)
        
        if not summary.nodes:
            lines.append("No nodes found in this file.")
            return '\n'.join(lines)
        
        # Sort nodes by start line (should already be sorted from graph_analyzer)
        sorted_nodes = sorted(summary.nodes, key=lambda n: n.start_line)
        
        current_line = 1
        
        for i, node in enumerate(sorted_nodes):
            # Show elide message for lines before this node
            # if current_line < node.start_line:
            #     elided_lines = node.start_line - current_line
            #     if elided_lines > 0:
            #         lines.append(f"... eliding lines {current_line}–{node.start_line - 1} ...")
            #         lines.append("")
            
            # Show the node's first line
            first_line = node.get_first_line().strip()
            
            # Format the node display
            node_info = []
            if show_line_numbers:
                if node.start_line == node.end_line:
                    node_info.append(f"L{node.start_line}")
                else:
                    node_info.append(f"L{node.start_line}-{node.end_line}")
            
            if show_node_types:
                node_info.append(f"[{node.type}]")
            
            node_info.append(f"({node.id})")
            
            info_str = " ".join(node_info)
            lines.append(f"{info_str}")
            lines.append(f"{first_line}")
            
            # Show elide message for remaining lines in this node (if any)
            if node.end_line > node.start_line:
                elided_in_node = node.end_line - node.start_line
                lines.append(f"... eliding {elided_in_node} more lines ...")
            
            lines.append("")  # Empty line between nodes
            
            # Update current line position
            current_line = node.end_line + 1
        
        # Show elide message for any remaining lines in the file
        if summary.total_lines and current_line <= summary.total_lines:
            elided_at_end = summary.total_lines - current_line + 1
            if elided_at_end > 0:
                lines.append(f"... eliding lines {current_line}–{summary.total_lines} ...")
        
        return '\n'.join(lines)
    
    def export_file_summary_json(self, summary: FileSummary, output_path: str):
        """
        Export the file summary to a JSON file.
        
        Args:
            summary: The file summary result
            output_path: Path to save the JSON file
        """
        import json
        
        # Build the export data structure
        export_data = {
            "analysis_type": "file_summary",
            "file_path": summary.file_path,
            "repo_path": summary.repo_path,
            "total_nodes": summary.get_total_nodes(),
            "total_file_lines": summary.total_lines,
            "file_exists": summary.file_exists,
            "nodes": []
        }
        
        # Add detailed node information
        for node in summary.nodes:
            export_data["nodes"].append({
                "id": node.id,
                "type": node.type,
                "start_line": node.start_line,
                "end_line": node.end_line,
                "first_line": node.get_first_line(),
                "full_code_snippet": node.code_snippet
            })
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"File summary exported to: {output_path}")
    
    def analyze_multiple_files(
        self, 
        file_paths: List[str], 
        repo_path: Optional[str] = None
    ) -> Dict[str, FileSummary]:
        """
        Analyze multiple files and generate summaries.
        
        Args:
            file_paths: List of file paths to analyze
            repo_path: Optional absolute path to the repository root
            
        Returns:
            Dictionary mapping file paths to their summaries
        """
        results = {}
        
        for file_path in file_paths:
            try:
                summary = self.analyze_file_summary(file_path, repo_path)
                results[file_path] = summary
            except ValueError as e:
                logger.warning(f"Could not analyze file {file_path}: {e}")
                # Create empty summary for failed files
                results[file_path] = FileSummary(file_path, repo_path)
        
        return results
    
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