import argparse
import asyncio
import os
import json
from pathlib import Path
from typing import List, Tuple, Optional
import time
from tqdm import tqdm
import fnmatch
import sys

from . import config
from .parse_single_file import extract_nodes_and_edges
from .schema import Node, Edge
from .patterns import DEFAULT_IGNORE_PATTERNS, DEFAULT_INCLUDE_PATTERNS, CODE_EXTENSIONS
from .logger import logger


class RepositoryParser:
    """Class to handle parsing of entire repositories."""
    
    def __init__(self, repo_path: str, repo_name: Optional[str] = None):
        self.repo_path = Path(repo_path).resolve()
        self.repo_name = repo_name or self.repo_path.name
        self.repo_name = self.repo_name + f"-{config.LLM_MODEL.split('/')[-1]}"
        self.supported_files: List[Path] = []
        self.all_nodes: List[Node] = []
        self.all_edges: List[Edge] = []
        self.failed_files: List[str] = []
        
    def discover_files(self) -> List[Path]:
        """Discover all supported files in the repository."""
        logger.info(f"Discovering files in repository: {self.repo_path}")
        
        supported_files: List[Path] = []
        total_files = 0
        
        for root, dirs, files in os.walk(self.repo_path):
            # Skip common directories that shouldn't be parsed
            # Get relative path from repo root for pattern matching
            try:
                relative_root = str(Path(root).relative_to(self.repo_path))
            except ValueError:
                # If relative_to fails, use empty string for repo root
                relative_root = ""
            
            dirs[:] = [d for d in dirs if not d.startswith('.') and not self._should_exclude_path(relative_root, d)]
            
            for file in files:
                total_files += 1
                file_path = Path(root) / file
                
                # Get relative path from repo root for pattern matching
                try:
                    relative_path = str(file_path.relative_to(self.repo_path))
                except ValueError:
                    # If relative_to fails, use the current approach
                    relative_path = root
                
                # Check if file should be excluded based on patterns
                if self._should_exclude_path(relative_path, file):
                    continue
                
                # Check if file should be included based on inclusion patterns
                if self._should_include_file(relative_path, file):
                    supported_files.append(file_path)

        logger.info(f"Found {len(supported_files)} supported files out of {total_files} total files")

        self.supported_files = supported_files
        return supported_files
    
    def _should_exclude_path(self, path: str, filename: str) -> bool:
        """
        Determine if a path should be excluded based on exclusion patterns.

        Checks the given path and filename against all configured exclude patterns
        using various matching strategies including glob patterns and path prefixes.

        Args:
            path: Relative path of the file/directory.
            filename: Name of the file/directory.

        Returns:
            True if the path should be excluded, False otherwise.
        """
        for pattern in DEFAULT_IGNORE_PATTERNS:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(filename, pattern):
                return True

            if pattern.endswith("/"):
                if path.startswith(pattern.rstrip("/")):
                    return True
            else:
                if path.startswith(pattern + "/") or path == pattern:
                    return True

                path_parts = path.split("/")
                if pattern in path_parts:
                    return True
        return False
    
    def _should_include_file(self, path: str, filename: str) -> bool:
        """
        Determine if a file should be included based on inclusion patterns.

        If no include patterns are specified, all files are included by default.
        Otherwise, files must match at least one include pattern.

        Args:
            path: Relative path of the file.
            filename: Name of the file.

        Returns:
            True if the file should be included, False otherwise.
        """
        if not DEFAULT_INCLUDE_PATTERNS:
            return True

        for pattern in DEFAULT_INCLUDE_PATTERNS:
            if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(filename, pattern):
                return True
        return False

    
    async def parse_single_file_wrapper(self, file_path: Path) -> Tuple[Optional[List[Node]], Optional[List[Edge]], str]:
        """Wrapper to parse a single file and handle errors."""
        try:
            logger.debug(f"Processing file: {file_path}")
            nodes, edges = await extract_nodes_and_edges(
                str(file_path), 
                str(self.repo_path), 
                self.repo_name
            )
            
            if nodes is not None and edges is not None:
                logger.debug(f"Successfully processed {file_path}: {len(nodes)} nodes, {len(edges)} edges")
                return nodes, edges, str(file_path)
            else:
                logger.warning(f"Failed to process {file_path}")
                return None, None, str(file_path)
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            return None, None, str(file_path)
    
    async def parse_files_concurrent(self, max_concurrent: int = 5) -> None:
        """Parse all discovered files with controlled concurrency."""
        if not self.supported_files:
            logger.warning("No supported files discovered. Run discover_files() first.")
            return
            
        logger.info(f"Starting to parse {len(self.supported_files)} files with max concurrency: {max_concurrent}")
        start_time = time.time()
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def parse_with_semaphore(file_path):
            async with semaphore:
                return await self.parse_single_file_wrapper(file_path)
        
        # Create tasks for all files
        tasks = [parse_with_semaphore(file_path) for file_path in self.supported_files]
        
        # Process files and collect results
        successful_files = 0
        failed_files = 0
        
        for i, task in tqdm(enumerate(asyncio.as_completed(tasks)), total=len(tasks)):

            nodes, edges, file_path = await task
            
            if nodes is not None and edges is not None:
                self.all_nodes.extend(nodes)
                self.all_edges.extend(edges)
                successful_files += 1
            else:
                self.failed_files.append(file_path)
                failed_files += 1
            
            # Progress reporting
            if (i + 1) % 10 == 0 or i + 1 == len(tasks):
                elapsed_time = time.time() - start_time
                logger.info(f"Progress: {i + 1}/{len(tasks)} files processed. "
                          f"Success: {successful_files}, Failed: {failed_files}. "
                          f"Elapsed: {elapsed_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.info(f"Completed parsing repository in {total_time:.2f}s. "
                   f"Total files: {len(self.supported_files)}, "
                   f"Successful: {successful_files}, "
                   f"Failed: {failed_files}")
    
    def save_aggregated_results(self) -> str:
        """Save all nodes and edges to a single aggregated JSON file."""
        output_dir = Path(config.OUTPUT_DIR) / self.repo_name
        output_dir.mkdir(parents=True, exist_ok=True)
        
        aggregated_file = output_dir / "aggregated_results.json"
        
        result = {
            "repository": {
                "name": self.repo_name,
                "path": str(self.repo_path),
                "total_files_processed": len(self.supported_files) - len(self.failed_files),
                "total_files_failed": len(self.failed_files),
                "failed_files": self.failed_files
            },
            "nodes": [node.model_dump() for node in self.all_nodes],
            "edges": [edge.model_dump() for edge in self.all_edges],
            "statistics": {
                "total_nodes": len(self.all_nodes),
                "total_edges": len(self.all_edges),
                "nodes_by_type": self._count_by_type(self.all_nodes, 'type'),
                "edges_by_type": self._count_by_type(self.all_edges, 'type'),
                "files_by_language": self._count_files_by_language()
            }
        }
        
        with open(aggregated_file, 'w') as f:
            json.dump(result, f, indent=2)
        
        logger.info(f"Aggregated results saved to: {aggregated_file}")
        logger.info(f"Total nodes: {len(self.all_nodes)}, Total edges: {len(self.all_edges)}")
        
        return str(aggregated_file)
    
    def _count_by_type(self, items: List, type_field: str) -> dict:
        """Count items by their type field."""
        counts = {}
        for item in items:
            item_type = getattr(item, type_field, 'unknown')
            counts[item_type] = counts.get(item_type, 0) + 1
        return counts
    
    def _count_files_by_language(self) -> dict:
        """Count processed files by programming language."""
        counts = {}
        for file_path in self.supported_files:
            if str(file_path) not in self.failed_files:
                extension = Path(file_path).suffix.lower()
                language = CODE_EXTENSIONS.get(extension, 'unknown')
                counts[language] = counts.get(language, 0) + 1
        return counts
    
    async def parse_repository(self, max_concurrent: int = 5) -> str:
        """Main method to parse the entire repository."""
        logger.info(f"Starting repository parsing for: {self.repo_path}")
        
        # Discover files
        self.discover_files()
        
        if not self.supported_files:
            logger.warning("No supported files found in repository")
            return ""
        
        # Parse files
        await self.parse_files_concurrent(max_concurrent)
        
        # Save results
        output_file = self.save_aggregated_results()
        
        logger.info(f"Repository parsing completed. Results saved to: {output_file}")
        return output_file


async def parse_repository_main(
    repo_path: str, 
    repo_name: Optional[str] = None, 
    max_concurrent: int = 5
) -> str:
    """Main function to parse a repository."""
    parser = RepositoryParser(repo_path, repo_name)
    return await parser.parse_repository(max_concurrent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse an entire repository for nodes and edges")
    parser.add_argument("--repo-path", required=True, type=str, 
                       help="The absolute path to the repository to parse")
    parser.add_argument("--repo-name", type=str, default=None,
                       help="Name for the repository (defaults to directory name)")
    parser.add_argument("--max-concurrent", type=int, default=5,
                       help="Maximum number of files to process concurrently (default: 5)")
    
    args = parser.parse_args()
    
    # Validate repository path
    repo_path = Path(args.repo_path).resolve()
    if not repo_path.exists():
        logger.error(f"Repository path does not exist: {repo_path}")
        exit(1)
    
    if not repo_path.is_dir():
        logger.error(f"Repository path is not a directory: {repo_path}")
        exit(1)
    
    # Run the parser
    asyncio.run(parse_repository_main(
        str(repo_path), 
        args.repo_name, 
        args.max_concurrent
    )) 