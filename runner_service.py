import os
import logging
import json
import time
import uuid
from config import SUPPORTED_LANGUAGES

logger = logging.getLogger(__name__)

class RunnerService:
    """Service for running tests in Kubernetes."""
    
    def __init__(self, k8s_client):
        """
        Initialize the runner service.
        
        Args:
            k8s_client: Kubernetes client instance
        """
        self.k8s_client = k8s_client
    
    def run_tests(self, language, code_filepath, test_config):
        """
        Run tests for the given code.
        
        Args:
            language (str): Programming language
            code_filepath (str): Path to the code file
            test_config (dict): Test configuration
            
        Returns:
            dict: Test results
        """
        if language not in SUPPORTED_LANGUAGES:
            raise ValueError(f"Unsupported language: {language}")
        
        try:
            # Read the code file
            with open(code_filepath, 'r') as f:
                code_content = f.read()
            
            # Create a unique ID for this test run
            run_id = str(uuid.uuid4())[:8]
            
            # Get language-specific settings
            lang_config = SUPPORTED_LANGUAGES[language]
            container_image = lang_config['image']
            file_extension = lang_config['file_extension']
            
            # Prepare code and test configuration for ConfigMap
            code_filename = f"solution.{file_extension}"
            config_filename = "test_config.json"
            
            config_map_data = {
                code_filename: code_content,
                config_filename: json.dumps(test_config)
            }
            
            # Create ConfigMap to hold code and test configuration
            config_map_name = self.k8s_client.create_config_map(
                name=f"{language}-test-{run_id}",
                data=config_map_data
            )
            
            # Prepare volume and volume mount for the ConfigMap
            volume = {
                "name": "test-files",
                "config_map": {
                    "name": config_map_name
                }
            }
            
            volume_mount = {
                "name": "test-files",
                "mount_path": "/mnt/exercise"
            }
            
            # Check if we're in mock mode to bypass Kubernetes client usage
            if hasattr(self.k8s_client, 'mock_mode') and self.k8s_client.mock_mode:
                # In mock mode, we don't need to create real Kubernetes objects
                volume_k8s = volume
                volume_mount_k8s = volume_mount
            else:
                # Convert volume and volume_mount to Kubernetes API objects
                from kubernetes import client as k8s_client
                
                volume_k8s = k8s_client.V1Volume(
                    name=volume["name"],
                    config_map=k8s_client.V1ConfigMapVolumeSource(
                        name=volume["config_map"]["name"]
                    )
                )
                
                volume_mount_k8s = k8s_client.V1VolumeMount(
                    name=volume_mount["name"],
                    mount_path=volume_mount["mount_path"]
                )
            
            # Prepare command for the test runner
            command = [
                "sh",
                "-c",
                f"cd /mnt/exercise && "
                f"cp {code_filename} /opt/test-runner/code/{code_filename} && "
                f"cp {config_filename} /opt/test-runner/config.json && "
                f"cd /opt/test-runner && "
                f"./bin/run.sh /opt/test-runner/code /opt/test-runner/output"
            ]
            
            # Create and start the job
            job_name = self.k8s_client.create_job(
                name=f"{language}-test-{run_id}",
                image=container_image,
                command=command,
                volume_mounts=[volume_mount_k8s],
                volumes=[volume_k8s],
                timeout_seconds=120  # 2 minutes timeout
            )
            
            # Wait for job completion
            success, logs = self.k8s_client.wait_for_job_completion(job_name)
            
            # Clean up the ConfigMap
            try:
                self.k8s_client.delete_config_map(config_map_name)
            except Exception as e:
                logger.warning(f"Failed to clean up ConfigMap: {e}")
            
            # Parse and return the test results
            if success:
                try:
                    # Try to extract JSON test results from logs
                    # The format might need adjustment based on the actual test runner output
                    results_start = logs.find('{"status":')
                    if results_start >= 0:
                        results_json = logs[results_start:]
                        return json.loads(results_json)
                    else:
                        return {
                            "status": "pass",
                            "message": "Tests passed but no structured output found",
                            "raw_output": logs
                        }
                except Exception as e:
                    logger.error(f"Failed to parse test results: {e}")
                    return {
                        "status": "error",
                        "message": f"Error parsing test results: {str(e)}",
                        "raw_output": logs
                    }
            else:
                return {
                    "status": "fail",
                    "message": "Test execution failed",
                    "raw_output": logs
                }
                
        except Exception as e:
            logger.exception(f"Error running tests: {e}")
            return {
                "status": "error",
                "message": f"Error running tests: {str(e)}"
            }
