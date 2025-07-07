#!/usr/bin/env python3
"""
Convert gitprobe output format (relationships.json + functions.json) 
to aggregated_results.json format.
"""

import json
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Any
from collections import defaultdict


def normalize_path(file_path: str, temp_dir_pattern: str) -> str:
    """
    Convert absolute temp path to relative src path.
    
    Args:
        file_path: Absolute path like "/var/folders/.../T/gitprobe_xyz/src/app.py"
        temp_dir_pattern: Pattern to match temp directory
    
    Returns:
        Relative path like "src/app.py"
    """
    # Remove temp directory prefix and leading slash
    if temp_dir_pattern in file_path:
        # Split on the temp directory pattern and take the part after it
        parts = file_path.split(temp_dir_pattern)
        if len(parts) > 1:
            # Get everything after the temp dir, remove leading slash
            relative_path = parts[1].lstrip('/')
            return relative_path
    
    # Fallback: if pattern not found, try to extract src/ onwards
    if '/src/' in file_path:
        src_index = file_path.find('/src/')
        return file_path[src_index + 1:]  # +1 to remove leading slash
    
    # Last fallback: return as is
    return file_path


def extract_temp_dir_pattern(file_paths: List[str]) -> str:
    """
    Extract the common temp directory pattern from file paths.
    
    Args:
        file_paths: List of absolute file paths
    
    Returns:
        Common temp directory pattern
    """
    if not file_paths:
        return ""
    
    # Look for gitprobe temp directory pattern
    for path in file_paths:
        match = re.search(r'/T/gitprobe_[^/]+/', path)
        if match:
            return match.group(0)
    
    # Fallback: find common prefix up to a temp-like directory
    common_prefix = os.path.commonpath(file_paths)
    return common_prefix


def parse_caller_callee(caller_callee_str: str, temp_dir_pattern: str) -> tuple:
    """
    Parse caller/callee string format.
    
    Args:
        caller_callee_str: Format like "/path/to/file.py:function_name"
        temp_dir_pattern: Temp directory pattern to remove
    
    Returns:
        (file_path, function_name) tuple
    """
    if ':' in caller_callee_str:
        file_path, func_name = caller_callee_str.rsplit(':', 1)
        normalized_file = normalize_path(file_path, temp_dir_pattern)
        return normalized_file, func_name
    else:
        # External function call without file path
        return None, caller_callee_str


def create_node_id(file_path: str, func_name: str, class_name: str = None) -> str:
    """
    Create a node ID in the format expected by aggregated_results.json.
    
    Args:
        file_path: Relative file path like "src/app.py"
        func_name: Function name
        class_name: Optional class name
    
    Returns:
        Node ID like "src.app.ping" or "src.clients.cache_clients.ShortTermCacheClient.get"
    """
    # Convert file path to module path
    module_path = file_path.replace('/', '.').replace('.py', '')
    
    if class_name:
        return f"{module_path}.{class_name}.{func_name}"
    else:
        return f"{module_path}.{func_name}"


def determine_node_type(func_info: Dict) -> str:
    """
    Determine the node type based on function information.
    
    Args:
        func_info: Function information from functions.json
    
    Returns:
        Node type string
    """
    if func_info.get('is_method', False):
        if 'async ' in func_info.get('code_snippet', ''):
            return 'async_method_definition'
        else:
            return 'method_definition'
    else:
        if 'async ' in func_info.get('code_snippet', ''):
            return 'async_function_definition'
        else:
            return 'function_definition'


def create_class_node_id(file_path: str, class_name: str) -> str:
    """
    Create a class node ID in the format expected by aggregated_results.json.
    
    Args:
        file_path: Relative file path like "src/clients/cache_clients.py"
        class_name: Class name like "ShortTermCacheClient"
    
    Returns:
        Node ID like "src.clients.cache_clients.ShortTermCacheClient"
    """
    # Convert file path to module path
    module_path = file_path.replace('/', '.').replace('.py', '')
    return f"{module_path}.{class_name}"


def extract_class_info(functions: List[Dict], temp_dir_pattern: str) -> Dict[str, Dict]:
    """
    Extract class information from functions data.
    
    Args:
        functions: List of function information from functions.json
        temp_dir_pattern: Temp directory pattern to normalize paths
    
    Returns:
        Dictionary mapping class_id to class info
    """
    classes = {}
    
    for func in functions:
        if func.get('class_name') and func.get('is_method', False):
            normalized_file = normalize_path(func['file_path'], temp_dir_pattern)
            class_name = func['class_name']
            class_id = create_class_node_id(normalized_file, class_name)
            
            if class_id not in classes:
                # Find the earliest line start and latest line end for the class
                classes[class_id] = {
                    'id': class_id,
                    'implementation_file': normalized_file,
                    'class_name': class_name,
                    'start_line': func['line_start'],
                    'end_line': func['line_end'],
                    'methods': []
                }
            else:
                # Update class boundaries to encompass all methods
                classes[class_id]['start_line'] = min(classes[class_id]['start_line'], func['line_start'])
                classes[class_id]['end_line'] = max(classes[class_id]['end_line'], func['line_end'])
            
            # Add method to class
            method_id = create_node_id(normalized_file, func['name'], class_name)
            classes[class_id]['methods'].append(method_id)
    
    return classes


def determine_edge_type(caller_info: Dict, callee_info: Dict) -> str:
    """
    Determine the relationship type between caller and callee.
    
    Args:
        caller_info: Caller function information
        callee_info: Callee function information
    
    Returns:
        Edge type string
    """
    caller_is_method = caller_info.get('is_method', False) if caller_info else False
    callee_is_method = callee_info.get('is_method', False) if callee_info else False
    
    if caller_is_method and callee_is_method:
        return 'calls_method'
    elif caller_is_method and not callee_is_method:
        return 'calls_function'
    elif not caller_is_method and callee_is_method:
        return 'calls_method'
    else:
        return 'calls_function'


def convert_gitprobe_to_aggregated(
    relationships_file: str,
    functions_file: str,
    output_file: str,
    repo_name: str = None,
    repo_dir: str = None
):
    """
    Convert gitprobe output to aggregated_results.json format.
    
    Args:
        relationships_file: Path to relationships.json
        functions_file: Path to functions.json  
        output_file: Path to output aggregated_results.json
        repo_name: Repository name (optional)
        repo_dir: Repository path (optional)
    """
    # Load input files
    with open(relationships_file, 'r') as f:
        relationships = json.load(f)
    
    with open(functions_file, 'r') as f:
        functions = json.load(f)
    
    # Extract temp directory pattern
    all_file_paths = [func['file_path'] for func in functions]
    temp_dir_pattern = extract_temp_dir_pattern(all_file_paths)
    
    # Build function lookup by normalized path and name
    func_lookup = {}
    for func in functions:
        normalized_file = normalize_path(func['file_path'], temp_dir_pattern)
        key = (normalized_file, func['name'])
        func_lookup[key] = func
    
    # Extract class information
    classes_info = extract_class_info(functions, temp_dir_pattern)
    
    # Build nodes
    nodes = []
    node_ids = set()
    
    # Add class nodes
    for class_info in classes_info.values():
        nodes.append({
            'id': class_info['id'],
            'implementation_file': class_info['implementation_file'],
            'start_line': class_info['start_line'],
            'end_line': class_info['end_line'],
            'type': 'class_definition'
        })
        node_ids.add(class_info['id'])
    
    # Add function/method nodes
    for func in functions:
        normalized_file = normalize_path(func['file_path'], temp_dir_pattern)
        node_id = create_node_id(normalized_file, func['name'], func.get('class_name'))
        
        if node_id not in node_ids:
            node_ids.add(node_id)
            nodes.append({
                'id': node_id,
                'implementation_file': normalized_file,
                'start_line': func['line_start'],
                'end_line': func['line_end'],
                'type': determine_node_type(func)
            })
    
    # Build edges
    edges = []
    edge_set = set()  # To avoid duplicates
    
    for rel in relationships:
        if not rel.get('is_resolved', False):
            continue  # Skip unresolved calls
        
        caller_file, caller_func = parse_caller_callee(rel['caller'], temp_dir_pattern)
        callee_file, callee_func = parse_caller_callee(rel['callee'], temp_dir_pattern)
        
        if not caller_file or not callee_file:
            continue  # Skip external calls
        
        # Get function info for type determination
        caller_info = func_lookup.get((caller_file, caller_func))
        callee_info = func_lookup.get((callee_file, callee_func))
        
        if not caller_info or not callee_info:
            continue  # Skip if function info not found
        
        # Create node IDs
        caller_id = create_node_id(caller_file, caller_func, caller_info.get('class_name'))
        callee_id = create_node_id(callee_file, callee_func, callee_info.get('class_name'))
        
        # Create edge
        edge_key = (caller_id, callee_id)
        if edge_key not in edge_set:
            edge_set.add(edge_key)
            edges.append({
                'subject_id': caller_id,
                'subject_implementation_file': caller_file,
                'object_id': callee_id,
                'object_implementation_file': callee_file,
                'type': determine_edge_type(caller_info, callee_info)
            })
    
    # Add contains_method edges from classes to their methods
    for class_info in classes_info.values():
        for method_id in class_info['methods']:
            edge_key = (class_info['id'], method_id)
            if edge_key not in edge_set:
                edge_set.add(edge_key)
                edges.append({
                    'subject_id': class_info['id'],
                    'subject_implementation_file': class_info['implementation_file'],
                    'object_id': method_id,
                    'object_implementation_file': class_info['implementation_file'],
                    'type': 'contains_method'
                })
    
    # Calculate statistics
    type_counts = defaultdict(int)
    for node in nodes:
        type_counts[node['type']] += 1
    
    edge_type_counts = defaultdict(int)
    for edge in edges:
        edge_type_counts[edge['type']] += 1
    
    # Build final result
    result = {
        'repository': {
            'name': repo_name or 'unknown',
            'path': repo_dir or 'unknown',
            'total_files_processed': len(set(normalize_path(func['file_path'], temp_dir_pattern) for func in functions)),
            'total_files_failed': 0,
            'failed_files': []
        },
        'nodes': nodes,
        'edges': edges,
        'statistics': {
            'total_nodes': len(nodes),
            'total_edges': len(edges),
            'nodes_by_type': dict(type_counts),
            'edges_by_type': dict(edge_type_counts),
            'files_by_language': {
                'python': len(set(normalize_path(func['file_path'], temp_dir_pattern) for func in functions))
            }
        }
    }
    
    # Write output
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(result, f, indent=2)
    
    print(f"Converted {len(functions)} functions and {len(relationships)} relationships")
    print(f"Generated {len(nodes)} nodes and {len(edges)} edges")
    print(f"Output written to: {output_file}")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert gitprobe output to aggregated_results.json format')
    parser.add_argument('relationships_file', help='Path to relationships.json')
    parser.add_argument('functions_file', help='Path to functions.json')
    parser.add_argument('output_file', help='Path to output aggregated_results.json')
    parser.add_argument('--repo-name', help='Repository name')
    parser.add_argument('--repo-dir', help='Repository path')
    
    args = parser.parse_args()
    
    convert_gitprobe_to_aggregated(
        args.relationships_file,
        args.functions_file,
        args.output_file,
        args.repo_name,
        args.repo_dir
    ) 