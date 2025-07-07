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

from ..core import config
from .single_file import extract_nodes_and_edges
from ..core.models import Node, Edge
from .patterns import DEFAULT_IGNORE_PATTERNS, DEFAULT_INCLUDE_PATTERNS, CODE_EXTENSIONS
from .incremental import ChangeDetector, IncrementalAggregator
from ..utils.logger import logger


class RepositoryParser:
    """Class to handle parsing of entire repositories."""
    
    def __init__(self, repo_dir: str, repo_name: Optional[str] = None):
        self.repo_dir = Path(repo_dir).resolve()
        self.repo_name = repo_name or self.repo_dir.name
        self.repo_name = self.repo_name + f"-{config.LLM_MODEL.split('/')[-1]}"
        self.supported_files: List[Path] = []
        self.all_nodes: List[Node] = []
        self.all_edges: List[Edge] = []
        self.failed_files: List[str] = []
        
        # Incremental update components
        self.change_detector = ChangeDetector(str(self.repo_dir), self.repo_name)
        self.incremental_aggregator = IncrementalAggregator(str(self.repo_dir), self.repo_name)
        
    def discover_files(self) -> List[Path]:
        """Discover all supported files in the repository."""
        logger.info(f"Discovering files in repository: {self.repo_dir}")
        
        supported_files: List[Path] = []
        total_files = 0
        
        for root, dirs, files in os.walk(self.repo_dir):
            # Skip common directories that shouldn't be parsed
            # Get relative path from repo root for pattern matching
            try:
                relative_root = str(Path(root).relative_to(self.repo_dir))
            except ValueError:
                # If relative_to fails, use empty string for repo root
                relative_root = ""
            
            dirs[:] = [d for d in dirs if not d.startswith('.') and not self._should_exclude_path(relative_root, d)]
            
            for file in files:
                total_files += 1
                file_path = Path(root) / file
                
                # Get relative path from repo root for pattern matching
                try:
                    relative_path = str(file_path.relative_to(self.repo_dir))
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
                str(self.repo_dir), 
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
                "path": str(self.repo_dir),
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
        logger.info(f"Starting repository parsing for: {self.repo_dir}")
        
        # Load metadata for tracking
        self.change_detector.load_metadata()
        
        # Discover files
        self.discover_files()
        
        if not self.supported_files:
            logger.warning("No supported files found in repository")
            return ""
        
        # Parse files
        await self.parse_files_concurrent(max_concurrent)
        
        # Save results
        output_file = self.save_aggregated_results()
        
        # Mark full parse complete and save metadata
        self.mark_full_parse_complete()
        
        logger.info(f"Repository parsing completed. Results saved to: {output_file}")
        return output_file

    async def parse_repository_incremental(
        self, 
        max_concurrent: int = 5, 
        use_content_hash: bool = False,
        force_reparse: Optional[List[str]] = None
    ) -> str:
        """Parse repository incrementally, only processing changed files."""
        logger.info(f"Starting incremental repository parsing for: {self.repo_dir}")
        
        # Load existing metadata
        self.change_detector.load_metadata()
        
        # Discover all files
        self.discover_files()
        
        if not self.supported_files:
            logger.warning("No supported files found in repository")
            return ""
        
        # Clean up orphaned metadata
        self.change_detector.cleanup_orphaned_metadata(self.supported_files)
        
        # Get changed files
        changed_files = self.change_detector.get_changed_files(self.supported_files, use_content_hash)
        
        # Add force-reparse files
        if force_reparse:
            force_reparse_paths = []
            for pattern in force_reparse:
                for file_path in self.supported_files:
                    relative_path = str(file_path.relative_to(self.repo_dir))
                    if fnmatch.fnmatch(relative_path, pattern):
                        if file_path not in changed_files:
                            changed_files.append(file_path)
                            force_reparse_paths.append(file_path)
            
            if force_reparse_paths:
                logger.info(f"Force re-parsing {len(force_reparse_paths)} files matching patterns: {force_reparse}")
        
        if not changed_files:
            logger.info("No changed files detected. Repository is up to date.")
            # Still update metadata file
            self.change_detector.save_metadata()
            
            # Return path to existing aggregated results
            existing_aggregated = self.incremental_aggregator.aggregated_file
            if existing_aggregated.exists():
                return str(existing_aggregated)
            else:
                logger.warning("No existing aggregated results found")
                return ""
        
        logger.info(f"Processing {len(changed_files)} changed files out of {len(self.supported_files)} total files")
        
        # Load existing aggregated results
        aggregated_data = self.incremental_aggregator.load_existing_aggregated_results()
        
        # Remove data from changed files
        if aggregated_data:
            aggregated_data = self.incremental_aggregator.remove_file_data_from_aggregated(
                aggregated_data, changed_files
            )
        
        # Parse only the changed files
        await self.parse_files_concurrent_incremental(changed_files, max_concurrent, use_content_hash)
        
        # Add new data to aggregated results
        aggregated_data = self.incremental_aggregator.add_file_data_to_aggregated(
            aggregated_data, self.all_nodes, self.all_edges
        )
        
        # Update statistics
        aggregated_data = self.incremental_aggregator.update_statistics(aggregated_data)
        
        # Update repository metadata in aggregated results
        if aggregated_data and 'repository' in aggregated_data:
            aggregated_data['repository']['name'] = self.repo_name
            aggregated_data['repository']['path'] = str(self.repo_dir)
            # Update file counts (simplified)
            aggregated_data['repository']['total_files_processed'] = len(self.supported_files) - len(self.failed_files)
            aggregated_data['repository']['total_files_failed'] = len(self.failed_files)
            aggregated_data['repository']['failed_files'] = self.failed_files
        
        # Save updated aggregated results
        output_file = self.incremental_aggregator.save_aggregated_results(aggregated_data)
        
        # Save metadata
        self.change_detector.save_metadata()
        
        logger.info(f"Incremental repository parsing completed. Results saved to: {output_file}")
        logger.info(f"Updated {len(changed_files)} files. Total: {aggregated_data['statistics']['total_nodes']} nodes, {aggregated_data['statistics']['total_edges']} edges")
        
        return output_file
    
    async def parse_files_concurrent_incremental(
        self, 
        files_to_parse: List[Path], 
        max_concurrent: int = 5,
        use_content_hash: bool = False
    ) -> None:
        """Parse a specific list of files with controlled concurrency for incremental updates."""
        if not files_to_parse:
            logger.info("No files to parse for incremental update")
            return
            
        logger.info(f"Starting to parse {len(files_to_parse)} files with max concurrency: {max_concurrent}")
        start_time = time.time()
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def parse_with_semaphore(file_path):
            async with semaphore:
                return await self.parse_single_file_wrapper_incremental(file_path, use_content_hash)
        
        # Create tasks for all files
        tasks = [parse_with_semaphore(file_path) for file_path in files_to_parse]
        
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
        logger.info(f"Completed incremental parsing in {total_time:.2f}s. "
                   f"Files: {len(files_to_parse)}, "
                   f"Successful: {successful_files}, "
                   f"Failed: {failed_files}")
    
    async def parse_single_file_wrapper_incremental(
        self, 
        file_path: Path, 
        use_content_hash: bool = False
    ) -> Tuple[Optional[List[Node]], Optional[List[Edge]], str]:
        """Wrapper to parse a single file for incremental updates and update metadata."""
        try:
            logger.debug(f"Processing file for incremental update: {file_path}")
            
            # Remove existing individual file result first
            individual_output_path = self.incremental_aggregator.get_file_output_path(file_path)
            if individual_output_path.exists():
                individual_output_path.unlink()
                logger.debug(f"Removed existing individual result: {individual_output_path}")
            
            nodes, edges = await extract_nodes_and_edges(
                str(file_path), 
                str(self.repo_dir), 
                self.repo_name
            )
            
            if nodes is not None and edges is not None:
                logger.debug(f"Successfully processed {file_path}: {len(nodes)} nodes, {len(edges)} edges")
                
                # Update metadata for successful parse
                self.change_detector.update_file_metadata(
                    file_path, 
                    parse_successful=True, 
                    error_message=None,
                    use_content_hash=use_content_hash
                )
                
                return nodes, edges, str(file_path)
            else:
                logger.warning(f"Failed to process {file_path}")
                
                # Update metadata for failed parse
                self.change_detector.update_file_metadata(
                    file_path, 
                    parse_successful=False, 
                    error_message="Parsing returned None",
                    use_content_hash=use_content_hash
                )
                
                return None, None, str(file_path)
                
        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            
            # Update metadata for failed parse
            self.change_detector.update_file_metadata(
                file_path, 
                parse_successful=False, 
                error_message=str(e),
                use_content_hash=use_content_hash
            )
            
            return None, None, str(file_path)
    
    def mark_full_parse_complete(self) -> None:
        """Mark that a full repository parse has been completed."""
        # Update metadata for all successfully parsed files
        for file_path in self.supported_files:
            if str(file_path) not in self.failed_files:
                self.change_detector.update_file_metadata(file_path, parse_successful=True)
        
        # Mark full parse completion
        self.change_detector.mark_full_parse_complete()
        self.change_detector.save_metadata()
        logger.info("Marked full repository parse as complete in metadata")


async def parse_repository_main(
    repo_dir: str, 
    repo_name: Optional[str] = None, 
    max_concurrent: int = 5
) -> str:
    """Main function to parse a repository."""
    parser = RepositoryParser(repo_dir, repo_name)
    return await parser.parse_repository(max_concurrent)


async def parse_repository_incremental_main(
    repo_dir: str, 
    repo_name: Optional[str] = None, 
    max_concurrent: int = 5,
    use_content_hash: bool = False,
    force_reparse: Optional[List[str]] = None
) -> str:
    """Main function to incrementally update repository parsing results."""
    parser = RepositoryParser(repo_dir, repo_name)
    return await parser.parse_repository_incremental(max_concurrent, use_content_hash, force_reparse)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Parse an entire repository for nodes and edges")
    parser.add_argument("--repo-dir", required=True, type=str, 
                       help="The absolute path to the repository to parse")
    parser.add_argument("--repo-name", type=str, default=None,
                       help="Name for the repository (defaults to directory name)")
    parser.add_argument("--max-concurrent", type=int, default=5,
                       help="Maximum number of files to process concurrently (default: 5)")
    
    args = parser.parse_args()
    
    # Validate repository path
    repo_dir = Path(args.repo_dir).resolve()
    if not repo_dir.exists():
        logger.error(f"Repository path does not exist: {repo_dir}")
        exit(1)
    
    if not repo_dir.is_dir():
        logger.error(f"Repository path is not a directory: {repo_dir}")
        exit(1)
    
    # Run the parser
    asyncio.run(parse_repository_main(
        str(repo_dir), 
        args.repo_name, 
        args.max_concurrent
    )) 