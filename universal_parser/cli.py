"""
Command-line interface for DeepWiki Parser.

This module provides the main CLI entry point for parsing repositories.
"""

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

from .parse_repository import parse_repository_main
from .config import update_config, LLM_API_KEY
from .logger import logger, set_log_level


def validate_repo_path(repo_path: str) -> Path:
    """Validate that the repository path exists and is a directory."""
    path = Path(repo_path).resolve()
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
  # Basic usage
  deepwiki-parse --repo-path /path/to/repo

  # With custom settings
  deepwiki-parse --repo-path /path/to/repo --repo-name my-project --max-concurrent 10

  # With custom LLM settings
  deepwiki-parse --repo-path /path/to/repo --model gpt-4o --max-tokens 8192

Environment Variables:
  LLM_API_KEY       OpenAI API key (required)
  LLM_BASE_URL      API base URL (default: https://api.openai.com/v1)
  LLM_MODEL         Model name (default: gpt-4o-mini)
  OUTPUT_DIR        Output directory (default: ./data/outputs)

For more information, visit: https://github.com/yourusername/deepwiki-parser
        """
    )
    
    # Required arguments
    parser.add_argument(
        "--repo-path", 
        required=True, 
        type=str,
        help="The absolute path to the repository to parse"
    )
    
    # Optional arguments
    parser.add_argument(
        "--repo-name", 
        type=str, 
        default=None,
        help="Name for the repository (defaults to directory name)"
    )
    
    parser.add_argument(
        "--max-concurrent", 
        type=int, 
        default=5,
        help="Maximum number of files to process concurrently (default: 5)"
    )
    
    # LLM configuration
    parser.add_argument(
        "--model", 
        type=str, 
        default=None,
        help="LLM model to use (e.g., gpt-4o, gpt-4o-mini)"
    )

    parser.add_argument(
        "--base-url", 
        type=str, 
        default=None,
        help="Custom API base URL"
    )

    parser.add_argument(
        "--api-key", 
        type=str, 
        default=None,
        help="Custom API key"
    )
    
    parser.add_argument(
        "--output-dir", 
        type=str, 
        default=None,
        help="Custom output directory"
    )

    # Utility arguments
    parser.add_argument(
        "--log-level", 
        choices=["DEBUG", "INFO", "WARNING", "ERROR"], 
        default="INFO",
        help="Set the logging level (default: INFO)"
    )
    
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
        
        # Run the parser
        output_file = await parse_repository_main(
            repo_path=str(args.repo_path),
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
    args = parser.parse_args()
    
    # Set logging level
    set_log_level(args.log_level)
    
    # Validate inputs
    args.repo_path = validate_repo_path(args.repo_path)
    check_api_key()
    
    # Print startup info
    logger.info("🚀 Starting Universal Parser")
    logger.info(f"📂 Repository: {args.repo_path}")
    if args.repo_name:
        logger.info(f"🏷️  Name: {args.repo_name}")
    logger.info(f"⚡ Concurrency: {args.max_concurrent}")
    
    # Run the parser
    try:
        asyncio.run(run_parser(args))
    except Exception as e:
        logger.error(f"❌ Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main() 