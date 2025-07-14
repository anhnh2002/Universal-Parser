#!/usr/bin/env python3
"""
Utility script to load aggregated results into Neo4j database.

This script provides a simple interface to load the JSON results from
repository parsing into a Neo4j graph database for visualization and analysis.

Usage:
    python load_to_neo4j.py --file path/to/aggregated_results.json --repo my-repo
    python load_to_neo4j.py --file outputs/titan-sight/aggregated_results.json --repo titan-sight
"""

import argparse
import sys
from pathlib import Path
from typing import Dict

from neo4j_service import load_aggregated_results_to_neo4j, Neo4jService
from logger import logger
import config



def print_stats(stats: Dict):
    """Print formatted statistics"""
    print("\n" + "="*50)
    print("LOADING STATISTICS")
    print("="*50)
    print(f"Repository: {stats['repository']}")
    print(f"Nodes created: {stats['nodes_created']}")
    print(f"Relationships created: {stats['edges_created']}")
    print(f"Total nodes in DB: {stats['total_nodes']}")
    print(f"Total relationships in DB: {stats['total_relationships']}")
    
    if stats.get('node_types'):
        print(f"\nNode types ({len(stats['node_types'])}):")
        for node_type in sorted(stats['node_types']):
            print(f"  - {node_type}")
    
    if stats.get('relationship_types'):
        print(f"\nRelationship types ({len(stats['relationship_types'])}):")
        for rel_type in sorted(stats['relationship_types']):
            print(f"  - {rel_type}")
    
    print("="*50)


def check_file_exists(file_path: str) -> bool:
    """Check if the aggregated results file exists"""
    path = Path(file_path)
    if not path.exists():
        logger.debug(f"File does not exist: {file_path}")
        return False
    
    if not path.is_file():
        logger.debug(f"Path is not a file: {file_path}")
        return False
    
    if path.suffix.lower() != '.json':
        logger.warning(f"File does not have .json extension: {file_path}")
    
    return True


def main():
    """Main function"""
    parser = argparse.ArgumentParser(
        description="Load aggregated results into Neo4j database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python load_to_neo4j.py --file outputs/my-repo/aggregated_results.json --repo my-repo
  python load_to_neo4j.py --file outputs/titan-sight/aggregated_results.json --repo titan-sight --no-clear
  python load_to_neo4j.py --file data/results.json --repo test-project --stats-only
        """
    )
    
    parser.add_argument(
        "--file", 
        required=True, 
        help="Path to the aggregated_results.json file"
    )
    
    parser.add_argument(
        "--repo", 
        required=True, 
        help="Repository name (will be used as identifier in Neo4j)"
    )
    
    parser.add_argument(
        "--no-clear", 
        action="store_true", 
        help="Don't clear existing data for this repository (default: clear existing data)"
    )
    
    parser.add_argument(
        "--stats-only",
        action="store_true",
        help="Only display statistics for existing repository data (don't load new data)"
    )
    
    parser.add_argument(
        "--test-connection",
        action="store_true",
        help="Test Neo4j connection and exit"
    )
    
    args = parser.parse_args()
    
    # Test connection if requested
    if args.test_connection:
        try:
            service = Neo4jService()
            service.close()
            print("✅ Neo4j connection successful!")
            sys.exit(0)
        except Exception as e:
            logger.debug(f"❌ Neo4j connection failed: {e}")
            sys.exit(1)
    
    # Validate file exists (unless stats-only)
    if not args.stats_only:
        if not check_file_exists(args.file):
            sys.exit(1)
    
    try:
        if args.stats_only:
            # Just get stats for existing repository
            service = Neo4jService()
            try:
                stats = service.get_repository_stats(args.repo)
                if stats['total_nodes'] == 0:
                    logger.debug(f"No data found for repository: {args.repo}")
                else:
                    print_stats(stats)
            finally:
                service.close()
        else:
            # Load the data
            logger.debug(f"Loading aggregated results from: {args.file}")
            logger.debug(f"Repository name: {args.repo}")
            logger.debug(f"Clear existing data: {not args.no_clear}")
            
            result = load_aggregated_results_to_neo4j(
                args.file,
                args.repo,
                clear_existing=not args.no_clear
            )
            
            print_stats(result)
            
            # Provide Neo4j Browser access information
            print(f"\n🔗 Access your data in Neo4j Browser:")
            print(f"   URL: {config.NEO4J_URI.replace('bolt://', 'http://').replace(':7687', ':7474')}")
            print(f"   Database: {config.NEO4J_DATABASE or 'neo4j'}")
            print(f"\n📊 Example Cypher queries:")
            print(f"   // View all nodes for this repository")
            print(f"   MATCH (n:CodeNode {{repository: '{args.repo}'}}) RETURN n LIMIT 25")
            print(f"   ")
            print(f"   // View node types and counts")
            print(f"   MATCH (n:CodeNode {{repository: '{args.repo}'}}) RETURN n.type, count(*) ORDER BY count(*) DESC")
            print(f"   ")
            print(f"   // View relationships")
            print(f"   MATCH (a:CodeNode {{repository: '{args.repo}'}})-[r:RELATES_TO]->(b:CodeNode)")
            print(f"   RETURN a.name, r.type, b.name LIMIT 10")
    
    except KeyboardInterrupt:
        logger.debug("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        logger.debug(f"Failed to load data: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 