import argparse
import asyncio
import os
import json
from tree_sitter import Node as TreeSitterNode
from tree_sitter_language_pack import get_parser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

from .patterns import CODE_EXTENSIONS
from ..utils.llm import get_llm_response
from ..core.models import Node, Edge
from ..utils.logger import logger
from ..utils.utils import list_files_at_level_minus_one

import traceback

# Constants
CHUNKING_THRESHOLD = 1000  # Lines threshold for chunking
CHUNK_SIZE = 800  # Target lines per chunk
CHUNK_OVERLAP = 50  # Lines to overlap between chunks for context

PROMPT_NORMALIZATION = """
Extract nodes and edges from the following formated AST and project structure context.

Project Structure:
{file_tree}

Formated AST:
{formatted_ast}

Output schema:
{{
    "nodes": [
        # Internal nodes only, DO NOT include nodes that are not defined in the file; e.g. "utils.helper.HelperClass" is implemented in "utils.helper.py"
        {{
            "id": <relative_path_to_node>,# ignore file extention; e.g. "utils.helper.HelperClass"
            "implementation_file": <relative_path_to_implementation_file>,# e.g. "utils/helper.py"
            "start_line": <start_line>,# int
            "end_line": <end_line>,# int
            "type": <brief_description_of_the_node_type>
        }},
        ...
    ],
    "edges": [
        # DO include all kind of edges; e.g. "utils.helper.HelperClass" depends on "utils.helper.HelperClass.helper_method", "utils.helper.HelperClass.helper_method" depends on "llms.ChatLLM", ...
        {{
            "subject_id": <relative_path_to_node>,# e.g. "utils.helper.HelperClass"
            "subject_implementation_file": <relative_path_to_subject_implementation_file>,# e.g. "utils/helper.py"
            "object_id": <relative_path_to_node>,# e.g. "utils.helper.HelperClass.helper_method"
            "object_implementation_file": <relative_path_to_object_implementation_file>,# e.g. "utils/helper.py"
            "type": <brief_description_of_the_edge_type>
        }},
        ...
    ]
}}

IMPORTANT INSTRUCTIONS:
- Use the EXACT file path shown at the beginning of the formatted AST as the base for all relative paths
- For node IDs: Convert the file path to dot notation and append the node name (e.g., if file is "autorag/autorag/chunker.py", use "autorag.autorag.chunker.ClassName")  
- For implementation_file: Use the EXACT file path as shown (e.g., "autorag/autorag/chunker.py")
- IGNORE built-in, third-party packages, and standard library dependencies
- IGNORE global variables Nodes
- Use the provided project structure to understand the context and relationships between files
"""

# ------------------------------------------------------------
# Format AST
# ------------------------------------------------------------

def format_ast(node: TreeSitterNode, indent: int = 0) -> str:
    result = ""
    if indent == 0:
        pass
    elif indent == 1:
        result += "\n" + '  ' * (indent-1) + f'Node type: {node.type}' + f"\n---Start Line: {node.start_point[0]}---\n"+node.text.decode("utf-8") + f"\n---End Line: {node.end_point[0]}---\n"
    else:
        return ""

    for child in node.children:
        result += format_ast(child, indent + 1)

    return result

# ------------------------------------------------------------
# Parse AST
# ------------------------------------------------------------

def parse_ast(file_path: str) -> str:
    with open(file_path, "r") as file:
        file_content = file.read()

    extension = "." + file_path.split(".")[-1]
    language = CODE_EXTENSIONS[extension]

    parser = get_parser(language)

    tree = parser.parse(file_content.encode())

    return format_ast(tree.root_node)

def recovery_invalid_file_path(absolute_path_to_project: str, file_path: str) -> str:
    """
    Recovery invalid file path.
    """
    absolute_file_path = os.path.join(absolute_path_to_project, file_path)
                
    if os.path.exists(absolute_file_path):
        return file_path
    else:
        logger.debug(f"Found invalid file path: {file_path}")
        # find available file paths matching the file_path in absolute_path_to_project directory, if there is only one, remove absolute_path_to_project and return it
        available_files = []
        for root, dirs, files in os.walk(absolute_path_to_project):
            for file in files:
                if os.path.join(root, file).endswith(file_path):
                    available_files.append(os.path.join(root, file))

        if len(available_files) == 1:
            file_path = available_files[0].replace(absolute_path_to_project, "")
            if file_path.startswith(os.sep):
                file_path = file_path[1:]
            logger.debug(f"Recovery to {file_path} instead")
            return file_path
        else:
            logger.debug(f"Found multiple or no available file paths {available_files} matching the file path, recovery failed!")
            return None

# ------------------------------------------------------------
# Retryable LLM Response Parser
# ------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((json.JSONDecodeError, SyntaxError, KeyError, ValueError)),
    reraise=True,
    before_sleep=before_sleep_log(logger, logger.debug)
)
async def parse_llm_response_with_retry(prompt: str, file_path: str, absolute_path_to_project: str) -> tuple[list[Node], list[Edge]]:
    """
    Parse LLM response with retry functionality for robust error handling.
    
    Args:
        prompt: The formatted prompt to send to LLM
        file_path: The file path being processed (for logging)
        
    Returns:
        Tuple of (nodes, edges) lists
        
    Raises:
        Exception: If parsing fails after all retries
    """
    logger.debug(f"Attempting to parse LLM response for {file_path}")

    logger.debug("##### Prompt #####")
    logger.debug(prompt)
    
    llm_response = await get_llm_response(prompt)

    if "</think>" in llm_response:
        llm_response = llm_response.split("</think>")[-1]

    logger.debug("\n\n\n##### LLM Response #####")
    logger.debug(llm_response)

    # Extract JSON from response
    json_start = llm_response.find('{')
    json_end = llm_response.rfind('}') + 1
    
    if json_start == -1 or json_end == 0:
        logger.debug(f"No valid JSON found in LLM response for {file_path}")
        logger.debug(f"LLM Response that caused the error:\n{llm_response}")
        raise ValueError(f"No valid JSON found in LLM response for {file_path}")
    
    json_str = llm_response[json_start:json_end]
    
    # Parse JSON (prefer json.loads over eval for security)
    try:
        result = json.loads(json_str)
    except json.JSONDecodeError:
        # Fallback to eval if json.loads fails (for malformed JSON)
        logger.warning(f"JSON parsing failed for {file_path}, trying eval as fallback")
        try:
            result = eval(json_str)
        except Exception as eval_error:
            logger.debug(f"Both JSON parsing and eval failed for {file_path}: {eval_error}")
            logger.debug(f"LLM Response that caused the error:\n{llm_response}")
            raise
    
    # Validate required keys exist
    if "nodes" not in result or "edges" not in result:
        logger.debug(f"Missing required keys 'nodes' or 'edges' in LLM response for {file_path}")
        logger.debug(f"LLM Response that caused the error:\n{llm_response}")
        raise KeyError(f"Missing required keys 'nodes' or 'edges' in LLM response for {file_path}")
    
    # Create Node and Edge objects
    nodes = []
    for node in result["nodes"]:
        try:
            _node = Node(**node)
            _node.implementation_file = recovery_invalid_file_path(absolute_path_to_project, _node.implementation_file)
            if _node.implementation_file is not None:
                # Extract code snippet for the node
                _node.code_snippet = extract_code_snippet(
                    _node.implementation_file, 
                    _node.start_line, 
                    _node.end_line, 
                    absolute_path_to_project
                )
                nodes.append(_node)
            else:
                pass
        except Exception as e:
            logger.debug(f"Error creating Node object for {node}: {e}")
            continue
    edges = []
    for edge in result["edges"]:
        try:
            _edge = Edge(**edge)
            _edge.subject_implementation_file = recovery_invalid_file_path(absolute_path_to_project, _edge.subject_implementation_file)
            _edge.object_implementation_file = recovery_invalid_file_path(absolute_path_to_project, _edge.object_implementation_file)
            if _edge.subject_implementation_file is not None and _edge.object_implementation_file is not None:
                edges.append(_edge)
            else:
                pass
        except Exception as e:
            logger.debug(f"Error creating Edge object for {edge}: {e}")
            continue
    
    return nodes, edges

# ------------------------------------------------------------
# Code Snippet Extraction
# ------------------------------------------------------------

def extract_code_snippet(file_path: str, start_line: int, end_line: int, absolute_path_to_project: str) -> str:
    """
    Extract code snippet from a file between start_line and end_line (inclusive).
    
    Args:
        file_path: Relative path to the file
        start_line: Starting line number (1-indexed)
        end_line: Ending line number (1-indexed)
        absolute_path_to_project: Absolute path to the project root
        
    Returns:
        The code snippet as a string, or empty string if extraction fails
    """
    try:
        # Convert to absolute path
        absolute_file_path = os.path.join(absolute_path_to_project, file_path)
        
        if not os.path.exists(absolute_file_path):
            logger.warning(f"File not found for code snippet extraction: {absolute_file_path}")
            return ""
        
        with open(absolute_file_path, 'r', encoding='utf-8') as file:
            file_content = file.read()

        lines = file_content.split("\n")
        
        # Convert to 0-indexed and ensure valid range
        start_idx = max(0, start_line)
        end_idx = min(len(lines), end_line + 1)
        
        if start_idx >= len(lines) or end_idx <= start_idx:
            logger.warning(f"Invalid line range for {file_path}: {start_line}-{end_line}")
            return ""
        
        # Extract and return the snippet
        snippet_lines = lines[start_idx:end_idx]
        return '\n'.join(snippet_lines)
        
    except Exception as e:
        logger.debug(f"Error extracting code snippet from {file_path} (lines {start_line}-{end_line}): {e}")
        return ""

# ------------------------------------------------------------
# File Line Counting
# ------------------------------------------------------------

def count_file_lines(file_path: str) -> int:
    """Count the number of lines in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return sum(1 for _ in file)
    except Exception as e:
        logger.warning(f"Error counting lines in {file_path}: {e}")
        return 0

# ------------------------------------------------------------
# AST Chunking
# ------------------------------------------------------------

def chunk_formatted_ast(formatted_ast: str, file_header: str) -> list[str]:
    """
    Split formatted AST into chunks based on AST nodes to avoid breaking in the middle of nodes.
    
    Args:
        formatted_ast: The formatted AST string
        file_header: The file header (e.g., "File: path/to/file.py")
        
    Returns:
        List of AST chunks, each with the file header
    """
    lines = formatted_ast.split('\n')
    chunks = []
    current_chunk = [file_header]
    current_chunk_lines = 1
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Skip the file header if it's already in the original
        if line.startswith("File: ") and i == 0:
            i += 1
            continue
            
        # Check if this is the start of a new node (Node type: ...)
        if line.strip().startswith('Node type: '):
            # If adding this node would exceed chunk size, start a new chunk
            if current_chunk_lines > CHUNK_SIZE:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [file_header]
                current_chunk_lines = 1
            
            # Find the end of this node (next "Node type:" or end of content)
            node_lines = [line]
            j = i + 1
            
            # Read until we find the next node or reach the end
            while j < len(lines):
                next_line = lines[j]
                if next_line.strip().startswith('Node type: '):
                    break
                node_lines.append(next_line)
                j += 1
            
            # Add the complete node to current chunk
            current_chunk.extend(node_lines)
            current_chunk_lines += len(node_lines)
            i = j
        else:
            # Add non-node lines
            current_chunk.append(line)
            current_chunk_lines += 1
            i += 1
    
    # Add the last chunk if it has content
    if len(current_chunk) > 1:  # More than just the header
        chunks.append('\n'.join(current_chunk))
    
    # If no chunks were created but we have content, create a single chunk
    if not chunks and formatted_ast.strip():
        chunks.append(formatted_ast)
    
    logger.debug(f"Split AST into {len(chunks)} chunks")
    return chunks

# ------------------------------------------------------------
# Chunk Processing
# ------------------------------------------------------------

async def process_chunk(
    chunk: str,
    file_tree: str,
    file_path: str,
    absolute_path_to_project: str,
    chunk_index: int
) -> tuple[list[Node], list[Edge]]:
    """Process a single chunk of formatted AST."""
    try:
        prompt = PROMPT_NORMALIZATION.format(formatted_ast=chunk, file_tree=file_tree)
        
        logger.debug(f"Processing chunk {chunk_index + 1} for {file_path}")
        nodes, edges = await parse_llm_response_with_retry(prompt, f"{file_path}_chunk_{chunk_index}", absolute_path_to_project)
        
        return nodes, edges
    except Exception as e:
        logger.error(f"Error processing chunk {chunk_index + 1} for {file_path}: {e}")
        return [], []

# ------------------------------------------------------------
# Result Deduplication
# ------------------------------------------------------------

def deduplicate_results(all_nodes: list[Node], all_edges: list[Edge]) -> tuple[list[Node], list[Edge]]:
    """Remove duplicate nodes and edges from combined results."""
    # Deduplicate nodes by id
    seen_nodes = set()
    unique_nodes = []
    for node in all_nodes:
        if node.id not in seen_nodes:
            seen_nodes.add(node.id)
            unique_nodes.append(node)
    
    # Deduplicate edges by subject_id and object_id combination
    seen_edges = set()
    unique_edges = []
    for edge in all_edges:
        edge_key = (edge.subject_id, edge.object_id)
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            unique_edges.append(edge)
    
    logger.debug(f"Deduplicated {len(all_nodes)} nodes to {len(unique_nodes)} unique nodes")
    logger.debug(f"Deduplicated {len(all_edges)} edges to {len(unique_edges)} unique edges")
    
    return unique_nodes, unique_edges

# ------------------------------------------------------------

async def extract_nodes_and_edges(
    file_path: str,
    absolute_path_to_project: str,
    repo_name: str,
    output_dir: str
):
    """Extract nodes and edges from a single file."""
    relative_path = os.path.relpath(file_path, absolute_path_to_project)

    try:
        formatted_ast = parse_ast(file_path)
    except Exception as e:
        logger.warning(f"Error parsing AST for {file_path}")
        # logger.warning(f"Fallback to using raw file content for {file_path}")
        logger.error(traceback.format_exc())
        raise e
        # with open(file_path, "r") as file:
        #     formatted_ast = file.read()
    else:
        logger.debug(f"Successfully parsed AST for {file_path}")

    # Determine if chunking is needed
    total_lines = count_file_lines(file_path)
    if total_lines >= CHUNKING_THRESHOLD:
        logger.debug(f"File {file_path} exceeds chunking threshold ({CHUNKING_THRESHOLD} lines). Chunking AST.")
        file_header = f"File: {relative_path}"
        chunks = chunk_formatted_ast(formatted_ast, file_header)
        
        all_nodes = []
        all_edges = []
        
        # Process chunks concurrently
        file_tree = list_files_at_level_minus_one(absolute_path_to_project, relative_path)
        tasks = [
            process_chunk(chunk, file_tree, relative_path, absolute_path_to_project, i)
            for i, chunk in enumerate(chunks)
        ]
        
        # Wait for all chunks to complete
        results = await asyncio.gather(*tasks)
        
        # Collect results from all chunks
        for nodes, edges in results:
            if nodes:
                all_nodes.extend(nodes)
            if edges:
                all_edges.extend(edges)
        
        # Deduplicate results across chunks
        unique_nodes, unique_edges = deduplicate_results(all_nodes, all_edges)
        logger.debug(f"Total nodes after deduplication: {len(unique_nodes)}")
        logger.debug(f"Total edges after deduplication: {len(unique_edges)}")
        
        # Save combined results to json
        output_dir = os.path.join(output_dir, repo_name, *relative_path.split("/")[:-1])
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, relative_path.split("/")[-1] + ".json")

        with open(output_path, "w") as file:
            json.dump({"nodes": [node.model_dump() for node in unique_nodes], "edges": [edge.model_dump() for edge in unique_edges]}, file, indent=4)

        logger.debug(f"Successfully extracted nodes and edges for {file_path}. Result saved to {output_path}")
        
        return unique_nodes, unique_edges
    else:
        logger.debug(f"File {file_path} does not exceed chunking threshold ({CHUNKING_THRESHOLD} lines). Processing as a single chunk.")
        
        # Format the AST with file header
        formatted_ast = f"File: {relative_path}\n" + formatted_ast
        
        # Create prompt
        prompt = PROMPT_NORMALIZATION.format(formatted_ast=formatted_ast, file_tree=list_files_at_level_minus_one(absolute_path_to_project, relative_path))

        # Try to parse the JSON response with retry mechanism
        try:
            # save nodes and edges to json
            output_dir = os.path.join(output_dir, repo_name, *relative_path.split("/")[:-1])
            os.makedirs(output_dir, exist_ok=True)
            output_path = os.path.join(output_dir, relative_path.split("/")[-1] + ".json")

            nodes, edges = await parse_llm_response_with_retry(prompt, file_path, absolute_path_to_project)

            with open(output_path, "w") as file:
                json.dump({"nodes": [node.model_dump() for node in nodes], "edges": [edge.model_dump() for edge in edges]}, file, indent=4)

            logger.debug(f"Successfully extracted nodes and edges for {file_path}. Result saved to {output_path}")

            return nodes, edges
            
        except Exception as e:
            logger.debug(f"Error parsing LLM response for {file_path} after all retries: {e}")
            logger.debug(traceback.format_exc())
            logger.debug(f"This indicates a persistent issue with the LLM response format or content")
            return None, None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file-path", required=True, type=str, help="The file path to parse")
    parser.add_argument("--absolute-path-to-project", required=True, type=str, help="The absolute path to the project")
    parser.add_argument("--repo-name", default="default", type=str, help="The name of the repository")
    parser.add_argument("--output-dir", required=True, type=str, help="The output directory")
    
    args = parser.parse_args()

    asyncio.run(extract_nodes_and_edges(args.file_path, args.absolute_path_to_project, args.repo_name, args.output_dir)) 