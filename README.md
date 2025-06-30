# Universal Code Graph Construction

A hybrid approach to building unified dependency graphs across multiple programming languages using tree-sitter parsing enhanced with LLM semantic understanding.

## Overview

This project solves the challenge of analyzing codebases that span multiple programming languages by creating a **universal representation** of code constructs and their relationships. Instead of maintaining separate parsers for each language, this system:

1. **Defines universal node and edge types** that can represent any programming language construct
2. **Uses tree-sitter for fast, accurate parsing** of individual files  
3. **Employs LLMs for semantic normalization** to map language-specific constructs to universal types
4. **Builds comprehensive cross-file dependency graphs** for entire repositories

## Key Features

- 🌍 **Universal Representation**: Single graph format for Python, C++, Java, and more
- ⚡ **Hybrid Parsing**: Tree-sitter speed + LLM semantic understanding
- 🔗 **Cross-Language Analysis**: Detect dependencies across different programming languages
- 📊 **Comprehensive Graphs**: Functions, classes, imports, inheritance, and more
- 🚀 **Scalable**: Parallel processing for large codebases
- 💾 **Multiple Export Formats**: JSON, DOT (Graphviz), summary reports

## Architecture

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   Source Code   │───▶│   Tree-sitter    │───▶│  Universal      │
│  (Multi-lang)   │    │   AST Parser     │    │  Node/Edge      │
└─────────────────┘    └──────────────────┘    │  Normalization  │
                                               └─────────────────┘
                                                        │
                       ┌─────────────────┐              ▼
                       │      LLM        │    ┌─────────────────┐
                       │   Enhancement   │◀───│  Semantic       │
                       │   (Optional)    │    │  Analysis       │
                       └─────────────────┘    └─────────────────┘
                                                        │
                                                        ▼
                                               ┌─────────────────┐
                                               │  Universal      │
                                               │  Code Graph     │
                                               └─────────────────┘
```

## Universal Types

### Node Types
- **Code Structures**: `function`, `class`, `struct`, `interface`, `enum`
- **Namespacing**: `namespace`, `module`, `package`
- **Type Definitions**: `type_alias`, `typedef`, `template`, `generic`
- **Variables**: `variable`, `constant`, `field`, `parameter`
- **Dependencies**: `import`, `include`
- **Files**: `file`

### Edge Types
- **Dependencies**: `imports`, `includes`, `depends_on`
- **Inheritance**: `inherits`, `implements`, `extends`
- **Containment**: `contains`, `defines`, `belongs_to`
- **Function Relations**: `calls`, `overrides`, `overloads`
- **Type Relations**: `uses_type`, `returns_type`, `parameter_type`
- **Access**: `accesses`, `located_in`

## Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd deepwiki-agent-universal-parser
```

2. **Install dependencies**:
```bash
pip install tree-sitter-language-pack tree-sitter python-dotenv
```

3. **Set up the environment**:
```bash
# Create .env file if needed for LLM configuration
touch .env
```

## Quick Start

### Basic Usage

```python
from universal_graph_builder import UniversalGraphBuilder

# Initialize the builder
builder = UniversalGraphBuilder()

# Parse specific files
files = ["src/main.py", "src/utils.cpp", "src/App.java"]
graph = builder.build_graph_from_files(files)

# Parse entire directory
graph = builder.build_graph_from_directory("./src")

# Generate summary report
summary = builder.generate_summary_report(graph)
print(f"Found {summary['total_nodes']} nodes and {summary['total_edges']} edges")

# Save graph
builder.save_graph(graph, "my_project_graph.json")
```

### Run the Demo

```bash
# Demo with example files
python universal_demo.py --mode files

# Demo with current directory
python universal_demo.py --mode directory

# Demo with custom directory
python universal_demo.py --mode directory --directory /path/to/your/project

# Run all demos
python universal_demo.py --mode all
```

## LLM Integration

To enable LLM enhancement for better semantic understanding:

```python
# Example with OpenAI (implement your LLM client)
class YourLLMClient:
    def chat(self, prompt):
        # Your LLM implementation
        return response

llm_client = YourLLMClient()
builder = UniversalGraphBuilder(llm_client=llm_client)
```

The system includes fallback rule-based normalization when LLM is not available.

## Example Output

### Graph Summary
```
UNIVERSAL GRAPH SUMMARY:
Total Nodes: 47
Total Edges: 43

Nodes by Type:
  file: 3
  function: 15
  class: 8
  import: 18
  struct: 3

Languages Found:
  python: 1 files
  cpp: 1 files  
  java: 1 files
```

### Detailed Analysis
```
FUNCTIONS:
  - main (python) at python.py:9
  - process_data (python) at python.py:25
  - main (cpp) at cpp.cpp:8
  - ImportExample (java) at java.java:8

CLASSES:
  - ImportExample (java) at java.java:8
```

## File Structure

```
deepwiki-agent-universal-parser/
├── universal_types.py          # Universal node/edge type definitions
├── llm_enhanced_parser.py      # Hybrid tree-sitter + LLM parser
├── universal_graph_builder.py  # Repository-level graph construction
├── universal_demo.py           # Demo script
├── config.py                   # Configuration utilities
├── examples/                   # Sample code files
│   ├── python.py
│   ├── cpp.cpp
│   └── java.java
├── grammars/                   # Tree-sitter grammars
│   ├── python.js
│   ├── cpp.js
│   └── java.js
└── queries/                    # Tree-sitter queries
    ├── definition/
    ├── dependence/
    └── importation/
```

## Extending the System

### Adding New Languages

1. **Add tree-sitter grammar** to `grammars/` directory
2. **Update language mappings** in `UniversalGraphBuilder`
3. **Add normalization rules** in `LLMEnhancedParser`
4. **Create test examples** in `examples/` directory

### Custom Node/Edge Types

```python
# Add to universal_types.py
class NodeType(Enum):
    # ... existing types ...
    YOUR_CUSTOM_TYPE = "your_custom_type"

class EdgeType(Enum):
    # ... existing types ...
    YOUR_CUSTOM_RELATIONSHIP = "your_custom_relationship"
```

### Enhanced Relationship Detection

Implement custom relationship detectors in `UniversalGraphBuilder`:

```python
def _detect_custom_relationships(self, graph):
    # Your custom relationship detection logic
    pass
```

## Use Cases

- **Code Analysis**: Understand large multi-language codebases
- **Dependency Tracking**: Visualize cross-file and cross-language dependencies  
- **Refactoring Support**: Identify impact of changes across languages
- **Documentation Generation**: Auto-generate architecture diagrams
- **Code Quality Metrics**: Analyze coupling and cohesion across languages
- **Migration Planning**: Understand dependencies when modernizing code

## Performance

- **Parallel Processing**: Multi-threaded file parsing
- **Efficient Memory Usage**: Streaming processing for large codebases
- **Caching**: Tree-sitter parse tree caching (planned)
- **Incremental Updates**: Delta processing for CI/CD (planned)

## Limitations & Future Work

### Current Limitations
- Limited cross-file relationship detection (work in progress)
- Basic LLM integration (extensible framework provided)
- C++ template parsing complexity
- Python dynamic import resolution

### Planned Enhancements
- **Advanced LLM Integration**: GPT-4, Claude, or local models
- **More Languages**: JavaScript, TypeScript, Rust, Go, etc.
- **Sophisticated Relationship Detection**: Function calls, variable usage
- **Real-time Analysis**: IDE plugins and development workflow integration
- **Visualization Tools**: Interactive graph exploration
- **Metrics & Analytics**: Code quality and architecture insights

## Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Acknowledgments

- [Tree-sitter](https://tree-sitter.github.io/) for fast, accurate parsing
- Tree-sitter language maintainers for grammar implementations
- The broader code analysis and static analysis community

---

**Built for developers who work with multi-language codebases and need unified analysis tools.** 