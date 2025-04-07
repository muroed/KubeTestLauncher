#!/bin/bash

# Test the API
echo "Testing the Exercism Test Runner API..."

# Test the health endpoint
echo "Testing health endpoint..."
curl -s http://localhost:5000/health

# Test the Python test runner
echo -e "\n\nTesting Python test runner..."
curl -s -X POST \
  -F "code_file=@test-python-code.py" \
  -F "test_config=@test-config.json" \
  http://localhost:5000/api/python-test-runner/start | python -m json.tool

echo -e "\nAPI test complete!"