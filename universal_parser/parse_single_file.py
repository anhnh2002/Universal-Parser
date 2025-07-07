import argparse
import asyncio
import os
import json
from tree_sitter import Node as TreeSitterNode
from tree_sitter_language_pack import get_parser
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log

from . import config
from .patterns import CODE_EXTENSIONS
from .llm_services import get_llm_response
from .schema import Node, Edge
from .logger import logger
import traceback

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
# Generate File Tree
# ------------------------------------------------------------

def generate_file_tree(start_path: str, relative_file_path: str, max_depth: int = 3, max_files: int = 100) -> str:
    """
    Generate a file tree starting from the first folder of the relative path.
    
    Args:
        start_path: The absolute path to the project root
        relative_file_path: The relative path of the file being processed
        max_depth: Maximum depth to traverse (default: 3)
        max_files: Maximum number of files to include (default: 100)
        
    Returns:
        A formatted file tree string
    """
    # Get relative directory path
    relative_dir_path = os.path.join(start_path, os.path.dirname(relative_file_path))
    
    # Get the first folder from the relative path
    path_parts = relative_file_path.split(os.sep)
    if len(path_parts) > 1:
        first_folder = path_parts[0]
        tree_start_path = os.path.join(start_path, first_folder)
    else:
        # If the file is in the root, use the project root
        tree_start_path = start_path
        first_folder = "."
    
    if not os.path.exists(tree_start_path):
        return f"{first_folder}/\n  (directory not found)"
    
    def _build_tree(path: str, prefix: str = "", depth: int = 0, file_count: list = [0]) -> str:
        if depth >= max_depth or file_count[0] >= max_files:
            return ""
        
        p_parts = path.split(os.sep)
        r_parts = relative_dir_path.split(os.sep)
        l_p = len(p_parts)
        l_r = len(r_parts)
        if l_p < l_r:
            if p_parts[l_p-1] != r_parts[l_p-1]:
                return f"{prefix}..."
        else:
            if p_parts[l_r-1] != r_parts[l_r-1]:
                return f"{prefix}..."
        
        tree = ""
        try:
            items = sorted(os.listdir(path))
            # Filter out common non-essential files/directories
            items = [item for item in items if not item.startswith('.') and 
                    item not in ['__pycache__', 'node_modules', '.git', '.vscode', 'venv', 'env', 'tests']]
            
            for i, item in enumerate(items):
                if file_count[0] >= max_files:
                    break
                    
                item_path = os.path.join(path, item)

                is_last = i == len(items) - 1
                current_prefix = "└── " if is_last else "├── "
                
                if os.path.isdir(item_path):
                    tree += f"{prefix}{current_prefix}{item}/\n"
                    next_prefix = prefix + ("    " if is_last else "│   ")
                    tree += _build_tree(item_path, next_prefix, depth + 1, file_count)
                else:
                    tree += f"{prefix}{current_prefix}{item}\n"
                    file_count[0] += 1
                    
        except PermissionError:
            tree += f"{prefix}├── (permission denied)\n"
        except Exception as e:
            tree += f"{prefix}├── (error: {str(e)})\n"
            
        return tree
    
    if tree_start_path == start_path:
        tree_header = "Project Root:\n"
    else:
        tree_header = f"{first_folder}/\n"
    
    return tree_header + _build_tree(tree_start_path)

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
        logger.warning(f"Found invalid file path: {file_path}")
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
            logger.warning(f"Recovery to {file_path} instead")
            return file_path
        else:
            logger.error(f"Found multiple or no available file paths {available_files} matching the file path, recovery failed!")
            return None

# ------------------------------------------------------------
# Retryable LLM Response Parser
# ------------------------------------------------------------

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((json.JSONDecodeError, SyntaxError, KeyError, ValueError)),
    reraise=True,
    before_sleep=before_sleep_log(logger, logger.info)
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
        logger.error(f"No valid JSON found in LLM response for {file_path}")
        logger.error(f"LLM Response that caused the error:\n{llm_response}")
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
            logger.error(f"Both JSON parsing and eval failed for {file_path}: {eval_error}")
            logger.error(f"LLM Response that caused the error:\n{llm_response}")
            raise
    
    # Validate required keys exist
    if "nodes" not in result or "edges" not in result:
        logger.error(f"Missing required keys 'nodes' or 'edges' in LLM response for {file_path}")
        logger.error(f"LLM Response that caused the error:\n{llm_response}")
        raise KeyError(f"Missing required keys 'nodes' or 'edges' in LLM response for {file_path}")
    
    # Create Node and Edge objects
    nodes = []
    for node in result["nodes"]:
        try:
            _node = Node(**node)
            _node.implementation_file = recovery_invalid_file_path(absolute_path_to_project, _node.implementation_file)
            if _node.implementation_file is not None:
                nodes.append(_node)
            else:
                pass
        except Exception as e:
            logger.error(f"Error creating Node object for {node}: {e}")
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
            logger.error(f"Error creating Edge object for {edge}: {e}")
            continue
    
    return nodes, edges


async def extract_nodes_and_edges(
    file_path: str,
    absolute_path_to_project: str,
    repo_name: str = "default"
):
    """Extract nodes and edges from a single file."""
    relative_path = os.path.relpath(file_path, absolute_path_to_project)

    try:
        formatted_ast = parse_ast(file_path)
    except Exception as e:
        logger.error(f"Error parsing AST for {file_path}: {e}")
        logger.warning(f"Fallback to using raw file content for {file_path}")
        with open(file_path, "r") as file:
            formatted_ast = file.read()
    else:
        logger.debug(f"Successfully parsed AST for {file_path}")

    formatted_ast = f"File: {relative_path}\n" + formatted_ast

    prompt = PROMPT_NORMALIZATION.format(formatted_ast=formatted_ast, file_tree=generate_file_tree(absolute_path_to_project, relative_path))

    # Try to parse the JSON response with retry mechanism
    try:
        # save nodes and edges to json
        output_dir = os.path.join(config.OUTPUT_DIR, repo_name, *relative_path.split("/")[:-1])
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, relative_path.split("/")[-1] + ".json")

        if os.path.exists(output_path):
            logger.debug(f"Skipping {file_path} because it already exists")
            # read nodes and edges from json
            with open(output_path, "r") as file:
                result = json.load(file)
                nodes = [Node(**node) for node in result["nodes"]]
                edges = [Edge(**edge) for edge in result["edges"]]

            await asyncio.sleep(1)

            return nodes, edges

        nodes, edges = await parse_llm_response_with_retry(prompt, file_path, absolute_path_to_project)

        with open(output_path, "w") as file:
            json.dump({"nodes": [node.model_dump() for node in nodes], "edges": [edge.model_dump() for edge in edges]}, file, indent=4)

        logger.debug(f"Successfully extracted nodes and edges for {file_path}. Result saved to {output_path}")

        return nodes, edges
        
    except Exception as e:
        logger.error(f"Error parsing LLM response for {file_path} after all retries: {e}")
        logger.error(traceback.format_exc())
        logger.error(f"This indicates a persistent issue with the LLM response format or content")
        return None, None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file-path", required=True, type=str, help="The file path to parse")
    parser.add_argument("--absolute-path-to-project", required=True, type=str, help="The absolute path to the project")
    parser.add_argument("--repo-name", default="default", type=str, help="The name of the repository")

    args = parser.parse_args()

    asyncio.run(extract_nodes_and_edges(args.file_path, args.absolute_path_to_project, args.repo_name + f"-{config.LLM_MODEL.split('/')[-1]}")) 