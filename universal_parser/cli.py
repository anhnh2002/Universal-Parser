"""
Command-line interface for universal Parser.

This module provides the main CLI entry point for parsing repositories.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from .parse_repository import parse_repository_main, parse_repository_incremental_main
from .config import update_config, LLM_API_KEY
from .logger import logger, set_log_level


def validate_repo_dir(repo_dir: str) -> Path:
    """Validate that the repository path exists and is a directory."""
    path = Path(repo_dir).resolve()
    if not path.exists():
        logger.error(f"Repository path does not exist: {path}")
        sys.exit(1)
    
    if not path.is_dir():
        logger.error(f"Repository path is not a directory: {path}")
        sys.exit(1)
    
    return path


def check_api_key() -> None:
    """Check if LLM API key is configured."""
    if not LLM_API_KEY:
        logger.error("LLM_API_KEY is not set. Please set it in environment variables or .env file")
        logger.error("Example: export LLM_API_KEY='your-api-key-here'")
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create and configure the argument parser."""
    parser = argparse.ArgumentParser(
        description="Parse repositories to extract code structure and relationships",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full repository parsing
  universal-parse parse --repo-dir /path/to/repo

  # Incremental update (only changed files)
  universal-parse update --repo-dir /path/to/repo

  # With custom settings
  universal-parse parse --repo-dir /path/to/repo --repo-name my-project --max-concurrent 10

  # Incremental update with content hash verification
  universal-parse update --repo-dir /path/to/repo --use-content-hash

  # Force re-parsing specific files/patterns
  universal-parse update --repo-dir /path/to/repo --force-reparse "src/*.py" "config/*"

Environment Variables:
  LLM_API_KEY       OpenAI API key (required)
  LLM_BASE_URL      API base URL (default: https://api.openai.com/v1)
  LLM_MODEL         Model name (default: gpt-4o-mini)
  OUTPUT_DIR        Output directory (default: ./data/outputs)

For more information, visit: https://github.com/yourusername/universal-parser
        """
    )
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Common arguments for both parsers
    def add_common_arguments(subparser):
        # Required arguments
        subparser.add_argument(
            "--repo-dir", 
            required=True, 
            type=str,
            help="The absolute directory to the repository to parse"
        )
        
        # Optional arguments
        subparser.add_argument(
            "--repo-name", 
            type=str, 
            default=None,
            help="Name for the repository (defaults to directory name)"
        )
        
        subparser.add_argument(
            "--max-concurrent", 
            type=int, 
            default=5,
            help="Maximum number of files to process concurrently (default: 5)"
        )
        
        # LLM configuration
        subparser.add_argument(
            "--model", 
            type=str, 
            default=None,
            help="LLM model to use (e.g., gpt-4o, gpt-4o-mini)"
        )

        subparser.add_argument(
            "--base-url", 
            type=str, 
            default=None,
            help="Custom API base URL"
        )

        subparser.add_argument(
            "--api-key", 
            type=str, 
            default=None,
            help="Custom API key"
        )
        
        subparser.add_argument(
            "--output-dir", 
            type=str, 
            default=None,
            help="Custom output directory"
        )

        # Utility arguments
        subparser.add_argument(
            "--log-level", 
            choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
            default="INFO",
            help="Set the logging level (default: INFO)"
        )
    
    # Full parse subcommand
    parse_parser = subparsers.add_parser(
        'parse', 
        help='Parse entire repository from scratch',
        description='Parse the entire repository, processing all supported files'
    )
    add_common_arguments(parse_parser)
    
    # Incremental update subcommand
    update_parser = subparsers.add_parser(
        'update', 
        help='Incrementally update parsed results for changed files',
        description='Update parsing results by only processing files that have changed since the last parse'
    )
    add_common_arguments(update_parser)
    
    # Additional arguments specific to incremental updates
    update_parser.add_argument(
        "--use-content-hash",
        action="store_true",
        help="Use content hashing for more thorough change detection (slower but more accurate)"
    )
    
    update_parser.add_argument(
        "--force-reparse",
        type=str,
        nargs="*",
        help="Force re-parsing of files matching these patterns (e.g., 'src/*.py' 'config/*')"
    )
    
    # Legacy support: if no subcommand is provided, default to parse
    parser.set_defaults(command='parse')
    
    return parser


async def run_parser(args: argparse.Namespace) -> None:
    """Run the repository parser with the given arguments."""
    try:
        # Update configuration if needed
        config_updates = {}
        if args.model:
            config_updates["model"] = args.model
        
        if args.base_url:
            config_updates["base_url"] = args.base_url
        
        if args.api_key:
            config_updates["api_key"] = args.api_key

        # Update output directory if specified
        if args.output_dir:
            config_updates["output_dir"] = args.output_dir
        
        if config_updates:
            update_config(**config_updates)
        
        # Determine which command to run
        if args.command == 'update':
            # Run incremental update
            output_file = await parse_repository_incremental_main(
                repo_dir=str(args.repo_dir),
                repo_name=args.repo_name,
                max_concurrent=args.max_concurrent,
                use_content_hash=getattr(args, 'use_content_hash', False),
                force_reparse=getattr(args, 'force_reparse', None)
            )
            
            if output_file:
                logger.info(f"✅ Incremental repository update completed successfully!")
                logger.info(f"📁 Results saved to: {output_file}")
            else:
                logger.warning("⚠️  Incremental update completed but no output file was generated")
        else:
            # Run full parse (default)
            output_file = await parse_repository_main(
                repo_dir=str(args.repo_dir),
                repo_name=args.repo_name,
                max_concurrent=args.max_concurrent
            )
            
            if output_file:
                logger.info(f"✅ Repository parsing completed successfully!")
                logger.info(f"📁 Results saved to: {output_file}")
            else:
                logger.warning("⚠️  Repository parsing completed but no output file was generated")
            
    except KeyboardInterrupt:
        logger.info("🛑 Parser interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"❌ Parser failed with error: {e}")
        logger.debug("Full traceback:", exc_info=True)
        sys.exit(1)


def main() -> None:
    """Main entry point for the CLI."""
    parser = create_parser()
    
    # Handle legacy usage (no subcommand) by checking if first arg looks like --repo-dir
    if len(sys.argv) > 1 and not sys.argv[1] in ['parse', 'update', '-h', '--help']:
        # Legacy usage - insert 'parse' as the default command
        sys.argv.insert(1, 'parse')
    
    args = parser.parse_args()
    
    # Set logging level
    set_log_level(args.log_level)
    
    # Validate inputs
    args.repo_dir = validate_repo_dir(args.repo_dir)
    check_api_key()
    
    # Print startup info
    command_name = "Incremental Update" if args.command == 'update' else "Full Parse"
    logger.info(f"🚀 Starting Universal Parser - {command_name}")
    logger.info(f"📂 Repository: {args.repo_dir}")
    if args.repo_name:
        logger.info(f"🏷️  Name: {args.repo_name}")
    logger.info(f"⚡ Concurrency: {args.max_concurrent}")
    
    if args.command == 'update':
        if getattr(args, 'use_content_hash', False):
            logger.info("🔍 Using content hash for change detection")
        if getattr(args, 'force_reparse', None):
            logger.info(f"🔄 Force re-parsing patterns: {args.force_reparse}")
    
    # Run the parser
    try:
        asyncio.run(run_parser(args))
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 