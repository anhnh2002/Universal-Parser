import os
import json
from pathlib import Path
import argparse
from typing import Dict, Any
from dotenv import load_dotenv, find_dotenv

# Load environment variables
load_dotenv(find_dotenv())

# Environment variables with defaults
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")

# Default output directory
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./data/outputs")

def update_config(**kwargs) -> None:
    """Update configuration values."""
    global LLM_MODEL, LLM_BASE_URL, LLM_API_KEY, OUTPUT_DIR
    
    for key, value in kwargs.items():
        if value is not None:
            if key == "model":
                LLM_MODEL = value
            elif key == "base_url":
                LLM_BASE_URL = value
            elif key == "api_key":
                LLM_API_KEY = value
            elif key == "output_dir":
                OUTPUT_DIR = value