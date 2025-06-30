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

# ------------------------------------------------------------
# Language to Extension
# ------------------------------------------------------------

LANGUAGE_TO_EXTENSION = {
    "c": [
        ".c",
        ".cats",
        ".h",
        ".idc",
        ".w"
    ],
    "cpp": [
        ".cpp",
        ".c++",
        ".cc",
        ".cp",
        ".cxx",
        ".h",
        ".h++",
        ".hh",
        ".hpp",
        ".hxx",
        ".inc",
        ".inl",
        ".ipp",
        ".tcc",
        ".tpp"
    ],
    "csharp": [
        ".cs",
        ".cake",
        ".cshtml",
        ".csx"
    ],
    "css": [
        ".css",
    ],
    "cmake": [
        ".cmake",
        ".cmake.in"
    ],
    "cuda": [
        ".cu",
        ".cuh"
    ],
    "go": [
        ".go",
    ],
    "html": [
        ".html",
        ".htm",
        ".html.hl",
        ".inc",
        ".st",
        ".xht",
        ".xhtml"
    ],
    "java": [
        ".java",
    ],
    "javascript": [
        ".js",
        "._js",
        ".bones",
        ".es",
        ".es6",
        ".frag",
        ".gs",
        ".jake",
        ".jsb",
        ".jscad",
        ".jsfl",
        ".jsm",
        ".jss",
        ".njs",
        ".pac",
        ".sjs",
        ".ssjs",
        ".sublime-build",
        ".sublime-commands",
        ".sublime-completions",
        ".sublime-keymap",
        ".sublime-macro",
        ".sublime-menu",
        ".sublime-mousemap",
        ".sublime-project",
        ".sublime-settings",
        ".sublime-theme",
        ".sublime-workspace",
        ".sublime_metrics",
        ".sublime_session",
        ".xsjs",
        ".xsjslib"
    ],
    "kotlin": [
        ".kt",
        ".ktm",
        ".kts"
    ],
    "lua": [
        ".lua",
        ".fcgi",
        ".nse",
        ".pd_lua",
        ".rbxs",
        ".wlua"
    ],
    "php": [
        ".php",
        ".aw",
        ".ctp",
        ".fcgi",
        ".inc",
        ".php3",
        ".php4",
        ".php5",
        ".phps",
        ".phpt"
    ],
    "python": [
        ".py",
    ],
    "r": [
        ".r",
        ".rd",
        ".rsx"
    ],
    "ruby": [
        ".rb",
        ".builder",
        ".fcgi",
        ".gemspec",
        ".god",
        ".irbrc",
        ".jbuilder",
        ".mspec",
        ".pluginspec",
        ".podspec",
        ".rabl",
        ".rake",
        ".rbuild",
        ".rbw",
        ".rbx",
        ".ru",
        ".ruby",
        ".thor",
        ".watchr"
    ],
    "rust": [
        ".rs",
        ".rs.in",
    ]
}

EXTENSION_TO_LANGUAGE = {}
for language, extensions in LANGUAGE_TO_EXTENSION.items():
    for extension in extensions:
        EXTENSION_TO_LANGUAGE[extension] = language
