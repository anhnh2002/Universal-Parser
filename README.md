# universal Parser

A powerful tool for extracting structured information from codebases using AST parsing and LLM analysis. universal Parser analyzes repositories to identify code structure, dependencies, and relationships between different components.

## Features

- 🔍 **Multi-language support** - Support all of PLs
- 🏗️ **AST-based parsing** - Uses Tree-sitter for accurate syntax analysiste
- 🤖 **LLM-powered analysis** - Leverages large language models for semantic understanding
- 📈 **Incremental updates** - Update only changed files for faster processing
- 🔎 **Analysis tools** - File summaries and definition analysis capabilities

## Installation

### From Source

```bash
git clone https://github.com/yourusername/universal-parser.git
cd universal-parser
pip install -e .
```

or 
```bash
pip install git+https://github.com/anhnh2002/Universal-Parser.git
```

## Quick Start

### 1. Set up LLM service

universal Parser requires a LLM:

```bash
export LLM_MODEL="<llm_model>"
export LLM_BASE_URL="<llm_base_url>"
export LLM_API_KEY="<llm_api_key>"
```

Or create a `.env` file:

```.env
LLM_MODEL=llm_model
LLM_BASE_URL=llm_base_url
LLM_API_KEY=llm_api_key
```

### 2. Parse a repository

```bash
# Full repository parsing
universal-parse parse --repo-dir /path/to/your/repository --output-dir ./output

# Incremental update (only changed files)
universal-parse update --repo-dir /path/to/your/repository --output-dir ./output
```

## CLI Usage

universal Parser provides several commands for different use cases:

### Full Repository Parsing

Parse the entire repository from scratch:

```bash
universal-parse parse --repo-dir /path/to/repo --output-dir ./output
```

### Incremental Updates

Update parsing results by only processing files that have changed:

```bash
universal-parse update --repo-dir /path/to/repo --output-dir ./output
```

### File Summary Analysis

Generate a summary of a file showing only first lines of nodes with elide messages:

```bash
universal-parse file-summary \
  --aggregated-results results.json \
  --file-path "src/main.py"
```

### Definition Analysis

Get detailed definition analysis for a specific node:

```bash
universal-parse get-definition \
  --aggregated-results results.json \
  --file-path "/absolute/path/to/src/main.py" \
  --node-name "SearchProvider"
```

### Advanced CLI Options

```bash
universal-parse parse \
  --repo-dir /path/to/repo \
  --output-dir ./custom-output \
  --max-concurrent 10 \
  --model gpt-4o \
  --log-level DEBUG
```

### CLI Help

```bash
# Get general help
universal-parse --help

# Get help for specific commands
universal-parse parse --help
universal-parse update --help
universal-parse file-summary --help
universal-parse get-definition --help
```

## Python SDK Usage

You can also use universal Parser programmatically in your Python applications:

### Basic Repository Parsing

```python
import asyncio
from universal_parser import parse_repository_main
from universal_parser.core import update_config

# Configure LLM (optional, uses environment variables by default)
update_config(
    model="gpt-4o-mini",
    base_url="https://api.openai.com/v1",
    api_key="your-api-key"
)

async def main():
    # Parse repository
    output_file = await parse_repository_main(
        repo_dir="/path/to/repository",
        output_dir="./output",
        max_concurrent=5
    )
    print(f"Results saved to: {output_file}")

# Run the parser
asyncio.run(main())
```

### Using RepositoryParser Class

```python
import asyncio
from universal_parser.parsing import RepositoryParser

async def parse_repo():
    # Create parser instance
    parser = RepositoryParser(
        repo_dir="/path/to/repository",
        output_dir="./output"
    )
    
    # Discover files
    supported_files = parser.discover_files()
    print(f"Found {len(supported_files)} supported files")
    
    # Parse repository
    output_file = await parser.parse_repository(max_concurrent=10)
    print(f"Parsing completed: {output_file}")

asyncio.run(parse_repo())
```

### Incremental Updates

```python
import asyncio
from universal_parser import parse_repository_incremental_main

async def incremental_update():
    # Only process changed files
    output_file = await parse_repository_incremental_main(
        repo_dir="/path/to/repository",
        output_dir="./output",
        max_concurrent=5
    )
    print(f"Incremental update completed: {output_file}")

asyncio.run(incremental_update())
```

### File Summary Analysis

```python
from universal_parser.analyzing import FileSummaryAnalyzer

# Create analyzer from aggregated results
analyzer = FileSummaryAnalyzer.from_aggregated_results("results.json")

# Analyze a specific file
summary = analyzer.analyze_file_summary("src/main.py")

# Format and display the summary
formatted_summary = analyzer.format_file_summary(summary, k=5)
print(formatted_summary)
```

### Definition Analysis

```python
from universal_parser.analyzing import DefinitionAnalyzer

# Create analyzer from aggregated results
analyzer = DefinitionAnalyzer.from_aggregated_results("results.json")

# Analyze a specific node
analysis = analyzer.get_definition_analysis(
    absolute_file_path="/absolute/path/to/src/main.py",
    node_name="SearchProvider"
)

# Format and display the analysis
formatted_analysis = analyzer.format_definition_analysis(analysis)
print(formatted_analysis)

# Access analysis data
print(f"Dependents: {analysis.get_total_dependents()}")
print(f"Dependencies: {analysis.get_total_dependencies()}")
```

### Custom Configuration

```python
from universal_parser.core.config import update_config, LLM_MODEL, LLM_BASE_URL
from universal_parser.utils.logger import set_log_level

# Update configuration
update_config(
    model="gpt-4o",
    base_url="https://custom-api.example.com/v1",
    api_key="custom-key"
)

# Set logging level
set_log_level("DEBUG")

# Access current configuration
print(f"Current model: {LLM_MODEL}")
print(f"Current base URL: {LLM_BASE_URL}")
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | API key (required) | - |
| `LLM_BASE_URL` | API base URL | - |
| `LLM_MODEL` | Model name | - |

## Output Format

The parser generates a JSON file with the following structure:

```json
{
  "repository": {
    "name": "whisper.cpp-gpt-4o-mini",
    "path": "/path/to/repo",
    "total_files_processed": 42,
    "total_files_failed": 0,
    "failed_files": []
  },
  "nodes": [
    {
      "id": "src.main.WhisperModel",
      "implementation_file": "src/main.cpp",
      "start_line": 15,
      "end_line": 145,
      "type": "class"
    }
  ],
  "edges": [
    {
      "subject_id": "src.main.WhisperModel",
      "subject_implementation_file": "src/main.cpp",
      "object_id": "src.utils.Logger",
      "object_implementation_file": "src/utils.cpp",
      "type": "dependency"
    }
  ],
  "statistics": {
    "total_nodes": 156,
    "total_edges": 298,
    "nodes_by_type": {
      "class": 23,
      "function": 87,
      "variable": 46
    },
    "edges_by_type": {
      "dependency": 178,
      "inheritance": 12,
      "composition": 108
    },
    "files_by_language": {
      "cpp": 15,
      "python": 8,
      "javascript": 19
    }
  }
}
```

