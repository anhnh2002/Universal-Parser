#include <iostream>
#include <vector>
#include <string>
#include <algorithm>
#include "myheader.h"
#include "utils/helper.hpp"

int main() {
    // Using iostream
    std::cout << "Hello, World!" << std::endl;
    
    // Using vector
    std::vector<int> numbers = {3, 1, 4, 1, 5, 9, 2};
    
    // Using string
    std::string message = "C++ Programming";
    
    // Using algorithm
    std::sort(numbers.begin(), numbers.end());
    
    std::cout << "Sorted numbers: ";
    for (const auto& num : numbers) {
        std::cout << num << " ";
    }
    std::cout << std::endl;
    
    // Find maximum element
    auto max_it = std::max_element(numbers.begin(), numbers.end());
    std::cout << "Maximum: " << *max_it << std::endl;
    
    // Using custom headers (example functions)
    myFunction(); // from myheader.h
    helper::utilityFunction(); // from utils/helper.hpp
    
    return 0;
}