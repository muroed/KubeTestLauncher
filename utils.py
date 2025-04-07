import logging
import json
import os

logger = logging.getLogger(__name__)

def validate_test_config(config, language):
    """
    Validate the test configuration for a specific language.
    
    Args:
        config (dict): Test configuration
        language (str): Programming language
        
    Returns:
        bool: True if valid, False otherwise
    """
    # Basic validation to ensure it's a non-empty dict
    if not isinstance(config, dict) or not config:
        logger.error("Invalid test config: not a non-empty dict")
        return False
    
    # Specific validation for different languages
    if language == 'python':
        # For Python test runner we expect at least 'version' and 'test_files'
        if 'version' not in config:
            logger.error("Missing 'version' in Python test config")
            return False
        
        if 'test_file' not in config and 'test_files' not in config:
            logger.error("Missing 'test_file' or 'test_files' in Python test config")
            return False
    
    # Add more language-specific validation as needed
    
    return True

def read_file_content(filepath):
    """
    Read content from a file.
    
    Args:
        filepath (str): Path to the file
        
    Returns:
        str: File content
    """
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        raise FileNotFoundError(f"File not found: {filepath}")
    
    with open(filepath, 'r') as f:
        return f.read()

def write_file_content(filepath, content):
    """
    Write content to a file.
    
    Args:
        filepath (str): Path to the file
        content (str): Content to write
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            f.write(content)
        return True
    except Exception as e:
        logger.error(f"Failed to write file {filepath}: {e}")
        return False

def parse_test_results(output):
    """
    Parse test runner output to extract results.
    
    Args:
        output (str): Test runner output
        
    Returns:
        dict: Parsed test results
    """
    try:
        # Look for JSON in the output
        start_idx = output.find('{')
        end_idx = output.rfind('}')
        
        if start_idx >= 0 and end_idx > start_idx:
            json_str = output[start_idx:end_idx+1]
            return json.loads(json_str)
        else:
            return {
                "status": "error",
                "message": "No JSON results found in output",
                "raw_output": output
            }
    except json.JSONDecodeError:
        return {
            "status": "error",
            "message": "Failed to parse JSON results",
            "raw_output": output
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error parsing results: {str(e)}",
            "raw_output": output
        }
