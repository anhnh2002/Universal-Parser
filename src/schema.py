from pydantic import BaseModel

class Node(BaseModel):
    name: str
    type: str
    children: list["Node"]

class Edge(BaseModel):
    source: str
    target: str
    type: str