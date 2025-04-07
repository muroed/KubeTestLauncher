import unittest
import tempfile
import os
import json
from unittest.mock import MagicMock, patch

from runner_service import RunnerService

class TestRunnerService(unittest.TestCase):
    """Tests for the RunnerService class."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.k8s_client = MagicMock()
        self.runner_service = RunnerService(self.k8s_client)
        
        # Create a temp file with test code
        self.temp_dir = tempfile.TemporaryDirectory()
        self.code_file = os.path.join(self.temp_dir.name, 'solution.py')
        with open(self.code_file, 'w') as f:
            f.write('def hello():\n    return "Hello, World!"\n')
        
        # Sample test config
        self.test_config = {
            'version': 1,
            'test_files': ['test_hello.py']
        }
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.temp_dir.cleanup()
    
    def test_run_tests_unsupported_language(self):
        """Test running tests with an unsupported language."""
        with self.assertRaises(ValueError):
            self.runner_service.run_tests('unsupported', self.code_file, self.test_config)
    
    @patch('runner_service.SUPPORTED_LANGUAGES', {
        'python': {
            'image': 'exercism/python-test-runner:latest',
            'file_extension': 'py',
            'timeout': 60,
        }
    })
    def test_run_tests_success(self):
        """Test running tests successfully."""
        # Mock the K8s client methods
        self.k8s_client.create_config_map.return_value = 'test-config-map'
        self.k8s_client.create_job.return_value = 'test-job'
        self.k8s_client.wait_for_job_completion.return_value = (
            True, 
            '{"status": "pass", "tests": [{"name": "test_hello", "status": "pass"}]}'
        )
        
        # Run the tests
        result = self.runner_service.run_tests('python', self.code_file, self.test_config)
        
        # Verify the result
        self.assertEqual(result['status'], 'pass')
        self.assertIn('tests', result)
        
        # Verify the K8s client method calls
        self.k8s_client.create_config_map.assert_called_once()
        self.k8s_client.create_job.assert_called_once()
        self.k8s_client.wait_for_job_completion.assert_called_once_with('test-job')
        self.k8s_client.delete_config_map.assert_called_once_with('test-config-map')
    
    @patch('runner_service.SUPPORTED_LANGUAGES', {
        'python': {
            'image': 'exercism/python-test-runner:latest',
            'file_extension': 'py',
            'timeout': 60,
        }
    })
    def test_run_tests_failure(self):
        """Test running tests with a failure."""
        # Mock the K8s client methods
        self.k8s_client.create_config_map.return_value = 'test-config-map'
        self.k8s_client.create_job.return_value = 'test-job'
        self.k8s_client.wait_for_job_completion.return_value = (
            False, 
            'Error: Test execution failed'
        )
        
        # Run the tests
        result = self.runner_service.run_tests('python', self.code_file, self.test_config)
        
        # Verify the result
        self.assertEqual(result['status'], 'fail')
        self.assertEqual(result['message'], 'Test execution failed')
        self.assertEqual(result['raw_output'], 'Error: Test execution failed')
        
        # Verify the K8s client method calls
        self.k8s_client.create_config_map.assert_called_once()
        self.k8s_client.create_job.assert_called_once()
        self.k8s_client.wait_for_job_completion.assert_called_once_with('test-job')
        self.k8s_client.delete_config_map.assert_called_once_with('test-config-map')

if __name__ == '__main__':
    unittest.main()
