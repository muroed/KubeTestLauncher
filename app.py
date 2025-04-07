import os
import logging
from flask import Flask, request, jsonify, render_template
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.utils import secure_filename
import tempfile
import json

from runner_service import RunnerService
from k8s_client import K8sClient
from config import SUPPORTED_LANGUAGES
from utils import validate_test_config

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                   format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.environ.get("SESSION_SECRET")
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

# Initialize Kubernetes client
# Enable mock mode by default during development
is_mock_mode = os.environ.get("K8S_MOCK_MODE", "true").lower() in ("true", "1", "yes")
k8s_client = K8sClient(mock_mode=is_mock_mode)
runner_service = RunnerService(k8s_client)
logger.info(f"Kubernetes client initialized (mock mode: {is_mock_mode})")

@app.route('/', methods=['GET'])
def index():
    """Index page with API documentation."""
    api_docs = {
        'name': 'Exercism Test Runner API',
        'description': 'API service for orchestrating Exercism test runners in Kubernetes',
        'endpoints': {
            '/health': {
                'method': 'GET',
                'description': 'Health check endpoint'
            },
            '/api/{language}-test-runner/start': {
                'method': 'POST',
                'description': 'Run tests for a specific language',
                'required_files': ['code_file', 'test_config'],
                'supported_languages': list(SUPPORTED_LANGUAGES.keys())
            }
        },
        'version': '1.0.0'
    }
    return jsonify(api_docs)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint for the API service."""
    is_connected = k8s_client and k8s_client.is_connected()
    is_mock = k8s_client and getattr(k8s_client, 'mock_mode', False)
    
    health_status = {
        'status': 'ok',
        'kubernetes_client': 'ok (mock mode)' if is_mock else ('ok' if is_connected else 'error'),
        'supported_languages': list(SUPPORTED_LANGUAGES.keys()),
        'api_version': '1.0.0'
    }
    
    if not is_connected and not is_mock:
        return jsonify(health_status), 500
    
    return jsonify(health_status)

@app.route('/api/<language>-test-runner/start', methods=['POST'])
def run_tests(language):
    """
    API endpoint to run tests for a specific language.
    
    Accepts:
    - code file: The source code to test
    - test_config: JSON configuration for the tests
    
    Returns:
    - Test results in JSON format
    """
    if not runner_service:
        return jsonify({'error': 'Kubernetes client not initialized'}), 500
    
    # Check if language is supported
    if language not in SUPPORTED_LANGUAGES:
        return jsonify({
            'error': f'Unsupported language: {language}',
            'supported_languages': list(SUPPORTED_LANGUAGES.keys())
        }), 400
    
    # Check if files were uploaded
    if 'code_file' not in request.files or 'test_config' not in request.files:
        return jsonify({
            'error': 'Missing required files',
            'required': ['code_file', 'test_config']
        }), 400
    
    code_file = request.files['code_file']
    test_config_file = request.files['test_config']
    
    # Create temporary directory to store uploaded files
    with tempfile.TemporaryDirectory() as temp_dir:
        # Save the code file
        code_filename = secure_filename(code_file.filename)
        code_filepath = os.path.join(temp_dir, code_filename)
        code_file.save(code_filepath)
        
        # Save and parse the test configuration
        test_config_filename = secure_filename(test_config_file.filename)
        test_config_filepath = os.path.join(temp_dir, test_config_filename)
        test_config_file.save(test_config_filepath)
        
        try:
            with open(test_config_filepath, 'r') as f:
                test_config = json.load(f)
            
            # Validate test configuration
            if not validate_test_config(test_config, language):
                return jsonify({'error': 'Invalid test configuration'}), 400
            
            # Run the tests using the runner service
            logger.info(f"Starting test runner for {language}")
            result = runner_service.run_tests(
                language=language,
                code_filepath=code_filepath,
                test_config=test_config
            )
            
            return jsonify(result)
            
        except json.JSONDecodeError:
            return jsonify({'error': 'Invalid JSON in test configuration'}), 400
        except Exception as e:
            logger.exception(f"Error running tests: {e}")
            return jsonify({'error': f'Error running tests: {str(e)}'}), 500

@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors."""
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors."""
    return jsonify({"error": "Internal server error"}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
