import os
import sys
from collections import defaultdict
from typing import List, Dict
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split as split

from src.llm_services import cross_dependence
from test.utils import local_dependence


class MyClass:
    def __init__(self, name: str):
        self.name = name
    
    def __str__(self):
        return f"MyClass(name={self.name})"

# Using imported packages
def main():
    # Using os
    current_dir = os.getcwd()

    # Using cross_dependence
    cross_dependence(current_dir)

    # Using local_dependence
    local_dependence(current_dir)
    
    # Using sys
    print(f"Python version: {sys.version}")
    
    # Using defaultdict from collections
    word_count = defaultdict(int)
    word_count['hello'] += 1
    
    # Using typing for type hints
    def process_data(items: List[str]) -> Dict[str, int]:
        return {item: len(item) for item in items}
    
    # Using numpy
    arr = np.array([1, 2, 3, 4, 5])
    mean_val = np.mean(arr)
    
    # Using pandas
    df = pd.DataFrame({'A': [1, 2, 3], 'B': [4, 5, 6]})
    
    # Using aliased import
    X = np.random.rand(100, 4)
    y = np.random.rand(100)
    X_train, X_test, y_train, y_test = split(X, y, test_size=0.2)
    
    print(f"Dataset split: {len(X_train)} train, {len(X_test)} test")