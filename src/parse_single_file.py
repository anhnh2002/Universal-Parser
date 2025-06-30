import argparse
import asyncio
import os
from tree_sitter import Node
from tree_sitter_language_pack import get_parser

import config as config
from llm_services import run_llm_natively
from logger import logger

PROMPT_NORMALIZATION = """
Extract nodes and edges from the following formated AST.

Formated AST:
{formatted_ast}

Output schema:
{{
    "nodes": [
        # Internal nodes only, DO NOT include nodes that are not defined in the file; e.g. "utils.helper.HelperClass" is implemented in "utils.helper.py"
        {{
            "id": <relative_path_to_node>,# ignore file extention, replace `/` by `.`; e.g. "utils.helper.HelperClass"
            "start_line": <start_line>,# int
            "end_line": <end_line>,# int
            "type": <brief_description_of_the_node_type>
        }},
        ...
    ],
    "edges": [
        # DO include all kind of edges; e.g. "utils.helper.HelperClass" depends on "utils.helper.HelperClass.helper_method"
        {{
            "subject": <relative_path_to_node>,# e.g. "utils.helper.HelperClass"
            "object": <relative_path_to_node>,# e.g. "utils.helper.HelperClass.helper_method"
            "type": <brief_description_of_the_edge_type>
        }},
        ...
    ]
}}

Note: IGNORE built-in, third-party packages, and standard library dependencies.
"""

# ------------------------------------------------------------
# Format AST
# ------------------------------------------------------------

def format_ast(node: Node, indent: int = 0) -> str:
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
    language = config.EXTENSION_TO_LANGUAGE[extension]

    parser = get_parser(language)

    tree = parser.parse(file_content.encode())

    return format_ast(tree.root_node)



async def extract_nodes_and_edges(
    file_path: str,
    absolute_path_to_project: str
):

    relative_path = os.path.relpath(file_path, absolute_path_to_project)

    try:
        formatted_ast = parse_ast(file_path, absolute_path_to_project)
    except Exception as e:
        logger.error(f"Error parsing AST for {file_path}: {e}")
        logger.warning(f"Fallback to using raw file content for {file_path}")
        with open(file_path, "r") as file:
            formatted_ast = file.read()
    else:
        logger.info(f"Successfully parsed AST for {file_path}")

    formatted_ast = f"File: {relative_path}\n" + formatted_ast

    prompt = PROMPT_NORMALIZATION.format(formatted_ast=formatted_ast)
    llm_response = await run_llm_natively(prompt)

    logger.debug("##### Prompt #####")
    logger.debug(prompt)
    logger.debug("\n\n\n##### LLM Response #####")
    logger.debug(llm_response)

    # Try to parse the JSON response
    try:

        json_start = llm_response.find('{')
        json_end = llm_response.rfind('}') + 1

        result = eval(llm_response[json_start:json_end])
        
    except Exception as e:
        logger.error(f"Error parsing LLM response for {file_path}: {e}")
        logger.warning(f"Fallback to using raw file content for {file_path}")
        return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file-path", required=True, type=str, help="The file path to parse")
    parser.add_argument("--absolute-path-to-project", required=True, type=str, help="The absolute path to the project")

    args = parser.parse_args()

    asyncio.run(main(args.file_path, args.absolute_path_to_project))