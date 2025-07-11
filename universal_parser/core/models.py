from pydantic import BaseModel, model_validator
from typing import Optional, Dict, Any, Union
import os

class Node(BaseModel):
    id: str
    implementation_file: str
    start_line: Union[int, str]
    end_line: Union[int, str]
    type: str
    code_snippet: str = ""
    absolute_path_to_implementation_file: str = ""
    file_level_id: str = ""

    @model_validator(mode='after')
    def validate_node(cls, data):
        data.id = data.id.replace("/", ".")
        parts = data.implementation_file.split(".")
        if len(parts) > 1:
            data.implementation_file = "/".join(parts[:-1]) + f".{parts[-1]}"

        if isinstance(data.start_line, str):
            data.start_line = int(data.start_line)
        if isinstance(data.end_line, str):
            data.end_line = int(data.end_line)

        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any], absolute_path_to_repo: Optional[str] = None):
        node = cls(**data)
        if absolute_path_to_repo:
            node.absolute_path_to_implementation_file = os.path.join(absolute_path_to_repo, node.implementation_file)
        node.file_level_id = node.implementation_file.split(".")[0]
        node.file_level_id = node.file_level_id.replace("/", ".")
        node.file_level_id = node.id.replace(node.file_level_id, "")
        if node.file_level_id.startswith("."):
            node.file_level_id = node.file_level_id[1:]
        return node
    
    def __repr__(self, include_absolute_path: bool = False):
        if include_absolute_path:
            return f"* Component: {self.file_level_id} in File: {self.absolute_path_to_implementation_file} (Line {self.start_line + 1} to {self.end_line + 1})"
        else:
            return f"# Component:{self.file_level_id} (Line {self.start_line + 1} to {self.end_line + 1})"
    
    def get_k_first_line(self, k: int = 1) -> str:
        """Get the first line of the code snippet."""
        lines = self.code_snippet.strip().split('\n')
        return lines[:k] if lines else ""

    

class Edge(BaseModel):
    subject_id: str
    subject_implementation_file: str
    object_id: str
    object_implementation_file: str
    type: str

    @classmethod
    @model_validator(mode='after')
    def validate_edge(cls, data):
        data.subject_id = data.subject_id.replace("/", ".")
        data.object_id = data.object_id.replace("/", ".")
        parts = data.subject_implementation_file.split(".")
        if len(parts) > 1:
            data.subject_implementation_file = "/".join(parts[:-1]) + f".{parts[-1]}"
        parts = data.object_implementation_file.split(".")
        if len(parts) > 1:
            data.object_implementation_file = "/".join(parts[:-1]) + f".{parts[-1]}"
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        return cls(**data)
    
    def __repr__(self):
        return f"Edge: {self.subject_id} --{self.type}--> {self.object_id}"