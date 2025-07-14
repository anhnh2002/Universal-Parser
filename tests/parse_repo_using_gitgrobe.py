import requests
import argparse
import os
import json

from logger import logger


def main(args):
    # Analyze repository
    response = requests.post("http://localhost:8000/analyze", json={
        "github_url": args.repo_url,
        # "include_patterns": ["*.py"],
        "exclude_patterns": ["*test*", "docs/", "examples/", "tests/"]
    })

    result = response.json()
    logger.debug(f"GitGrobe found {result['data']['summary']['total_functions']} functions")
    logger.debug(f"GitGrobe found {result['data']['summary']['languages_analyzed']} languages")

    # Save the result to a file
    output_dir = f"./data/gitgrobe-outputs/{args.repo_name}"
    os.makedirs(output_dir, exist_ok=True)

    with open(f"{output_dir}/functions.json", "w") as f:
        json.dump(result['data']['functions'], f, indent=4)
    
    with open(f"{output_dir}/relationships.json", "w") as f:
        json.dump(result['data']['relationships'], f, indent=4)
    
    


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-url", type=str, required=True)
    parser.add_argument("--repo-name", type=str, required=True)
    args = parser.parse_args()
    main(args)