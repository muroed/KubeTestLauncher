import unittest
from unittest.mock import MagicMock, patch
import yaml

from k8s_client import K8sClient

class TestK8sClient(unittest.TestCase):
    """Tests for the K8sClient class."""
    
    @patch('k8s_client.config')
    @patch('k8s_client.client')
    def setUp(self, mock_client, mock_config):
        """Set up test fixtures."""
        # Mock the Kubernetes configuration and API clients
        self.mock_core_v1_api = MagicMock()
        self.mock_apps_v1_api = MagicMock()
        self.mock_batch_v1_api = MagicMock()
        
        mock_client.CoreV1Api.return_value = self.mock_core_v1_api
        mock_client.AppsV1Api.return_value = self.mock_apps_v1_api
        mock_client.BatchV1Api.return_value = self.mock_batch_v1_api
        
        # Override _test_connection to avoid actual API calls
        with patch.object(K8sClient, '_test_connection', return_value=True):
            self.k8s_client = K8sClient()
    
    def test_is_connected(self):
        """Test connection check."""
        with patch.object(self.k8s_client, '_test_connection', return_value=True):
            self.assertTrue(self.k8s_client.is_connected())
        
        with patch.object(self.k8s_client, '_test_connection', side_effect=Exception("Connection error")):
            self.assertFalse(self.k8s_client.is_connected())
    
    def test_create_config_map(self):
        """Test creating a ConfigMap."""
        # Mock the API response
        self.mock_core_v1_api.create_namespaced_config_map.return_value = MagicMock(
            metadata=MagicMock(name="test-config-map")
        )
        
        # Call the method
        data = {"key": "value"}
        result = self.k8s_client.create_config_map("test", data)
        
        # Verify the result and API call
        self.assertTrue(result.startswith("test-"))
        self.mock_core_v1_api.create_namespaced_config_map.assert_called_once()
        
        # Get the body argument from the call
        body = self.mock_core_v1_api.create_namespaced_config_map.call_args[1]['body']
        self.assertEqual(body.data, data)
    
    def test_create_job(self):
        """Test creating a Job."""
        # Mock the API response
        self.mock_batch_v1_api.create_namespaced_job.return_value = MagicMock(
            metadata=MagicMock(name="test-job")
        )
        
        # Call the method
        result = self.k8s_client.create_job(
            name="test",
            image="test-image",
            command=["echo", "hello"],
            env_vars={"VAR": "value"}
        )
        
        # Verify the result and API call
        self.assertTrue(result.startswith("test-"))
        self.mock_batch_v1_api.create_namespaced_job.assert_called_once()
        
        # Get the body argument from the call
        body = self.mock_batch_v1_api.create_namespaced_job.call_args[1]['body']
        self.assertEqual(body.spec.template.spec.containers[0].image, "test-image")
        self.assertEqual(body.spec.template.spec.containers[0].command, ["echo", "hello"])
        
        # Check for the environment variable
        env_vars = body.spec.template.spec.containers[0].env
        self.assertEqual(len(env_vars), 1)
        self.assertEqual(env_vars[0].name, "VAR")
        self.assertEqual(env_vars[0].value, "value")
    
    def test_wait_for_job_completion_success(self):
        """Test waiting for a successful job."""
        # Mock the job status
        mock_job = MagicMock()
        mock_job.status.succeeded = 1
        mock_job.status.failed = None
        
        self.mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job
        
        # Mock the pod logs
        self.mock_core_v1_api.list_namespaced_pod.return_value = MagicMock(
            items=[MagicMock(metadata=MagicMock(name="test-pod"))]
        )
        self.mock_core_v1_api.read_namespaced_pod_log.return_value = "Test logs"
        
        # Call the method
        success, logs = self.k8s_client.wait_for_job_completion("test-job")
        
        # Verify the result
        self.assertTrue(success)
        self.assertEqual(logs, "Test logs")
        
        # Verify API calls
        self.mock_batch_v1_api.read_namespaced_job_status.assert_called_once()
        self.mock_core_v1_api.list_namespaced_pod.assert_called_once()
        self.mock_core_v1_api.read_namespaced_pod_log.assert_called_once()
    
    def test_wait_for_job_completion_failure(self):
        """Test waiting for a failed job."""
        # Mock the job status
        mock_job = MagicMock()
        mock_job.status.succeeded = None
        mock_job.status.failed = 1
        
        self.mock_batch_v1_api.read_namespaced_job_status.return_value = mock_job
        
        # Mock the pod logs
        self.mock_core_v1_api.list_namespaced_pod.return_value = MagicMock(
            items=[MagicMock(metadata=MagicMock(name="test-pod"))]
        )
        self.mock_core_v1_api.read_namespaced_pod_log.return_value = "Error logs"
        
        # Call the method
        success, logs = self.k8s_client.wait_for_job_completion("test-job")
        
        # Verify the result
        self.assertFalse(success)
        self.assertEqual(logs, "Error logs")
        
        # Verify API calls
        self.mock_batch_v1_api.read_namespaced_job_status.assert_called_once()
        self.mock_core_v1_api.list_namespaced_pod.assert_called_once()
        self.mock_core_v1_api.read_namespaced_pod_log.assert_called_once()
    
    def test_delete_config_map(self):
        """Test deleting a ConfigMap."""
        # Call the method
        self.k8s_client.delete_config_map("test-config-map")
        
        # Verify the API call
        self.mock_core_v1_api.delete_namespaced_config_map.assert_called_once_with(
            name="test-config-map",
            namespace=self.k8s_client.namespace
        )

if __name__ == '__main__':
    unittest.main()
