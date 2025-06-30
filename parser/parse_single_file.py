import argparse

from tree_sitter import Tree, Language, Node
from tree_sitter_language_pack import get_language, get_parser

from src.config import get_project_path

def load_query(language: str, capture: str) -> str:
    with open(get_project_path(f"queries/{capture}/{language}.txt"), "r") as f:
        return f.read()

def load_file(language: str, extension: str) -> str:
    with open(get_project_path(f"examples/{language}.{extension}"), "r") as f:
        return f.read()

def extract_import_names(node, language: str) -> list:
    """Extract import names based on the specific language's AST structure."""
    names = []
    
    if language == "python":
        # For Python: handle both import_statement and import_from_statement
        if node.type == "import_statement":
            # import os, sys, numpy as np
            for child in node.children:
                if child.type == "dotted_name":
                    names.append(child.text.decode("utf-8"))
                elif child.type == "aliased_import":
                    # Handle "numpy as np" case
                    names.append(child.text.decode("utf-8"))
        elif node.type == "import_from_statement":
            # from typing import List, Dict
            capturing = False
            for child in node.children:
                if child.type == "import":
                    capturing = True
                elif capturing and child.type in ["dotted_name", "identifier", "aliased_import"]:
                    names.append(child.text.decode("utf-8"))
                elif capturing and child.type == "import_list":
                    # Handle multiple imports: from typing import List, Dict
                    for subchild in child.children:
                        if subchild.type in ["dotted_name", "identifier", "aliased_import"]:
                            names.append(subchild.text.decode("utf-8"))
    
    elif language == "java":
        # For Java: extract from scoped_identifier or identifier
        def extract_java_path(node):
            if node.type == "identifier":
                return node.text.decode("utf-8")
            elif node.type == "scoped_identifier":
                parts = []
                for child in node.children:
                    if child.type == "identifier":
                        parts.append(child.text.decode("utf-8"))
                    elif child.type == "scoped_identifier":
                        parts.append(extract_java_path(child))
                return ".".join(filter(None, parts))
            return ""
        
        for child in node.children:
            if child.type in ["scoped_identifier", "identifier"]:
                path = extract_java_path(child)
                if path:
                    names.append(path)
            elif child.type == "asterisk":
                # Handle wildcard imports like java.io.*
                if names:  # If we already extracted a path, append the asterisk
                    names[-1] += ".*"
                else:
                    names.append("*")
    
    elif language == "cpp":
        # For C++: extract from system_lib_string or string_literal
        for child in node.children:
            if child.type == "system_lib_string":
                # Remove < and > brackets
                include_name = child.text.decode("utf-8").strip("<>")
                names.append(include_name)
            elif child.type == "string_literal":
                # Handle "myheader.h" case - extract content without quotes
                for subchild in child.children:
                    if subchild.type == "string_content":
                        names.append(subchild.text.decode("utf-8"))
    
    return names




def parse_importation(tree: Tree, query: str, language: Language, lang_name: str) -> None:
    import_query = language.query(query)
    captures = import_query.captures(tree.root_node)
    for key, value in captures.items():
        print("#"*10 + str(key) + "#"*10)
        for node in value:
            print("="*10)
            print(node.text.decode("utf-8"))
            
            # Extract import names using language-specific logic
            import_names = extract_import_names(node, lang_name)
            print(import_names)

# # Function to print AST recursively
# def print_node(node: Node, source_code: str, indent: int = 0):
#     first_line = ""
#     for line in node.text.decode("utf-8").split("\n"):
#         if line.strip():
#             first_line = line.strip()
#             break
#     print('  ' * indent + f'{node.type}' + " | " + first_line)# ({node.start_point} - {node.end_point})')
#     for child in node.children:
#         print_node(child, source_code, indent + 1)

# Function to print AST recursively
def print_node(node: Node, source_code: str, indent: int = 0):
    if indent == 0:
        # print('  ' * indent + f'{node.type}')
        pass
    elif indent == 1:
        print('  ' * (indent-1) + f'{node.type}' + f' | Start line:{node.start_point[0]} - End line:{node.end_point[0]}' + "\n---Start---\n"+node.text.decode("utf-8")+"\n---End---\n")# ({node.start_point} - {node.end_point})')
    else:
        return

    for child in node.children:
        print_node(child, source_code, indent + 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", required=True, type=str, help="The programming language to parse")
    parser.add_argument("--extension", required=True, type=str, help="The file extension to parse")
    parser.add_argument("--capture", required=True, choices=["importation", "definition", "dependence"], help="The type of capture to parse")
    args = parser.parse_args()

    file = load_file(args.language, args.extension)
    query = load_query(args.language, args.capture)

    language = get_language(args.language)
    parser = get_parser(args.language)

    tree = parser.parse(file.encode())
    print("="*10 + "AST" + "="*10)
    print_node(tree.root_node, file)
    
    if args.capture == "importation":
        parse_importation(tree, query, language, args.language)
    # elif args.capture == "definition":
    #     parse_definition(tree, query, language, args.language)
    # elif args.capture == "dependence":
    #     parse_dependence(tree, query, language, args.language)

