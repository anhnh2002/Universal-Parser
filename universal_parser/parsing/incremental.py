"""
Incremental update functionality for repository parsing.

This module provides infrastructure for detecting file changes and updating
parsed results incrementally without re-parsing the entire repository.
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict

from .patterns import CODE_EXTENSIONS
from ..core.models import Node, Edge
from ..utils.logger import logger


@dataclass
class FileMetadata:
    """Metadata for tracking file parsing state."""
    relative_path: str
    last_modified: float
    last_parsed: float
    file_size: int
    parse_successful: bool = True
    error_message: Optional[str] = None


@dataclass
class RepositoryMetadata:
    """Metadata for tracking repository parsing state."""
    repo_name: str
    repo_path: str
    last_full_parse: float
    total_files_tracked: int
    files: Dict[str, FileMetadata]
    
    
class ChangeDetector:
    """Detects changes in repository files and manages parsing metadata."""
    
    def __init__(self, repo_dir: str, output_dir: str):
        self.repo_dir = Path(repo_dir).resolve()
        self.repo_name = self.repo_dir.name
        self.output_dir = Path(output_dir) / self.repo_name
        self.metadata_file = self.output_dir / "parse_metadata.json"
        self.repo_metadata: Optional[RepositoryMetadata] = None
        
    def load_metadata(self) -> RepositoryMetadata:
        """Load existing parsing metadata or create new."""
        if self.metadata_file.exists():
            try:
                with open(self.metadata_file, 'r') as f:
                    data = json.load(f)
                
                # Convert file metadata
                files = {}
                for path, file_data in data.get('files', {}).items():
                    files[path] = FileMetadata(**file_data)
                
                self.repo_metadata = RepositoryMetadata(
                    repo_name=data['repo_name'],
                    repo_path=data['repo_path'],
                    last_full_parse=data.get('last_full_parse', 0),
                    total_files_tracked=data.get('total_files_tracked', 0),
                    files=files
                )
                logger.debug(f"Loaded metadata for {len(files)} tracked files")
                
            except (json.JSONDecodeError, KeyError, TypeError) as e:
                logger.warning(f"Failed to load metadata: {e}. Creating new metadata.")
                self.repo_metadata = self._create_new_metadata()
        else:
            logger.debug("No existing metadata found. Creating new metadata.")
            self.repo_metadata = self._create_new_metadata()
            
        return self.repo_metadata
    
    def _create_new_metadata(self) -> RepositoryMetadata:
        """Create new repository metadata."""
        return RepositoryMetadata(
            repo_name=self.repo_name,
            repo_path=str(self.repo_dir),
            last_full_parse=0,
            total_files_tracked=0,
            files={}
        )
    
    def save_metadata(self) -> None:
        """Save metadata to disk."""
        if not self.repo_metadata:
            return
            
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Convert to dict for JSON serialization
        data = {
            'repo_name': self.repo_metadata.repo_name,
            'repo_path': self.repo_metadata.repo_path,
            'last_full_parse': self.repo_metadata.last_full_parse,
            'total_files_tracked': self.repo_metadata.total_files_tracked,
            'files': {path: asdict(metadata) for path, metadata in self.repo_metadata.files.items()}
        }
        
        with open(self.metadata_file, 'w') as f:
            json.dump(data, f, indent=2)
        
        logger.debug(f"Saved metadata in {self.metadata_file}")
    
    def is_file_changed(self, file_path: Path) -> bool:
        """Check if a file has changed since last parse."""
            
        try:
            relative_path = str(file_path.relative_to(self.repo_dir))
        except ValueError:
            # File is outside repo
            return True
            
        file_metadata = self.repo_metadata.files.get(relative_path)
        if not file_metadata:
            # File not tracked before
            return True
            
        # Check if file doesn't exist anymore
        if not file_path.exists():
            return True
            
        stat = file_path.stat()

        print(f"File path: {file_path}")
        print(f"Relative path: {relative_path}")
        print(f"File metadata: {file_metadata}")
        print(f"File stat: {stat}")
        
        # Check modification time
        if stat.st_mtime > file_metadata.last_modified:
            logger.debug(f"File modified by timestamp: {relative_path}")
            return True
            
        # Check file size
        if stat.st_size != file_metadata.file_size:
            logger.debug(f"File size changed: {relative_path}")
            return True
                
        return False
    
    def update_file_metadata(
        self, 
        file_path: Path, 
        parse_successful: bool = True, 
        error_message: Optional[str] = None
    ) -> None:
        """Update metadata for a parsed file."""
        if not self.repo_metadata:
            return
            
        try:
            relative_path = str(file_path.relative_to(self.repo_dir))
        except ValueError:
            logger.warning(f"Cannot update metadata for file outside repo: {file_path}")
            return
            
        if not file_path.exists():
            logger.warning(f"Cannot update metadata for non-existent file: {file_path}")
            return
            
        stat = file_path.stat()
        current_time = time.time()
        
        
        self.repo_metadata.files[relative_path] = FileMetadata(
            relative_path=relative_path,
            last_modified=stat.st_mtime,
            last_parsed=current_time,
            file_size=stat.st_size,
            parse_successful=parse_successful,
            error_message=error_message
        )
        
        self.repo_metadata.total_files_tracked = len(self.repo_metadata.files)
    
    def get_changed_files(self, file_paths: List[Path]) -> List[Path]:
        """Get list of files that have changed since last parse."""
        changed_files = []
        
        for file_path in file_paths:
            if self.is_file_changed(file_path):
                changed_files.append(file_path)
                
        logger.debug(f"Found {len(changed_files)} changed files out of {len(file_paths)} total files")
        return changed_files
    
    def mark_full_parse_complete(self) -> None:
        """Mark that a full repository parse has been completed."""
        if self.repo_metadata:
            self.repo_metadata.last_full_parse = time.time()
    
    def cleanup_orphaned_metadata(self, current_files: List[Path]) -> None:
        """Remove metadata for files that no longer exist."""
        if not self.repo_metadata:
            return
            
        current_relative_paths = set()
        for file_path in current_files:
            try:
                relative_path = str(file_path.relative_to(self.repo_dir))
                current_relative_paths.add(relative_path)
            except ValueError:
                continue
                
        orphaned_paths = set(self.repo_metadata.files.keys()) - current_relative_paths
        
        for orphaned_path in orphaned_paths:
            del self.repo_metadata.files[orphaned_path]
            logger.debug(f"Removed metadata for orphaned file: {orphaned_path}")
            
        if orphaned_paths:
            logger.debug(f"Cleaned up {len(orphaned_paths)} orphaned file metadata entries")
            
        self.repo_metadata.total_files_tracked = len(self.repo_metadata.files)


class IncrementalAggregator:
    """Manages incremental updates to aggregated results."""
    
    def __init__(self, repo_dir: str, output_dir: str):
        self.repo_dir = Path(repo_dir).resolve()
        self.repo_name = self.repo_dir.name
        self.output_dir = Path(output_dir) / self.repo_name
        self.aggregated_file = self.output_dir / "aggregated_results.json"
        
    def load_existing_aggregated_results(self) -> Optional[Dict[str, Any]]:
        """Load existing aggregated results."""
        if not self.aggregated_file.exists():
            logger.debug("No existing aggregated results found")
            return {
                "repository": {},
                "nodes": [],
                "edges": [],
                "statistics": {}
            }
            
        try:
            with open(self.aggregated_file, 'r') as f:
                data = json.load(f)
            logger.debug(f"Loaded existing aggregated results with {len(data.get('nodes', []))} nodes and {len(data.get('edges', []))} edges")
            return data
        except (json.JSONDecodeError, IOError) as e:
            logger.debug(f"Failed to load existing aggregated results: {e}")
            return None
    
    def get_file_output_path(self, file_path: Path) -> Path:
        """Get the output path for a single file's results."""
        try:
            relative_path = file_path.relative_to(self.repo_dir)
        except ValueError:
            raise ValueError(f"File {file_path} is not within repository {self.repo_dir}")
            
        output_dir = self.output_dir / relative_path.parent
        return output_dir / f"{relative_path.name}.json"
    
    def remove_file_data_from_aggregated(
        self, 
        aggregated_data: Dict[str, Any], 
        file_paths: List[Path]
    ) -> Dict[str, Any]:
        """Remove nodes and edges from files that are being re-parsed."""
        if not aggregated_data:
            return aggregated_data
            
        # Get relative paths of files being updated
        relative_paths = set()
        for file_path in file_paths:
            try:
                relative_path = str(file_path.relative_to(self.repo_dir))
                relative_paths.add(relative_path)
            except ValueError:
                continue
        
        # Filter out nodes and edges from these files
        original_nodes = len(aggregated_data.get('nodes', []))
        original_edges = len(aggregated_data.get('edges', []))
        
        filtered_nodes = [
            node for node in aggregated_data.get('nodes', [])
            if node.get('implementation_file') not in relative_paths
        ]
        
        filtered_edges = [
            edge for edge in aggregated_data.get('edges', [])
            if edge.get('subject_implementation_file') not in relative_paths
        ]
        
        aggregated_data['nodes'] = filtered_nodes
        aggregated_data['edges'] = filtered_edges
        
        removed_nodes = original_nodes - len(filtered_nodes)
        removed_edges = original_edges - len(filtered_edges)
        
        if removed_nodes > 0 or removed_edges > 0:
            logger.debug(f"Removed {removed_nodes} nodes and {removed_edges} edges from {len(file_paths)} changed files")
        
        return aggregated_data
    
    def add_file_data_to_aggregated(
        self, 
        aggregated_data: Dict[str, Any], 
        new_nodes: List[Node], 
        new_edges: List[Edge]
    ) -> Dict[str, Any]:
        """Add new nodes and edges to aggregated results."""
        if not aggregated_data:
            # Create new aggregated structure
            aggregated_data = {
                'repository': {
                    'name': self.repo_name,
                    'path': str(self.repo_dir),
                    'total_files_processed': 0,
                    'total_files_failed': 0,
                    'failed_files': []
                },
                'nodes': [],
                'edges': [],
                'statistics': {}
            }
        
        # Add new nodes and edges
        existing_nodes = aggregated_data.get('nodes', [])
        existing_edges = aggregated_data.get('edges', [])
        
        existing_nodes.extend([node.model_dump() for node in new_nodes])
        existing_edges.extend([edge.model_dump() for edge in new_edges])
        
        aggregated_data['nodes'] = existing_nodes
        aggregated_data['edges'] = existing_edges
        
        logger.debug(f"Added {len(new_nodes)} nodes and {len(new_edges)} edges to aggregated results")
        
        return aggregated_data
    
    def update_statistics(self, aggregated_data: Dict[str, Any]) -> Dict[str, Any]:
        """Update statistics in aggregated results."""
        nodes = aggregated_data.get('nodes', [])
        edges = aggregated_data.get('edges', [])
        
        # Count by type
        node_type_counts = {}
        for node in nodes:
            node_type = node.get('type', 'unknown')
            node_type_counts[node_type] = node_type_counts.get(node_type, 0) + 1
            
        edge_type_counts = {}
        for edge in edges:
            edge_type = edge.get('type', 'unknown')
            edge_type_counts[edge_type] = edge_type_counts.get(edge_type, 0) + 1
        
        # Count files by language (simplified)
        files_by_language = {}
        implementation_files = set()
        for node in nodes:
            impl_file = node.get('implementation_file', '')
            if impl_file:
                implementation_files.add(impl_file)
        
        for file_path in implementation_files:
            extension = Path(file_path).suffix.lower()
            language = CODE_EXTENSIONS.get(extension, 'unknown')
            files_by_language[language] = files_by_language.get(language, 0) + 1
        
        aggregated_data['statistics'] = {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'nodes_by_type': node_type_counts,
            'edges_by_type': edge_type_counts,
            'files_by_language': files_by_language
        }
        
        return aggregated_data
    
    def save_aggregated_results(self, aggregated_data: Dict[str, Any]) -> str:
        """Save updated aggregated results."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        with open(self.aggregated_file, 'w') as f:
            json.dump(aggregated_data, f, indent=2)
        
        stats = aggregated_data.get('statistics', {})
        logger.debug(f"Saved aggregated results: {stats.get('total_nodes', 0)} nodes, {stats.get('total_edges', 0)} edges")
        
        return str(self.aggregated_file) 