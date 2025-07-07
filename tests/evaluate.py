import json
import re
from typing import Dict, List, Set, Tuple
from dataclasses import dataclass
from pathlib import Path
import argparse

@dataclass
class EvaluationMetrics:
    """Container for evaluation metrics"""
    precision: float
    recall: float
    f1_score: float
    accuracy: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int = 0  # Not typically used for this type of evaluation


class CodeAnalysisBenchmark:
    """Benchmark tool for evaluating code analysis results"""
    
    def __init__(self, ground_truth_functions_path: str, ground_truth_relationships_path: str, method_output_path: str):
        self.gt_functions = self._load_json(ground_truth_functions_path)
        self.gt_relationships = self._load_json(ground_truth_relationships_path)
        self.method_output = self._load_json(method_output_path)
        
    def _load_json(self, path: str) -> dict:
        """Load JSON data from file"""
        with open(path, 'r') as f:
            return json.load(f)
    
    def _normalize_file_path(self, path: str) -> str:
        """Normalize file paths to handle different formats"""
        # Remove temporary directory paths and normalize
        path = re.sub(r'/var/folders/[^/]+/[^/]+/T/[^/]+/', '', path)
        path = re.sub(r'^.*?src/', 'src/', path)
        return path.replace('\\', '/')
    
    def _extract_function_name_from_path(self, full_path: str) -> str:
        """Extract function name from full path like 'src.app.search_v1'"""
        return full_path.split('.')[-1]
    
    def _normalize_node_identifier(self, node_data: dict, is_ground_truth: bool = False) -> str:
        """Create normalized identifier for nodes to enable comparison"""
        if is_ground_truth:
            # Ground truth format
            file_path = self._normalize_file_path(node_data['file_path'])
            func_name = node_data['name']
            class_name = node_data.get('class_name', '')
            
            if class_name:
                return f"{file_path}:{class_name}.{func_name}"
            else:
                return f"{file_path}:{func_name}"
        else:
            # Method output format - process all node types
            file_path = self._normalize_file_path(node_data['implementation_file'])
            # Extract function name from id like 'src.app.search_v1'
            func_name = self._extract_function_name_from_path(node_data['id'])
            
            # Check if it's a method (contains class name in id)
            parts = node_data['id'].split('.')
            if len(parts) >= 3:
                # Look for class pattern (capitalized name before function)
                for i in range(len(parts) - 1):
                    if parts[i][0].isupper():  # Any capitalized name could be a class
                        class_name = parts[i]
                        return f"{file_path}:{class_name}.{func_name}"
            
            return f"{file_path}:{func_name}"
    
    def _extract_function_from_caller_callee(self, caller_callee: str) -> str:
        """Extract normalized function identifier from caller/callee string"""
        if ':' in caller_callee:
            parts = caller_callee.split(':')
            file_part = self._normalize_file_path(parts[0])
            func_part = parts[1]
            return f"{file_part}:{func_part}"
        else:
            # External function call
            return None
    
    def _normalize_relationship_identifier(self, rel_data: dict, is_ground_truth: bool = False) -> str:
        """Create normalized identifier for relationships"""
        if is_ground_truth:
            caller = self._extract_function_from_caller_callee(rel_data['caller'])
            callee = self._extract_function_from_caller_callee(rel_data['callee'])

            if caller is None or callee is None:
                return None

            return f"{caller} -> {callee}"
        else:
            # Method output format - process all edge types
            # Extract function names from IDs
            subject_parts = rel_data['subject_id'].split('.')
            object_parts = rel_data['object_id'].split('.')
            
            subject_file = self._normalize_file_path(rel_data['subject_implementation_file'])
            object_file = self._normalize_file_path(rel_data['object_implementation_file'])
            
            subject_func = subject_parts[-1]
            object_func = object_parts[-1]
            
            # Use only the base function name for comparison
            subject_normalized = f"{subject_file}:{subject_func}"
            object_normalized = f"{object_file}:{object_func}"
            
            return f"{subject_normalized} -> {object_normalized}"
    
    def evaluate_nodes(self) -> EvaluationMetrics:
        """Evaluate node detection performance"""
        print("Evaluating nodes (all types)...")
        
        # Create sets of normalized identifiers
        gt_nodes = set()
        for func in self.gt_functions:
            identifier = self._normalize_node_identifier(func, is_ground_truth=True)
            gt_nodes.add(identifier)
            if func.get('class_name'):
                class_identifier = self._normalize_node_identifier({
                    'file_path': func['file_path'],
                    'name': func['class_name'],
                    'class_name': None,  # This is the class itself
                    'is_method': False
                }, is_ground_truth=True)
                gt_nodes.add(class_identifier)
            

        # print("===GROUND TRUTH NODES===")
        # for node in gt_nodes:
        #     print(node)
        
        predicted_nodes = set()
        for node in self.method_output['nodes']:
            identifier = self._normalize_node_identifier(node, is_ground_truth=False)
            predicted_nodes.add(identifier)

        # print("===PREDICTED NODES===")
        # for node in predicted_nodes:
        #     print(node)
        
        # Calculate metrics
        true_positives = len(gt_nodes & predicted_nodes)
        false_positives = len(predicted_nodes - gt_nodes)
        false_negatives = len(gt_nodes - predicted_nodes)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = true_positives / len(gt_nodes | predicted_nodes) if len(gt_nodes | predicted_nodes) > 0 else 0
        
        # Print detailed analysis
        print(f"\nNode Evaluation Results:")
        print(f"Ground Truth Nodes: {len(gt_nodes)}")
        print(f"Predicted Nodes: {len(predicted_nodes)}")
        print(f"True Positives: {true_positives}")
        print(f"False Positives: {false_positives}")
        print(f"False Negatives: {false_negatives}")
        
        if false_positives > 0:
            print(f"\nFalse Positives (predicted but not in ground truth):")
            for fp in sorted(list(predicted_nodes - gt_nodes))[:20]:  # Show first 10
                print(f"  {fp}")
        
        if false_negatives > 0:
            print(f"\nFalse Negatives (in ground truth but not predicted):")
            for fn in sorted(list(gt_nodes - predicted_nodes))[:20]:  # Show first 10
                print(f"  {fn}")
        
        return EvaluationMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives
        )
    
    def evaluate_edges(self) -> EvaluationMetrics:
        """Evaluate relationship detection performance"""
        print("\nEvaluating edges (all types)...")
        
        # Create sets of normalized relationship identifiers
        gt_edges = set()
        for rel in self.gt_relationships:
            # Consider all relationships, including external calls
            identifier = self._normalize_relationship_identifier(rel, is_ground_truth=True)
            if identifier:
                gt_edges.add(identifier)
        
        predicted_edges = set()
        for edge in self.method_output['edges']:
            identifier = self._normalize_relationship_identifier(edge, is_ground_truth=False)
            predicted_edges.add(identifier)
        
        # Calculate metrics
        true_positives = len(gt_edges & predicted_edges)
        false_positives = len(predicted_edges - gt_edges)
        false_negatives = len(gt_edges - predicted_edges)
        
        precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
        recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
        f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
        accuracy = true_positives / len(gt_edges | predicted_edges) if len(gt_edges | predicted_edges) > 0 else 0
        
        # Print detailed analysis
        print(f"\nEdge Evaluation Results:")
        print(f"Ground Truth Edges: {len(gt_edges)}")
        print(f"Predicted Edges: {len(predicted_edges)}")
        print(f"True Positives: {true_positives}")
        print(f"False Positives: {false_positives}")
        print(f"False Negatives: {false_negatives}")
        
        if false_positives > 0:
            print(f"\nFalse Positives (predicted but not in ground truth):")
            for fp in sorted(list(predicted_edges - gt_edges))[:20]:  # Show first 10
                print(f"  {fp}")
        
        if false_negatives > 0:
            print(f"\nFalse Negatives (in ground truth but not predicted):")
            for fn in sorted(list(gt_edges - predicted_edges))[:20]:  # Show first 10
                print(f"  {fn}")
        
        return EvaluationMetrics(
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            accuracy=accuracy,
            true_positives=true_positives,
            false_positives=false_positives,
            false_negatives=false_negatives
        )
    
    def run_full_evaluation(self) -> Tuple[EvaluationMetrics, EvaluationMetrics]:
        """Run complete evaluation for both nodes and edges"""
        print("=" * 60)
        print("CODE ANALYSIS BENCHMARK EVALUATION")
        print("=" * 60)
        
        node_metrics = self.evaluate_nodes()
        edge_metrics = self.evaluate_edges()
        
        print("\n" + "=" * 60)
        print("FINAL RESULTS SUMMARY")
        print("=" * 60)
        
        print(f"\nNODE EVALUATION:")
        print(f"  Precision: {node_metrics.precision:.4f}")
        print(f"  Recall:    {node_metrics.recall:.4f}")
        print(f"  F1 Score:  {node_metrics.f1_score:.4f}")
        print(f"  Accuracy:  {node_metrics.accuracy:.4f}")
        
        print(f"\nEDGE EVALUATION:")
        print(f"  Precision: {edge_metrics.precision:.4f}")
        print(f"  Recall:    {edge_metrics.recall:.4f}")
        print(f"  F1 Score:  {edge_metrics.f1_score:.4f}")
        print(f"  Accuracy:  {edge_metrics.accuracy:.4f}")
        
        print(f"\nOVERALL PERFORMANCE:")
        overall_f1 = (node_metrics.f1_score + edge_metrics.f1_score) / 2
        overall_precision = (node_metrics.precision + edge_metrics.precision) / 2
        overall_recall = (node_metrics.recall + edge_metrics.recall) / 2
        print(f"  Average Precision: {overall_precision:.4f}")
        print(f"  Average Recall:    {overall_recall:.4f}")
        print(f"  Average F1 Score:  {overall_f1:.4f}")
        
        return node_metrics, edge_metrics


def main(args):
    """Main function to run the benchmark"""
    # File paths
    gt_functions_path = args.gt_functions_path
    gt_relationships_path = args.gt_relationships_path
    method_output_path = args.method_output_path
    
    # Create benchmark instance
    benchmark = CodeAnalysisBenchmark(
        gt_functions_path, 
        gt_relationships_path, 
        method_output_path
    )
    
    # Run evaluation
    node_metrics, edge_metrics = benchmark.run_full_evaluation()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run code analysis benchmark evaluation')
    parser.add_argument('--gt-functions-path', type=str, required=True, help='Path to ground truth functions JSON file')
    parser.add_argument('--gt-relationships-path', type=str, required=True, help='Path to ground truth relationships JSON file')
    parser.add_argument('--method-output-path', type=str, required=True, help='Path to method output JSON file')
    args = parser.parse_args()
    main(args) 