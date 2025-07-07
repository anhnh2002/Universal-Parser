import json
import os
from typing import Dict, List, Optional
from pathlib import Path
from neo4j import GraphDatabase
from neo4j.exceptions import ServiceUnavailable, AuthError
import config
from logger import logger
from schema import Node, Edge


class Neo4jService:
    """Service class for Neo4j database operations"""
    
    def __init__(self):
        """Initialize Neo4j connection"""
        self.driver = None
        self.connect()
    
    def connect(self):
        """Establish connection to Neo4j database"""
        try:
            if not all([config.NEO4J_URI, config.NEO4J_USERNAME, config.NEO4J_PASSWORD]):
                raise ValueError("Neo4j connection parameters not properly configured. Please check your environment variables.")
            
            self.driver = GraphDatabase.driver(
                config.NEO4J_URI,
                auth=(config.NEO4J_USERNAME, config.NEO4J_PASSWORD)
            )
            
            # Test the connection
            with self.driver.session(database=config.NEO4J_DATABASE) as session:
                session.run("RETURN 1")
            
            logger.info(f"Successfully connected to Neo4j at {config.NEO4J_URI}")
            
        except (ServiceUnavailable, AuthError) as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error connecting to Neo4j: {e}")
            raise
    
    def close(self):
        """Close Neo4j connection"""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")
    
    def clear_repository_data(self, repo_name: str):
        """Clear existing data for a specific repository"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            # Delete relationships first to avoid constraint issues
            session.run("""
                MATCH (n)-[r]-(m) 
                WHERE n.repository = $repo_name OR m.repository = $repo_name
                DELETE r
            """, repo_name=repo_name)
            
            # Then delete nodes
            session.run("""
                MATCH (n) 
                WHERE n.repository = $repo_name
                DELETE n
            """, repo_name=repo_name)
            
            logger.info(f"Cleared existing data for repository: {repo_name}")
    
    def create_constraints(self):
        """Create necessary constraints and indexes"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            try:
                # Create constraint for unique node IDs within a repository
                session.run("""
                    CREATE CONSTRAINT unique_node_id IF NOT EXISTS
                    FOR (n:CodeNode) REQUIRE (n.repository, n.node_id) IS UNIQUE
                """)
                
                # Create indexes for performance
                session.run("""
                    CREATE INDEX node_type_index IF NOT EXISTS
                    FOR (n:CodeNode) ON (n.type)
                """)
                
                session.run("""
                    CREATE INDEX repository_index IF NOT EXISTS
                    FOR (n:CodeNode) ON (n.repository)
                """)
                
                session.run("""
                    CREATE INDEX file_index IF NOT EXISTS
                    FOR (n:CodeNode) ON (n.implementation_file)
                """)
                
                logger.info("Created Neo4j constraints and indexes")
                
            except Exception as e:
                logger.warning(f"Some constraints/indexes might already exist: {e}")
    
    def load_aggregated_results(self, file_path: str, repo_name: str, clear_existing: bool = True):
        """
        Load aggregated results from JSON file into Neo4j
        
        Args:
            file_path: Path to the aggregated_results.json file
            repo_name: Name of the repository
            clear_existing: Whether to clear existing data for this repository
        """
        logger.info(f"Loading aggregated results from {file_path} for repository {repo_name}")
        
        # Validate file exists
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Aggregated results file not found: {file_path}")
        
        # Load JSON data
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in aggregated results file: {e}")
        
        # Validate JSON structure
        if not all(key in data for key in ['nodes', 'edges', 'repository']):
            raise ValueError("Aggregated results file missing required keys: 'nodes', 'edges', 'repository'")
        
        # Create constraints and indexes
        self.create_constraints()
        
        # Clear existing data if requested
        if clear_existing:
            self.clear_repository_data(repo_name)
        
        # Load nodes and edges
        nodes_created = self._create_nodes(data['nodes'], repo_name)
        edges_created = self._create_relationships(data['edges'], repo_name)
        
        # Store repository metadata
        self._create_repository_metadata(data['repository'], repo_name)
        
        logger.info(f"Successfully loaded {nodes_created} nodes and {edges_created} relationships for repository {repo_name}")
        
        return {
            "nodes_created": nodes_created,
            "edges_created": edges_created,
            "repository": repo_name
        }
    
    def _create_nodes(self, nodes_data: List[Dict], repo_name: str) -> int:
        """Create nodes in Neo4j"""
        logger.info(f"Creating {len(nodes_data)} nodes for repository {repo_name}")
        
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            # Use UNWIND for batch processing
            query = """
                UNWIND $nodes AS node_data
                MERGE (n:CodeNode {repository: $repo_name, node_id: node_data.id})
                SET n.implementation_file = node_data.implementation_file,
                    n.start_line = node_data.start_line,
                    n.end_line = node_data.end_line,
                    n.type = node_data.type,
                    n.name = split(node_data.id, '.')[-1],
                    n.created_at = datetime(),
                    n.updated_at = datetime()
                RETURN count(n) as nodes_created
            """
            
            result = session.run(query, nodes=nodes_data, repo_name=repo_name)
            nodes_created = result.single()["nodes_created"]
            
            logger.debug(f"Created {nodes_created} nodes")
            return nodes_created
    
    def _create_relationships(self, edges_data: List[Dict], repo_name: str) -> int:
        """Create relationships in Neo4j"""
        logger.info(f"Creating {len(edges_data)} relationships for repository {repo_name}")
        
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            query = """
                UNWIND $edges AS edge_data
                MATCH (subject:CodeNode {repository: $repo_name, node_id: edge_data.subject_id})
                MATCH (object:CodeNode {repository: $repo_name, node_id: edge_data.object_id})
                MERGE (subject)-[r:DEPENDS_ON {type: edge_data.type}]->(object)
                SET r.subject_file = edge_data.subject_implementation_file,
                    r.object_file = edge_data.object_implementation_file,
                    r.created_at = datetime(),
                    r.updated_at = datetime()
                RETURN count(r) as edges_created
            """
            
            result = session.run(query, edges=edges_data, repo_name=repo_name)
            edges_created = result.single()["edges_created"]
            
            logger.debug(f"Created {edges_created} relationships")
            return edges_created
    
    def _create_repository_metadata(self, repo_data: Dict, repo_name: str):
        """Create repository metadata node"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            query = """
                MERGE (r:Repository {name: $repo_name})
                SET r.path = $repo_path,
                    r.total_files_processed = $total_files_processed,
                    r.total_files_failed = $total_files_failed,
                    r.failed_files = $failed_files,
                    r.created_at = datetime(),
                    r.updated_at = datetime()
                RETURN r
            """
            
            session.run(
                query,
                repo_name=repo_name,
                repo_path=repo_data.get('path', ''),
                total_files_processed=repo_data.get('total_files_processed', 0),
                total_files_failed=repo_data.get('total_files_failed', 0),
                failed_files=repo_data.get('failed_files', [])
            )
            
            logger.debug(f"Created repository metadata for {repo_name}")
    
    def get_repository_stats(self, repo_name: str) -> Dict:
        """Get statistics for a repository"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            query = """
                MATCH (n:CodeNode {repository: $repo_name})
                OPTIONAL MATCH (n)-[r:RELATES_TO]->()
                RETURN 
                    count(DISTINCT n) as total_nodes,
                    count(r) as total_relationships,
                    collect(DISTINCT n.type) as node_types,
                    collect(DISTINCT r.type) as relationship_types
            """
            
            result = session.run(query, repo_name=repo_name)
            record = result.single()
            
            if record:
                return {
                    "repository": repo_name,
                    "total_nodes": record["total_nodes"],
                    "total_relationships": record["total_relationships"],
                    "node_types": record["node_types"],
                    "relationship_types": record["relationship_types"]
                }
            else:
                return {"repository": repo_name, "total_nodes": 0, "total_relationships": 0}
    
    def query_nodes_by_type(self, repo_name: str, node_type: str) -> List[Dict]:
        """Query nodes by type"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            query = """
                MATCH (n:CodeNode {repository: $repo_name, type: $node_type})
                RETURN n.node_id as id, n.implementation_file as file, 
                       n.start_line as start_line, n.end_line as end_line
                ORDER BY n.implementation_file, n.start_line
            """
            
            result = session.run(query, repo_name=repo_name, node_type=node_type)
            return [record.data() for record in result]
    
    def query_node_relationships(self, repo_name: str, node_id: str) -> Dict:
        """Get all relationships for a specific node"""
        with self.driver.session(database=config.NEO4J_DATABASE) as session:
            query = """
                MATCH (n:CodeNode {repository: $repo_name, node_id: $node_id})
                OPTIONAL MATCH (n)-[r:RELATES_TO]->(target)
                OPTIONAL MATCH (source)-[r2:RELATES_TO]->(n)
                RETURN 
                    n,
                    collect(DISTINCT {target: target.node_id, type: r.type, file: target.implementation_file}) as outgoing,
                    collect(DISTINCT {source: source.node_id, type: r2.type, file: source.implementation_file}) as incoming
            """
            
            result = session.run(query, repo_name=repo_name, node_id=node_id)
            record = result.single()
            
            if record:
                node = record["n"]
                return {
                    "node": {
                        "id": node["node_id"],
                        "type": node["type"],
                        "file": node["implementation_file"],
                        "start_line": node["start_line"],
                        "end_line": node["end_line"]
                    },
                    "outgoing_relationships": [rel for rel in record["outgoing"] if rel["target"]],
                    "incoming_relationships": [rel for rel in record["incoming"] if rel["source"]]
                }
            else:
                return None


def load_aggregated_results_to_neo4j(file_path: str, repo_name: str, clear_existing: bool = True) -> Dict:
    """
    Convenience function to load aggregated results into Neo4j
    
    Args:
        file_path: Path to the aggregated_results.json file
        repo_name: Name of the repository
        clear_existing: Whether to clear existing data for this repository
    
    Returns:
        Dict containing statistics about the loaded data
    """
    service = Neo4jService()
    try:
        result = service.load_aggregated_results(file_path, repo_name, clear_existing)
        stats = service.get_repository_stats(repo_name)
        result.update(stats)
        return result
    finally:
        service.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Load aggregated results into Neo4j")
    parser.add_argument("--file-path", required=True, help="Path to aggregated_results.json file")
    parser.add_argument("--repo-name", required=True, help="Repository name")
    parser.add_argument("--no-clear", action="store_true", help="Don't clear existing data")
    
    args = parser.parse_args()
    
    try:
        result = load_aggregated_results_to_neo4j(
            args.file_path, 
            args.repo_name, 
            clear_existing=not args.no_clear
        )
        print(f"Successfully loaded data: {result}")
    except Exception as e:
        logger.error(f"Failed to load data: {e}")
        exit(1) 