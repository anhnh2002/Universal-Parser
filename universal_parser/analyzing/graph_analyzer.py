"""
Base graph analyzer for processing aggregated parsing results.

This module provides the core GraphAnalyzer class that loads and processes
aggregated results from the universal parser.
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Any
from collections import defaultdict

from ..utils.logger import logger


class GraphNode:
    """Represents a node in the code graph."""
    
    def __init__(self, node_data: Dict[str, Any], absolute_path_to_repo: str):
        self.id: str = node_data["id"]
        self.implementation_file: str = node_data["implementation_file"]
        self.start_line: int = node_data["start_line"]
        self.end_line: int = node_data["end_line"]
        self.type: str = node_data["type"]
        self.code_snippet: str = node_data["code_snippet"]

        self.absolute_path_to_implementation_file = os.path.join(absolute_path_to_repo, self.implementation_file)

        # remove extension from implementation file
        self.file_level_id = self.implementation_file.split(".")[0]
        self.file_level_id = self.file_level_id.replace("/", ".")
        self.file_level_id = self.id.replace(self.file_level_id, "")
        if self.file_level_id.startswith("."):
            self.file_level_id = self.file_level_id[1:]

    
    def __repr__(self, include_absolute_path: bool = False):
        if include_absolute_path:
            return f"* Node: {self.file_level_id} in File: {self.absolute_path_to_implementation_file} (Line {self.start_line + 1} to {self.end_line + 1})"
        else:
            return f"# {self.file_level_id} (Line {self.start_line + 1} to {self.end_line + 1})"
    
    def get_k_first_line(self, k: int = 1) -> str:
        """Get the first line of the code snippet."""
        lines = self.code_snippet.strip().split('\n')
        return lines[:k] if lines else ""


class GraphEdge:
    """Represents an edge in the code graph."""
    
    def __init__(self, edge_data: Dict[str, Any], absolute_path_to_repo: str):
        self.absolute_path_to_repo = absolute_path_to_repo
        self.subject_id: str = edge_data["subject_id"]
        self.subject_implementation_file: str = edge_data["subject_implementation_file"]
        self.object_id: str = edge_data["object_id"]
        self.object_implementation_file: str = edge_data["object_implementation_file"]
        self.type: str = edge_data["type"]
    
    def __repr__(self):
        return f"GraphEdge('{self.subject_id}' --{self.type}--> '{self.object_id}')"


class GraphAnalyzer:
    """Main analyzer for processing code graphs from aggregated results."""
    
    def __init__(self, aggregated_results_path: str):
        """
        Initialize the graph analyzer.
        
        Args:
            aggregated_results_path: Path to the aggregated results JSON file
        """
        self.aggregated_results_path = Path(aggregated_results_path)
        self.data: Optional[Dict[str, Any]] = None
        self.nodes: Dict[str, GraphNode] = {}
        self.edges: List[GraphEdge] = []
        self.adjacency_list: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_adjacency_list: Dict[str, Set[str]] = defaultdict(set)
        self.files_to_nodes: Dict[str, List[GraphNode]] = defaultdict(list)
        
        self._load_data()
        self._build_graph()
    
    def _load_data(self):
        """Load the aggregated results from JSON file."""
        try:
            with open(self.aggregated_results_path, 'r', encoding='utf-8') as f:
                self.data = json.load(f)
            logger.info(f"Loaded aggregated results from {self.aggregated_results_path}")
        except FileNotFoundError:
            raise FileNotFoundError(f"Aggregated results file not found: {self.aggregated_results_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in aggregated results file: {e}")
    
    def _build_graph(self):
        """Build the graph structure from loaded data."""
        if not self.data:
            raise ValueError("No data loaded")
        
        absolute_path_to_repo = self.data.get("repository", {}).get("path", "")
        
        # Build nodes
        for node_data in self.data.get("nodes", []):
            node = GraphNode(node_data, absolute_path_to_repo)
            self.nodes[node.id] = node
            self.files_to_nodes[node.implementation_file].append(node)
        
        # Build edges and adjacency lists
        for edge_data in self.data.get("edges", []):
            edge = GraphEdge(edge_data, absolute_path_to_repo)
            self.edges.append(edge)
            
            # Build adjacency lists for graph traversal
            self.adjacency_list[edge.subject_id].add(edge.object_id)
            self.reverse_adjacency_list[edge.object_id].add(edge.subject_id)
        
        # Sort nodes by line number within each file
        for file_path in self.files_to_nodes:
            self.files_to_nodes[file_path].sort(key=lambda n: n.start_line)
        
        logger.info(f"Built graph with {len(self.nodes)} nodes and {len(self.edges)} edges")
    
    def get_node(self, node_id: str) -> Optional[GraphNode]:
        """Get a node by its ID."""
        return self.nodes.get(node_id)
    
    def get_nodes_in_file(self, file_path: str) -> List[GraphNode]:
        """Get all nodes in a specific file, sorted by line number."""
        return self.files_to_nodes.get(file_path, [])
    
    def get_outgoing_nodes(self, node_id: str) -> Set[str]:
        """Get all nodes that this node points to."""
        return self.adjacency_list.get(node_id, set())
    
    def get_incoming_nodes(self, node_id: str) -> Set[str]:
        """Get all nodes that point to this node."""
        return self.reverse_adjacency_list.get(node_id, set())
    
    def get_all_neighbors(self, node_id: str) -> Set[str]:
        """Get all connected nodes (both incoming and outgoing)."""
        return self.get_outgoing_nodes(node_id) | self.get_incoming_nodes(node_id)
    
    def find_edges_between(self, subject_id: str, object_id: str) -> List[GraphEdge]:
        """Find all edges between two specific nodes."""
        return [edge for edge in self.edges 
                if edge.subject_id == subject_id and edge.object_id == object_id]
    
    def get_repository_info(self) -> Dict[str, Any]:
        """Get repository information from the aggregated results."""
        return self.data.get("repository", {}) if self.data else {}
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get parsing statistics from the aggregated results."""
        return self.data.get("statistics", {}) if self.data else {}
    
    def validate_node_exists(self, node_id: str) -> bool:
        """Check if a node exists in the graph."""
        return node_id in self.nodes
    
    def get_all_node_ids(self) -> Set[str]:
        """Get all node IDs in the graph."""
        return set(self.nodes.keys())
    
    def get_files_list(self) -> List[str]:
        """Get list of all files that contain nodes."""
        return list(self.files_to_nodes.keys()) 