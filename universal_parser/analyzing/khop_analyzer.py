"""
K-hop dependency analyzer for code graphs.

This module provides functionality to analyze k-hop dependencies in code graphs,
finding all nodes reachable within k steps from a given starting node.
"""

from typing import Dict, List, Set, Optional, Any, Tuple
from collections import deque
import json

from .graph_analyzer import GraphAnalyzer, GraphNode, GraphEdge
from ..utils.logger import logger


class KHopResult:
    """Container for k-hop analysis results."""
    
    def __init__(self, start_node_id: str, k: int):
        self.start_node_id = start_node_id
        self.k = k
        self.nodes_by_hop: Dict[int, Set[str]] = {}  # hop_level -> set of node_ids
        self.all_nodes: Set[str] = set()
        self.edges_in_subgraph: List[GraphEdge] = []
    
    def add_node_at_hop(self, node_id: str, hop_level: int):
        """Add a node at a specific hop level."""
        if hop_level not in self.nodes_by_hop:
            self.nodes_by_hop[hop_level] = set()
        self.nodes_by_hop[hop_level].add(node_id)
        self.all_nodes.add(node_id)
    
    def get_total_nodes(self) -> int:
        """Get total number of nodes in the k-hop subgraph."""
        return len(self.all_nodes)
    
    def get_nodes_at_hop(self, hop_level: int) -> Set[str]:
        """Get all nodes at a specific hop level."""
        return self.nodes_by_hop.get(hop_level, set())


class KHopAnalyzer:
    """Analyzer for k-hop dependency analysis."""
    
    def __init__(self, graph_analyzer: GraphAnalyzer):
        """
        Initialize the k-hop analyzer.
        
        Args:
            graph_analyzer: The base graph analyzer instance
        """
        self.graph = graph_analyzer
    
    def analyze_khop_dependencies(
        self, 
        start_node_id: str, 
        k: int, 
        direction: str = "both"
    ) -> KHopResult:
        """
        Analyze k-hop dependencies from a starting node.
        
        Args:
            start_node_id: The ID of the starting node
            k: The number of hops to traverse
            direction: Direction of traversal ("outgoing", "incoming", "both")
            
        Returns:
            KHopResult containing the analysis results
            
        Raises:
            ValueError: If the starting node doesn't exist or k is negative
        """
        if not self.graph.validate_node_exists(start_node_id):
            raise ValueError(f"Node '{start_node_id}' not found in graph")
        
        if k < 0:
            raise ValueError("k must be non-negative")
        
        if direction not in ["outgoing", "incoming", "both"]:
            raise ValueError("direction must be 'outgoing', 'incoming', or 'both'")
        
        logger.info(f"Starting {k}-hop {direction} analysis from node: {start_node_id}")
        
        result = KHopResult(start_node_id, k)
        
        # Add the starting node at hop 0
        result.add_node_at_hop(start_node_id, 0)
        
        # BFS traversal to find k-hop dependencies
        visited = {start_node_id}
        current_level = {start_node_id}
        
        for hop_level in range(1, k + 1):
            next_level = set()
            
            for node_id in current_level:
                neighbors = self._get_neighbors(node_id, direction)
                
                for neighbor_id in neighbors:
                    if neighbor_id not in visited:
                        visited.add(neighbor_id)
                        next_level.add(neighbor_id)
                        result.add_node_at_hop(neighbor_id, hop_level)
            
            current_level = next_level
            if not current_level:  # No more nodes to explore
                break
        
        # Find all edges within the subgraph
        result.edges_in_subgraph = self._find_edges_in_subgraph(result.all_nodes)
        
        logger.info(f"Found {result.get_total_nodes()} nodes in {k}-hop subgraph")
        return result
    
    def _get_neighbors(self, node_id: str, direction: str) -> Set[str]:
        """Get neighbors based on direction."""
        if direction == "outgoing":
            return self.graph.get_outgoing_nodes(node_id)
        elif direction == "incoming":
            return self.graph.get_incoming_nodes(node_id)
        else:  # both
            return self.graph.get_all_neighbors(node_id)
    
    def _find_edges_in_subgraph(self, node_ids: Set[str]) -> List[GraphEdge]:
        """Find all edges that exist within the given set of nodes."""
        edges_in_subgraph = []
        
        for edge in self.graph.edges:
            if edge.subject_id in node_ids and edge.object_id in node_ids:
                edges_in_subgraph.append(edge)
        
        return edges_in_subgraph
    
    def format_khop_result(
        self, 
        result: KHopResult, 
        include_code: bool = False,
        max_code_lines: int = 5
    ) -> str:
        """
        Format the k-hop analysis result as a readable string.
        
        Args:
            result: The k-hop analysis result
            include_code: Whether to include code snippets
            max_code_lines: Maximum lines of code to show per node
            
        Returns:
            Formatted string representation
        """
        lines = []
        lines.append(f"K-hop Dependency Analysis (k={result.k})")
        lines.append(f"Starting Node: {result.start_node_id}")
        lines.append(f"Total Nodes Found: {result.get_total_nodes()}")
        lines.append(f"Total Edges in Subgraph: {len(result.edges_in_subgraph)}")
        lines.append("=" * 60)
        
        # Show nodes by hop level
        for hop_level in sorted(result.nodes_by_hop.keys()):
            nodes_at_hop = result.get_nodes_at_hop(hop_level)
            lines.append(f"\nHop Level {hop_level} ({len(nodes_at_hop)} nodes):")
            lines.append("-" * 40)
            
            for node_id in sorted(nodes_at_hop):
                node = self.graph.get_node(node_id)
                if node:
                    lines.append(f"  • {node_id}")
                    lines.append(f"    Type: {node.type}")
                    lines.append(f"    File: {node.implementation_file}:{node.start_line}-{node.end_line}")
                    
                    if include_code:
                        code_lines = node.code_snippet.strip().split('\n')
                        if len(code_lines) <= max_code_lines:
                            # Show all lines
                            for line in code_lines:
                                lines.append(f"    | {line}")
                        else:
                            # Show first few lines with elision
                            for i, line in enumerate(code_lines[:max_code_lines]):
                                lines.append(f"    | {line}")
                            remaining = len(code_lines) - max_code_lines
                            lines.append(f"    | ... eliding {remaining} more lines ...")
                    
                    lines.append("")  # Empty line between nodes
        
        # Show edges in subgraph
        if result.edges_in_subgraph:
            lines.append(f"\nEdges in Subgraph ({len(result.edges_in_subgraph)}):")
            lines.append("-" * 40)
            
            # Group edges by type
            edges_by_type = {}
            for edge in result.edges_in_subgraph:
                if edge.type not in edges_by_type:
                    edges_by_type[edge.type] = []
                edges_by_type[edge.type].append(edge)
            
            for edge_type, edges in sorted(edges_by_type.items()):
                lines.append(f"\n  {edge_type} ({len(edges)}):")
                for edge in edges:
                    lines.append(f"    {edge.subject_id} → {edge.object_id}")
        
        return '\n'.join(lines)
    
    def export_khop_result_json(self, result: KHopResult, output_path: str):
        """
        Export the k-hop analysis result to a JSON file.
        
        Args:
            result: The k-hop analysis result
            output_path: Path to save the JSON file
        """
        # Build the export data structure
        export_data = {
            "analysis_type": "k_hop_dependencies",
            "start_node_id": result.start_node_id,
            "k": result.k,
            "total_nodes": result.get_total_nodes(),
            "total_edges": len(result.edges_in_subgraph),
            "nodes_by_hop": {},
            "nodes": {},
            "edges": []
        }
        
        # Add nodes by hop level
        for hop_level, node_ids in result.nodes_by_hop.items():
            export_data["nodes_by_hop"][str(hop_level)] = list(node_ids)
        
        # Add detailed node information
        for node_id in result.all_nodes:
            node = self.graph.get_node(node_id)
            if node:
                export_data["nodes"][node_id] = {
                    "id": node.id,
                    "type": node.type,
                    "implementation_file": node.implementation_file,
                    "start_line": node.start_line,
                    "end_line": node.end_line,
                    "code_snippet": node.code_snippet
                }
        
        # Add edges
        for edge in result.edges_in_subgraph:
            export_data["edges"].append({
                "subject_id": edge.subject_id,
                "object_id": edge.object_id,
                "type": edge.type,
                "subject_file": edge.subject_implementation_file,
                "object_file": edge.object_implementation_file
            })
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"K-hop analysis result exported to: {output_path}")
    
    @classmethod
    def from_aggregated_results(cls, aggregated_results_path: str) -> "KHopAnalyzer":
        """
        Create a KHopAnalyzer from an aggregated results file.
        
        Args:
            aggregated_results_path: Path to the aggregated results JSON file
            
        Returns:
            KHopAnalyzer instance
        """
        graph_analyzer = GraphAnalyzer(aggregated_results_path)
        return cls(graph_analyzer) 