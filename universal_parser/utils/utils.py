from pathlib import Path
from typing import Set

# Common folders and files to ignore
IGNORE_PATTERNS = {
    # Version control
    '.git', '.svn', '.hg', '.bzr',
    # Dependencies
    'node_modules', 'bower_components', 'vendor',
    # Build/dist directories
    'build', 'dist', 'out', 'target', 'bin', 'obj',
    # Cache directories
    '.cache', '__pycache__', '.pytest_cache', '.mypy_cache',
    # IDE/Editor directories
    '.vscode', '.idea', '.eclipse', '.netbeans',
    # OS directories
    '.DS_Store', 'Thumbs.db', '.Trash',
    # Virtual environments
    'venv', '.venv', 'env', '.env', 'virtualenv',
    # Coverage/test outputs
    'coverage', '.nyc_output', '.coverage',
    # Logs
    'logs', 'log', '*.log',
    # Temporary files
    'tmp', 'temp', '.tmp', '.temp',
    # Package directories
    '.npm', '.yarn', '.pnpm-store'
}

def list_files_at_level_minus_one(proj_path: str, file_path: str, max_depth: int = 3, 
                                 include_directories: bool = True, 
                                 ignore_patterns: Set[str] = None) -> str:
    """
    Lists all relative paths of files and directories at level-1 from the specified file and their children.
    
    Args:
        proj_path (str): Absolute path to the project root
        file_path (str): Relative path to the specific file within the project
        max_depth (int): Maximum depth to traverse from level-1 directory (default: 3)
        include_directories (bool): Whether to include directories in the output (default: True)
        ignore_patterns (Set[str]): Set of folder/file patterns to ignore (default: uses IGNORE_PATTERNS)
    
    Returns:
        List[str]: List of relative paths (from project root) of all files/directories at level-1 and their children
    """
    # Convert to Path objects for easier manipulation
    proj_root = Path(proj_path)
    target_file = proj_root / file_path
    
    # Use default ignore patterns if none provided
    if ignore_patterns is None:
        ignore_patterns = IGNORE_PATTERNS
    
    def should_ignore(path: Path) -> bool:
        """Check if a path should be ignored based on ignore patterns"""
        path_name = path.name
        
        # Check exact name matches
        if path_name in ignore_patterns:
            return True
        
        # Check for patterns with wildcards
        for pattern in ignore_patterns:
            if '*' in pattern:
                import fnmatch
                if fnmatch.fnmatch(path_name, pattern):
                    return True
        
        # Check for hidden files/directories (starting with .)
        if path_name.startswith('.') and path_name not in {'.', '..'}:
            return True
            
        return False
    
    # Validate inputs
    if not proj_root.exists():
        raise ValueError(f"Project root does not exist: {proj_path}")
    
    if not target_file.exists():
        raise ValueError(f"Target file does not exist: {target_file}")
    
    # Get the directory containing the target file
    target_dir = target_file.parent
    
    # Get the parent directory (level-1)
    parent_dir = target_dir.parent
    
    # If we're already at project root, use project root as parent
    if parent_dir == proj_root.parent:
        parent_dir = proj_root
    
    result_files = []
    
    def add_files_recursively(directory: Path, current_files: Set[str], current_depth: int = 0):
        """Recursively add all files and directories from a directory up to max_depth"""
        if not directory.exists() or not directory.is_dir() or current_depth >= max_depth:
            return
        
        try:
            for item in directory.iterdir():
                # Skip ignored items
                if should_ignore(item):
                    continue
                
                rel_path = item.relative_to(proj_root)
                
                if item.is_file():
                    current_files.add(str(rel_path))
                elif item.is_dir():
                    # Add directory if requested
                    if include_directories and current_depth == max_depth - 1:
                        current_files.add(str(rel_path) + '/...') 
                    # Recursively process subdirectory
                    add_files_recursively(item, current_files, current_depth + 1)
        except PermissionError:
            # Skip directories we don't have permission to read
            pass
    
    # Set to avoid duplicates
    all_files = set()
    
    # Process all items in the parent directory (level-1)
    if parent_dir.exists():
        try:
            for item in parent_dir.iterdir():
                # Skip ignored items
                if should_ignore(item):
                    continue
                
                rel_path = item.relative_to(proj_root)
                
                if item.is_file():
                    # Add file at level-1
                    all_files.add(str(rel_path))
                elif item.is_dir():
                    # Add directory at level-1 if requested
                    # if include_directories:
                    #     all_files.add(str(rel_path) + '/')
                    # Add all files in subdirectories (children) up to max_depth
                    add_files_recursively(item, all_files, 1)
        except PermissionError:
            # Skip if we don't have permission to read the parent directory
            pass
    
    # Convert to sorted list
    result_files = sorted(list(all_files))

    # format the result_files to a string
    result_files_str = "\n  ".join(result_files)

    return f"Files at level-1 from '{file_path}' and their children (max depth: {max_depth}):\n  {result_files_str}"