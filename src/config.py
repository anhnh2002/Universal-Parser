import os
import json
from pathlib import Path
import argparse
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
# ANTHROPIC_MODEL = "claude-3-5-haiku-20241022"

FIREWORKS_API_KEY = os.getenv("FIREWORKS_API_KEY")
# FIREWORKS_MODEL = "accounts/fireworks/models/deepseek-r1-0528"
# FIREWORKS_MODEL = "accounts/fireworks/models/deepseek-r1-basic"
# FIREWORKS_MODEL = "accounts/fireworks/models/deepseek-v3-0324"
FIREWORKS_MODEL = "accounts/fireworks/models/qwen3-235b-a22b"
FIREWORKS_EMBEDDING_MODEL = "nomic-ai/nomic-embed-text-v1.5"

# langfuse
LANGFUSE_PUBLIC_KEY = os.getenv("LANGFUSE_PUBLIC_KEY")
LANGFUSE_SECRET_KEY = os.getenv("LANGFUSE_SECRET_KEY")
LANGFUSE_HOST = "https://cloud.langfuse.com"

os.environ["LANGFUSE_PUBLIC_KEY"] = LANGFUSE_PUBLIC_KEY
os.environ["LANGFUSE_SECRET_KEY"] = LANGFUSE_SECRET_KEY
os.environ["LANGFUSE_HOST"] = LANGFUSE_HOST

# output dir
OUTPUT_DIR = "./data/outputs"


# neo4j
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE")


# Load config from config.json
with open("config.json", "r") as file:
    CONFIG = json.load(file)
PROVIDER = CONFIG["provider"]
MODEL = CONFIG["model"]
MAX_TOKENS = CONFIG["max_tokens"]
TEMPERATURE = CONFIG["temperature"]
THINKING = {"type": "enabled", "budget_tokens": 10000} if CONFIG["thinking"] else {"type": "disabled"}

# Set config variables
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", type=str, default=PROVIDER)
    parser.add_argument("--model", type=str, default=MODEL)
    parser.add_argument("--max_tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--thinking", type=bool, default=THINKING)

    args = parser.parse_args()

    if args.provider:
        CONFIG["provider"] = args.provider
    if args.model:
        CONFIG["model"] = args.model
    if args.max_tokens:
        CONFIG["max_tokens"] = args.max_tokens
    if args.temperature:
        CONFIG["temperature"] = args.temperature
    if args.thinking:
        CONFIG["thinking"] = args.thinking

    # Update config variables by saving to config.json
    with open("config.json", "w") as file:
        json.dump(CONFIG, file, indent=4)

