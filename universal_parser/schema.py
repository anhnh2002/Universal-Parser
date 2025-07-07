from pydantic import BaseModel, model_validator

class Node(BaseModel):
    id: str
    implementation_file: str
    start_line: int | str
    end_line: int | str
    type: str
    code_snippet: str = ""

    @classmethod
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