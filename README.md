# universal Parser

A powerful tool for extracting structured information from codebases using AST parsing and LLM analysis. universal Parser analyzes repositories to identify code structure, dependencies, and relationships between different components.

## Features

- 🔍 **Multi-language support** - Python, JavaScript, TypeScript, Java, C/C++, Rust, Go, and more
- 🏗️ **AST-based parsing** - Uses Tree-sitter for accurate syntax analysis
- 🤖 **LLM-powered analysis** - Leverages large language models for semantic understanding
- ⚡ **Concurrent processing** - Processes multiple files simultaneously for speed
- 📊 **Structured output** - Generates JSON with nodes, edges, and statistics
- 🎯 **Smart filtering** - Configurable inclusion/exclusion patterns
- 🔧 **Flexible configuration** - Environment variables and CLI options

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

### 1. Set up your API key

universal Parser requires an OpenAI API key:

```bash
export LLM_API_KEY="your-openai-api-key-here"
```

Or create a `.env` file:

```bash
echo "LLM_API_KEY=your-openai-api-key-here" > .env
```

### 2. Parse a repository

```bash
# Basic usage
universal-parse --repo-dir /path/to/your/repository

# With custom settings
universal-parse --repo-dir /path/to/repo --repo-name my-project --max-concurrent 10
```

## Usage Examples

### Basic Repository Analysis

```bash
universal-parse --repo-dir /Users/anhnh/Documents/vscode/whisper.cpp --repo-name whisper.cpp
```

### Advanced Configuration

```bash
universal-parse \
  --repo-dir /path/to/repo \
  --repo-name my-project \
  --max-concurrent 10 \
  --model gpt-4o \
  --output-dir ./custom-output \
  --log-level DEBUG
```

### Using Different Models

```bash
# Use GPT-4
universal-parse --repo-dir /path/to/repo --model gpt-4o

# Use GPT-4o-mini (faster, cheaper)
universal-parse --repo-dir /path/to/repo --model gpt-4o-mini
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_API_KEY` | OpenAI API key (required) | - |
| `LLM_BASE_URL` | API base URL | `https://api.openai.com/v1` |
| `LLM_MODEL` | Model name | `gpt-4o-mini` |
| `OUTPUT_DIR` | Output directory | `./data/outputs` |

### CLI Options

```bash
universal-parse --help
```

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

