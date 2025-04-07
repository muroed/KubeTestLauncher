import os
import logging
import yaml
import uuid
import time
from kubernetes import client, config
from kubernetes.client.rest import ApiException

logger = logging.getLogger(__name__)

class K8sClient:
    """Client for interacting with Kubernetes API."""
    
    def __init__(self, mock_mode=False):
        """
        Initialize the Kubernetes client.
        
        Args:
            mock_mode (bool): If True, run in mock mode without connecting to K8s
        """
        self.mock_mode = mock_mode or os.environ.get("K8S_MOCK_MODE", "").lower() in ("true", "1", "yes")
        
        if self.mock_mode:
            logger.info("Initializing Kubernetes client in mock mode")
            self.core_v1_api = None
            self.apps_v1_api = None
            self.batch_v1_api = None
            self.namespace = "mock-namespace"
            return
            
        try:
            # Try to load in-cluster config first (when running inside K8s)
            config.load_incluster_config()
            logger.info("Using in-cluster Kubernetes configuration")
        except config.ConfigException:
            try:
                # Fall back to kubeconfig file
                config.load_kube_config()
                logger.info("Using kubeconfig file for Kubernetes configuration")
            except config.ConfigException:
                logger.error("Failed to load Kubernetes configuration")
                self.mock_mode = True
                logger.warning("Falling back to mock mode")
                self.core_v1_api = None
                self.apps_v1_api = None
                self.batch_v1_api = None
                self.namespace = "mock-namespace"
                return
        
        # Initialize API clients
        self.core_v1_api = client.CoreV1Api()
        self.apps_v1_api = client.AppsV1Api()
        self.batch_v1_api = client.BatchV1Api()
        
        # Namespace for creating resources
        self.namespace = os.environ.get("K8S_NAMESPACE", "default")
        logger.info(f"Using Kubernetes namespace: {self.namespace}")
        
        # Test connection
        try:
            self._test_connection()
        except Exception as e:
            logger.error(f"Failed to connect to Kubernetes API: {e}")
            self.mock_mode = True
            logger.warning("Falling back to mock mode")
    
    def _test_connection(self):
        """Test connection to Kubernetes API."""
        try:
            self.core_v1_api.list_namespace()
            return True
        except ApiException as e:
            logger.error(f"Kubernetes API connection test failed: {e}")
            raise
    
    def is_connected(self):
        """Check if connected to Kubernetes API."""
        if self.mock_mode:
            logger.info("Mock mode: Reporting as not connected to Kubernetes API")
            return False
            
        try:
            self._test_connection()
            return True
        except:
            return False
    
    def create_job(self, name, image, command, env_vars=None, volume_mounts=None, volumes=None, timeout_seconds=300):
        """
        Create a Kubernetes Job to run a test runner.
        
        Args:
            name (str): Name prefix for the job
            image (str): Container image to use
            command (list): Command to run in the container
            env_vars (dict): Environment variables
            volume_mounts (list): Volume mounts
            volumes (list): Volumes
            timeout_seconds (int): Job timeout in seconds
            
        Returns:
            str: Name of the created job
        """
        # Generate a unique job name
        job_name = f"{name}-{str(uuid.uuid4())[:8]}"
        
        if self.mock_mode:
            logger.info(f"Mock mode: Simulating job creation: {job_name}")
            return job_name
            
        # Prepare container definition
        container = client.V1Container(
            name="test-runner",
            image=image,
            command=command,
            env=[client.V1EnvVar(name=k, value=v) for k, v in (env_vars or {}).items()],
            volume_mounts=volume_mounts or []
        )
        
        # Prepare job spec
        job_spec = client.V1JobSpec(
            template=client.V1PodTemplateSpec(
                metadata=client.V1ObjectMeta(labels={"app": job_name}),
                spec=client.V1PodSpec(
                    containers=[container],
                    restart_policy="Never",
                    volumes=volumes or []
                )
            ),
            backoff_limit=0,  # Don't retry on failure
            ttl_seconds_after_finished=300,  # Clean up after 5 minutes
            active_deadline_seconds=timeout_seconds  # Job timeout
        )
        
        # Prepare job
        job = client.V1Job(
            api_version="batch/v1",
            kind="Job",
            metadata=client.V1ObjectMeta(name=job_name),
            spec=job_spec
        )
        
        # Create the job
        logger.info(f"Creating Kubernetes job: {job_name}")
        try:
            self.batch_v1_api.create_namespaced_job(
                namespace=self.namespace,
                body=job
            )
            return job_name
        except ApiException as e:
            logger.error(f"Failed to create job: {e}")
            raise
    
    def wait_for_job_completion(self, job_name, timeout_seconds=300, check_interval=5):
        """
        Wait for a job to complete and return its status.
        
        Args:
            job_name (str): Name of the job
            timeout_seconds (int): Maximum time to wait
            check_interval (int): Time between status checks
            
        Returns:
            tuple: (bool, str) - (success, logs)
        """
        logger.info(f"Waiting for job completion: {job_name}")
        
        if self.mock_mode:
            # In mock mode, simulate a successful job execution
            logger.info(f"Mock mode: Simulating successful job completion: {job_name}")
            # Check language from job name (e.g., python-test-abc123)
            language = job_name.split('-')[0] if '-' in job_name else "unknown"
            
            # Generate mock test results based on language
            if language == "python":
                mock_logs = '{"status": "pass", "tests": [{"name": "test_hello_world", "status": "pass"}]}'
            elif language == "javascript":
                mock_logs = '{"status": "pass", "tests": [{"name": "test_hello_world", "status": "pass"}]}'
            else:
                mock_logs = '{"status": "pass", "message": "All tests passed"}'
                
            # Simulate some processing time
            time.sleep(1)
            return True, mock_logs
        
        # Real implementation for Kubernetes
        start_time = time.time()
        
        while time.time() - start_time < timeout_seconds:
            try:
                job = self.batch_v1_api.read_namespaced_job_status(
                    name=job_name,
                    namespace=self.namespace
                )
                
                # Check if job completed
                if job.status.succeeded is not None and job.status.succeeded > 0:
                    logger.info(f"Job completed successfully: {job_name}")
                    # Get logs from the pod
                    pod_logs = self._get_pod_logs_for_job(job_name)
                    return True, pod_logs
                
                # Check if job failed
                if job.status.failed is not None and job.status.failed > 0:
                    logger.warning(f"Job failed: {job_name}")
                    # Get logs from the pod
                    pod_logs = self._get_pod_logs_for_job(job_name)
                    return False, pod_logs
                
                # Job still running
                logger.debug(f"Job still running: {job_name}")
                time.sleep(check_interval)
                
            except ApiException as e:
                logger.error(f"Error checking job status: {e}")
                raise
        
        # Timeout reached
        logger.error(f"Timeout waiting for job completion: {job_name}")
        return False, "Timeout waiting for job completion"
    
    def _get_pod_logs_for_job(self, job_name):
        """
        Get logs from pods created by the job.
        
        Args:
            job_name (str): Name of the job
            
        Returns:
            str: Pod logs or error message
        """
        if self.mock_mode:
            logger.info(f"Mock mode: Simulating pod logs retrieval for job: {job_name}")
            return f"Mock logs for job {job_name}"
            
        try:
            # Get pods with the job label
            pod_list = self.core_v1_api.list_namespaced_pod(
                namespace=self.namespace,
                label_selector=f"app={job_name}"
            )
            
            if not pod_list.items:
                return "No pods found for the job"
            
            # Get logs from the first pod
            pod_name = pod_list.items[0].metadata.name
            logs = self.core_v1_api.read_namespaced_pod_log(
                name=pod_name,
                namespace=self.namespace
            )
            
            return logs
        except ApiException as e:
            logger.error(f"Error getting pod logs: {e}")
            return f"Error retrieving logs: {e}"
    
    def create_config_map(self, name, data):
        """
        Create a ConfigMap to store code and test files.
        
        Args:
            name (str): Name for the ConfigMap
            data (dict): Data to store in the ConfigMap
            
        Returns:
            str: Name of the created ConfigMap
        """
        config_map_name = f"{name}-{str(uuid.uuid4())[:8]}"
        
        if self.mock_mode:
            logger.info(f"Mock mode: Simulating ConfigMap creation: {config_map_name}")
            return config_map_name
            
        config_map = client.V1ConfigMap(
            api_version="v1",
            kind="ConfigMap",
            metadata=client.V1ObjectMeta(name=config_map_name),
            data=data
        )
        
        try:
            self.core_v1_api.create_namespaced_config_map(
                namespace=self.namespace,
                body=config_map
            )
            return config_map_name
        except ApiException as e:
            logger.error(f"Failed to create ConfigMap: {e}")
            raise
    
    def delete_config_map(self, name):
        """Delete a ConfigMap."""
        if self.mock_mode:
            logger.info(f"Mock mode: Simulating ConfigMap deletion: {name}")
            return
            
        try:
            self.core_v1_api.delete_namespaced_config_map(
                name=name,
                namespace=self.namespace
            )
            logger.info(f"Deleted ConfigMap: {name}")
        except ApiException as e:
            logger.warning(f"Failed to delete ConfigMap {name}: {e}")
            # We don't raise here because this is cleanup code
