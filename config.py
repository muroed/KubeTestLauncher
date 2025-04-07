"""
Configuration for test runner orchestrator.
"""

# Supported languages and their configurations
SUPPORTED_LANGUAGES = {
    'python': {
        'image': 'exercism/python-test-runner:latest',
        'file_extension': 'py',
        'timeout': 60,  # seconds
    },
    # Additional language configurations can be added here
    # 'ruby': {
    #     'image': 'exercism/ruby-test-runner:latest',
    #     'file_extension': 'rb',
    #     'timeout': 60,
    # },
    # 'javascript': {
    #     'image': 'exercism/javascript-test-runner:latest',
    #     'file_extension': 'js',
    #     'timeout': 60, 
    # },
}

# Kubernetes namespace for test runners
DEFAULT_NAMESPACE = 'exercism-test-runners'

# Job execution timeout (seconds)
DEFAULT_TIMEOUT = 120

# Cleanup settings
CLEANUP_COMPLETED_JOBS = True
CLEANUP_FAILED_JOBS = True
JOB_TTL_SECONDS = 300  # 5 minutes

# API settings
API_RATE_LIMIT = 100  # requests per minute
