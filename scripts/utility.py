#!/usr/bin/env python3
"""
Utility functions for the application
This module contains helper functions and utilities
"""
#Testing again
import json
import os
import time
from datetime import datetime


def log_message(message, level="INFO"):
    """
    Log a message with timestamp and level
    
    Args:
        message (str): The message to log
        level (str): Log level (INFO, WARNING, ERROR)
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")


def read_config(config_file="config.json"):
    """
    Read configuration from JSON file
    
    Args:
        config_file (str): Path to config file
        
    Returns:
        dict: Configuration dictionary
    """
    if os.path.exists(config_file):
        try:
            with open(config_file, 'r') as f:
                config = json.load(f)
            log_message(f"Configuration loaded from {config_file}")
            return config
        except Exception as e:
            log_message(f"Error reading config: {e}", "ERROR")
            return {}
    else:
        log_message(f"Config file {config_file} not found, using defaults", "WARNING")
        return {
            "app_name": "Default App",
            "debug": False,
            "timeout": 30
        }


def write_output(data, filename="output.json"):
    """
    Write data to output file
    
    Args:
        data (dict): Data to write
        filename (str): Output filename
    """
    try:
        with open(filename, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        log_message(f"Output written to {filename}")
    except Exception as e:
        log_message(f"Error writing output: {e}", "ERROR")


def measure_execution_time(func):
    """
    Decorator to measure function execution time
    
    Args:
        func: Function to measure
        
    Returns:
        Wrapped function
    """
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        execution_time = end_time - start_time
        log_message(f"Function {func.__name__} executed in {execution_time:.4f} seconds")
        return result
    return wrapper


@measure_execution_time
def process_file_list(file_patterns):
    """
    Process a list of file patterns and return matching files
    
    Args:
        file_patterns (list): List of file patterns to search for
        
    Returns:
        list: List of matching files
    """
    import glob
    
    matching_files = []
    for pattern in file_patterns:
        matches = glob.glob(pattern, recursive=True)
        matching_files.extend(matches)
        log_message(f"Pattern '{pattern}' matched {len(matches)} files")
    
    return list(set(matching_files))  # Remove duplicates


def system_info():
    """
    Get system information
    
    Returns:
        dict: System information
    """
    import platform
    import sys
    
    info = {
        "platform": platform.platform(),
        "python_version": sys.version,
        "architecture": platform.architecture(),
        "processor": platform.processor(),
        "hostname": platform.node(),
        "current_directory": os.getcwd(),
        "environment_variables": dict(os.environ)
    }
    
    return info


def main():
    """Main function for testing utilities"""
    print("🔧 UTILITY SCRIPT EXECUTION")
    print("=" * 40)
    
    log_message("Starting utility script")
    
    # Test configuration reading
    config = read_config()
    log_message(f"Loaded config: {config}")
    
    # Test file processing
    python_files = process_file_list(["*.py", "**/*.py"])
    log_message(f"Found {len(python_files)} Python files")
    
    # Get system info
    info = system_info()
    log_message("System information collected")
    
    # Write output
    output_data = {
        "timestamp": datetime.now().isoformat(),
        "config": config,
        "python_files": python_files[:10],  # First 10 files
        "system_info": {
            "platform": info["platform"],
            "python_version": info["python_version"],
            "hostname": info["hostname"]
        }
    }
    
    write_output(output_data, "utility_output.json")
    
    log_message("Utility script completed successfully")


if __name__ == "__main__":
    main()
