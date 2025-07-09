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
from ..core.models import Node, Edge


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
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.adjacency_list: Dict[str, Set[str]] = defaultdict(set)
        self.reverse_adjacency_list: Dict[str, Set[str]] = defaultdict(set)
        self.files_to_nodes: Dict[str, List[Node]] = defaultdict(list)
        
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
            node = Node.from_dict(node_data, absolute_path_to_repo)
            self.nodes[node.id] = node
            self.files_to_nodes[node.implementation_file].append(node)
        
        # Build edges and adjacency lists
        for edge_data in self.data.get("edges", []):
            edge = Edge.from_dict(edge_data)
            self.edges.append(edge)
            
            # Build adjacency lists for graph traversal
            self.adjacency_list[edge.subject_id].add(edge.object_id)
            self.reverse_adjacency_list[edge.object_id].add(edge.subject_id)
        
        # Sort nodes by line number within each file
        for file_path in self.files_to_nodes:
            self.files_to_nodes[file_path].sort(key=lambda n: n.start_line)
        
        logger.info(f"Built graph with {len(self.nodes)} nodes and {len(self.edges)} edges")
    
    def get_node(self, node_id: str) -> Optional[Node]:
        """Get a node by its ID."""
        return self.nodes.get(node_id)
    
    def get_nodes_in_file(self, file_path: str) -> List[Node]:
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
    
    def find_edges_between(self, subject_id: str, object_id: str) -> List[Edge]:
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