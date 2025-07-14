import asyncio
import os
from pathlib import Path
from typing import List, Tuple, Optional
import time
from tqdm import tqdm
import fnmatch
import logging

from .single_file import extract_nodes_and_edges
from ..core.models import Node, Edge
from .patterns import DEFAULT_IGNORE_PATTERNS, DEFAULT_INCLUDE_PATTERNS
from .incremental import ChangeDetector, IncrementalAggregator
from ..utils.logger import logger


class RepositoryParser:
    """Class to handle parsing of entire repositories."""
    
    def __init__(self, repo_dir: str, output_dir: str):
        self.repo_dir = Path(repo_dir).resolve()
        self.repo_name = self.repo_dir.name
        self.supported_files: List[Path] = []
        self.all_nodes: List[Node] = []
        self.all_edges: List[Edge] = []
        self.failed_files: List[str] = []

        self.output_dir = Path(output_dir) / self.repo_name
        
        # Incremental update components
        self.change_detector = ChangeDetector(str(self.repo_dir), output_dir)
        self.incremental_aggregator = IncrementalAggregator(str(self.repo_dir), output_dir)
        
    def discover_files(self) -> List[Path]:
        """Discover all supported files in the repository."""
        logger.debug(f"Discovering files in repository: {self.repo_dir}")
        
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

        logger.debug(f"Found {len(supported_files)} supported files out of {total_files} total files")

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

    async def parse_repository_incremental(
        self,
        file_paths: List[Path]=[],
        max_concurrent: int = 5
    ) -> str:
        """Parse repository incrementally, only processing changed files."""
        logger.debug(f"Starting incremental repository parsing for: {self.repo_dir}")
        
        # Load existing metadata
        self.change_detector.load_metadata()
        
        # Discover all files
        self.supported_files = file_paths or self.discover_files()
        
        if not self.supported_files:
            logger.warning("No supported files found in repository")
            return ""
        
        # Clean up orphaned metadata
        self.change_detector.cleanup_orphaned_metadata(self.supported_files)
        
        # Get changed files
        changed_files = self.change_detector.get_changed_files(self.supported_files)
        
        if not changed_files:
            logger.debug("No changed files detected. Repository is up to date.")
            # Still update metadata file
            self.change_detector.save_metadata()
            
            # Return path to existing aggregated results
            existing_aggregated = self.incremental_aggregator.aggregated_file
            if existing_aggregated.exists():
                return str(existing_aggregated)
            else:
                logger.warning("No existing aggregated results found")
                return ""
        
        logger.debug(f"Processing {len(changed_files)} changed files out of {len(self.supported_files)} total files")
        
        # Load existing aggregated results
        aggregated_data = self.incremental_aggregator.load_existing_aggregated_results()
        
        # Remove data from changed files
        if aggregated_data:
            aggregated_data = self.incremental_aggregator.remove_file_data_from_aggregated(
                aggregated_data, changed_files
            )
        
        # Parse only the changed files
        await self.parse_files_concurrent_incremental(changed_files, max_concurrent)
        
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
        
        logger.debug(f"Incremental repository parsing completed. Results saved to: {output_file}")
        logger.debug(f"Updated {len(changed_files)} files. Total: {aggregated_data['statistics']['total_nodes']} nodes, {aggregated_data['statistics']['total_edges']} edges")
        
        return output_file
    
    async def parse_files_concurrent_incremental(
        self, 
        files_to_parse: List[Path], 
        max_concurrent: int = 5
    ) -> None:
        """Parse a specific list of files with controlled concurrency for incremental updates."""
        if not files_to_parse:
            logger.debug("No files to parse for incremental update")
            return
            
        logger.debug(f"Starting to parse {len(files_to_parse)} files with max concurrency: {max_concurrent}")
        start_time = time.time()
        
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def parse_with_semaphore(file_path):
            async with semaphore:
                return await self.parse_single_file_wrapper_incremental(file_path)
        
        # Create tasks for all files
        tasks = [parse_with_semaphore(file_path) for file_path in files_to_parse]
        
        # Process files and collect results
        successful_files = 0
        failed_files = 0

        progress_bar =  tqdm(enumerate(asyncio.as_completed(tasks)), total=len(tasks))\
                        if logger.level == logging.DEBUG\
                        else enumerate(asyncio.as_completed(tasks))
        
        for i, task in progress_bar:
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
                logger.debug(f"Progress: {i + 1}/{len(tasks)} files processed. "
                          f"Success: {successful_files}, Failed: {failed_files}. "
                          f"Elapsed: {elapsed_time:.2f}s")
        
        total_time = time.time() - start_time
        logger.debug(f"Completed incremental parsing in {total_time:.2f}s. "
                   f"Files: {len(files_to_parse)}, "
                   f"Successful: {successful_files}, "
                   f"Failed: {failed_files}")
    
    async def parse_single_file_wrapper_incremental(
        self, 
        file_path: Path
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
                self.repo_name,
                str(self.output_dir)
            )
            
            if nodes is not None and edges is not None:
                logger.debug(f"Successfully processed {file_path}: {len(nodes)} nodes, {len(edges)} edges")
                
                # Update metadata for successful parse
                self.change_detector.update_file_metadata(
                    file_path, 
                    parse_successful=True, 
                    error_message=None
                )
                
                return nodes, edges, str(file_path)
            else:
                logger.warning(f"Failed to process {file_path}")
                
                # Update metadata for failed parse
                self.change_detector.update_file_metadata(
                    file_path, 
                    parse_successful=False, 
                    error_message="Parsing returned None"
                )
                
                return None, None, str(file_path)
                
        except Exception as e:
            logger.debug(f"Error processing {file_path}: {e}")
            
            # Update metadata for failed parse
            self.change_detector.update_file_metadata(
                file_path, 
                parse_successful=False, 
                error_message=str(e)
            )
            
            return None, None, str(file_path)


async def parse_repository_incremental_main(
    repo_dir: str, 
    output_dir: str,
    file_paths: List[str]=[],# if provided, only parse these files
    max_concurrent: int = 5
) -> str:
    """Main function to incrementally update repository parsing results."""
    parser = RepositoryParser(repo_dir, output_dir)
    file_paths = [Path(path) for path in file_paths]
    return await parser.parse_repository_incremental(file_paths=file_paths, max_concurrent=max_concurrent)
