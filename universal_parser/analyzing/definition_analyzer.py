"""
Definition analyzer for code graphs.

This module provides functionality to analyze a specific node definition,
including its code snippet, dependents (nodes that depend on it), and 
dependencies (nodes it depends on).
"""

import os
from typing import Dict, List, Set, Optional, Any, Tuple
from pathlib import Path

from .graph_analyzer import GraphAnalyzer
from ..core.models import Node, Edge
from ..utils.logger import logger


class DefinitionAnalysis:
    """Container for definition analysis results."""
    
    def __init__(self, node: Node):
        self.node = node
        self.dependents: List[Tuple[Node, List[str]]] = []  # (node, edge_types)
        self.dependencies: List[Tuple[Node, List[str]]] = []  # (node, edge_types)
    
    def add_dependent(self, node: Node, edge_types: List[str]):
        """Add a node that depends on this node with its edge types."""
        self.dependents.append((node, edge_types))
    
    def add_dependency(self, node: Node, edge_types: List[str]):
        """Add a node that this node depends on with its edge types."""
        self.dependencies.append((node, edge_types))
    
    def get_total_dependents(self) -> int:
        """Get total number of dependents."""
        return len(self.dependents)
    
    def get_total_dependencies(self) -> int:
        """Get total number of dependencies."""
        return len(self.dependencies)


class DefinitionAnalyzer:
    """Analyzer for getting detailed information about specific node definitions."""
    
    def __init__(self, graph_analyzer: GraphAnalyzer):
        """
        Initialize the definition analyzer.
        
        Args:
            graph_analyzer: The base graph analyzer instance
        """
        self.graph = graph_analyzer
    
    def get_definition_analysis(
        self, 
        absolute_file_path: str, 
        node_name: str
    ) -> DefinitionAnalysis:
        """
        Analyze a specific node definition by file path and node name.
        
        Args:
            absolute_file_path: Absolute path to the file containing the node
            node_name: Name of the node (e.g., "SearchProvider", "ClassName.method_name")
            
        Returns:
            DefinitionAnalysis containing the analysis results
            
        Raises:
            ValueError: If the node is not found in the graph
        """
        # Convert absolute path to relative path
        repo_info = self.graph.get_repository_info()
        repo_path = repo_info.get("path", "")
        
        if not repo_path:
            raise ValueError("Repository path not found in graph data")
        
        try:
            relative_file_path = str(Path(absolute_file_path).relative_to(repo_path))
        except ValueError:
            raise ValueError(f"File '{absolute_file_path}' is not within repository '{repo_path}'")
        
        logger.debug(f"Analyzing definition for node '{node_name}' in file: {relative_file_path}")
        
        # Find the specific node
        target_node = self._find_node_by_name_and_file(relative_file_path, node_name)
        
        if not target_node:
            available_nodes = self._get_available_nodes_in_file(relative_file_path)
            raise ValueError(
                f"Node '{node_name}' not found in file '{relative_file_path}'. "
                f"Available nodes: {', '.join(available_nodes[:10])}{'...' if len(available_nodes) > 10 else ''}"
            )
        
        # Create the analysis
        analysis = DefinitionAnalysis(target_node)
        
        # Get dependents (nodes that depend on this node) - incoming edges
        dependent_node_ids = self.graph.get_incoming_nodes(target_node.id)
        for dependent_id in dependent_node_ids:
            dependent_node = self.graph.get_node(dependent_id)
            if dependent_node:
                # Find all edge types between dependent and target
                edges = self.graph.find_edges_between(dependent_id, target_node.id)
                edge_types = [edge.type for edge in edges]
                analysis.add_dependent(dependent_node, edge_types)
        
        # Get dependencies (nodes this node depends on) - outgoing edges
        dependency_node_ids = self.graph.get_outgoing_nodes(target_node.id)
        for dependency_id in dependency_node_ids:
            dependency_node = self.graph.get_node(dependency_id)
            if dependency_node:
                # Find all edge types between target and dependency
                edges = self.graph.find_edges_between(target_node.id, dependency_id)
                edge_types = [edge.type for edge in edges]
                analysis.add_dependency(dependency_node, edge_types)
        
        logger.debug(
            f"Found node '{node_name}' with {analysis.get_total_dependents()} dependents "
            f"and {analysis.get_total_dependencies()} dependencies"
        )
        
        return analysis
    
    def _find_node_by_name_and_file(self, relative_file_path: str, node_name: str) -> Optional[Node]:
        """Find a node by its name within a specific file."""
        # Get all nodes in the file
        nodes_in_file = self.graph.get_nodes_in_file(relative_file_path)
        
        if not nodes_in_file:
            # Try to find the file with different path formats
            possible_paths = self._find_possible_file_paths(relative_file_path)
            for possible_path in possible_paths:
                nodes_in_file = self.graph.get_nodes_in_file(possible_path)
                if nodes_in_file:
                    relative_file_path = possible_path
                    break
        
        # Look for exact matches in node names
        for node in nodes_in_file:
            # Check if the file_level_id matches the node_name
            if node.file_level_id == node_name:
                return node
            
            # Also check if the node_name is a substring at the end of the node ID
            if node.id.endswith(f".{node_name}") or node.id.endswith(node_name):
                return node
        
        return None
    
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
    
    def _get_available_nodes_in_file(self, relative_file_path: str) -> List[str]:
        """Get list of available node names in a file."""
        nodes_in_file = self.graph.get_nodes_in_file(relative_file_path)
        
        if not nodes_in_file:
            # Try possible paths
            possible_paths = self._find_possible_file_paths(relative_file_path)
            for possible_path in possible_paths:
                nodes_in_file = self.graph.get_nodes_in_file(possible_path)
                if nodes_in_file:
                    break
        
        return [node.file_level_id for node in nodes_in_file]
    
    def format_definition_analysis(self, analysis: DefinitionAnalysis) -> str:
        """
        Format the definition analysis as a readable string.
        
        Args:
            analysis: The definition analysis result
            
        Returns:
            Formatted string representation
        """

        lines = []
        
        # Node information
        lines.append("## Node Metadata:")
        lines.append(analysis.node.__repr__(include_absolute_path=True))
        lines.append("")
        
        # Code snippet
        lines.append("## Code Snippet:")
        lines.append("```")
        code_lines = analysis.node.code_snippet.strip().split('\n')
        for line_idx, line in enumerate(code_lines):
            line_number = analysis.node.start_line + line_idx + 1
            lines.append(f"{line_number:6}\t{line}")
        lines.append("```")
        lines.append("")
        
        # Dependencies (nodes this node depends on)
        if analysis.dependencies:
            lines.append(f"## This node ({analysis.node.file_level_id}) depends on:")
            for dependency_node, edge_types in analysis.dependencies:
                edge_types_str = ", ".join(edge_types) if edge_types else "unknown"
                lines.append(f"  {dependency_node.__repr__(include_absolute_path=True)} [dependency type: {edge_types_str}]")
            lines.append("")
        
        # Dependents (nodes that depend on this node)
        if analysis.dependents:
            lines.append(f"## Nodes depend on this node ({analysis.node.file_level_id}):")
            for dependent_node, edge_types in analysis.dependents:
                edge_types_str = ", ".join(edge_types) if edge_types else "unknown"
                lines.append(f"  {dependent_node.__repr__(include_absolute_path=True)} [dependent type: {edge_types_str}]")
        
        return '\n'.join(lines)
    
    @classmethod
    def from_aggregated_results(cls, aggregated_results_path: str, on_demand: bool = False) -> "DefinitionAnalyzer":
        """
        Create a DefinitionAnalyzer from an aggregated results file.
        
        Args:
            aggregated_results_path: Path to the aggregated results JSON file
            
        Returns:
            DefinitionAnalyzer instance
        """
        graph_analyzer = GraphAnalyzer(aggregated_results_path, on_demand)
        return cls(graph_analyzer) 