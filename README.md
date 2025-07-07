```bash

python config.py --provider fireworks --model accounts/fireworks/models/deepseek-v3-0324
python config.py --provider anthropic --model claude-sonnet-4-20250514

python parse_repo_using_gitgrobe.py --repo-url https://github.com/ggml-org/whisper.cpp.git --repo-name whisper.cpp

python parse_single_file.py --file-path /Users/anhnh/Documents/vscode/deepwiki-agent-universal-parser/src/data/repos/whisper.cpp/src/whisper.cpp --absolute-path-to-project /Users/anhnh/Documents/vscode/deepwiki-agent-universal-parser/src/data/repos/whisper.cpp --repo-name whisper.cpp

python parse_repository.py --repo-path /Users/anhnh/Documents/vscode/deepwiki-agent-universal-parser/src/data/repos/whisper.cpp --repo-name whisper.cpp --max-concurrent 10

python evaluate.py --gt-functions-path /Users/anhnh/Documents/vscode/deepwiki-agent-universal-parser/src/data/gitgrobe-outputs/DocAgent/functions.json --gt-relationships-path /Users/anhnh/Documents/vscode/deepwiki-agent-universal-parser/src/data/gitgrobe-outputs/DocAgent/relationships.json --method-output-path /Users/anhnh/Documents/vscode/deepwiki-agent-universal-parser/src/data/outputs/DocAgent-claude-sonnet-4-20250514/aggregated_results.json

python evaluate.py --gt-functions-path /Users/anhnh/Documents/vscode/deepwiki-agent-universal-parser/src/data/gitgrobe-outputs/whisper.cpp/functions.json --gt-relationships-path /Users/anhnh/Documents/vscode/deepwiki-agent-universal-parser/src/data/gitgrobe-outputs/whisper.cpp/relationships.json --method-output-path /Users/anhnh/Documents/vscode/deepwiki-agent-universal-parser/src/data/outputs/whisper.cpp-deepseek-v3-0324/aggregated_results.json


python convert_gitprobe_to_aggregated.py data/gitgrobe-outputs/DocAgent/relationships.json data/gitgrobe-outputs/DocAgent/functions.json data/gitgrobe-outputs/DocAgent/converted_aggregated_results.json --repo-name DocAgent-gitgrobe --repo-path /path/to/doc-agent


python load_to_neo4j.py --file outputs/DocAgent-claude-sonnet-4-20250514/aggregated_results.json --repo DocAgent
```

