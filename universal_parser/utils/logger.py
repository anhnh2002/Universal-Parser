import logging
import sys

# Create console handler for your app logs
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s - %(filename)s:%(lineno)d - %(levelname)s - %(message)s',
    '%Y-%m-%d %H:%M:%S'
))

# Clear any existing handlers from the root logger
root = logging.getLogger()
for handler in root.handlers[:]:
    root.removeHandler(handler)

# Configure the root logger with your handler
root.addHandler(console_handler)
root.setLevel(logging.WARNING)  # Default level for third-party modules

# Create your application logger with INFO level
logger = logging.getLogger('universal_parser')
logger.setLevel(logging.INFO)

# Set explicit levels for libraries you want to silence
noisy_loggers = [
    'litellm', '_client', 'sse', 'cost_calculator', 
    'utils', 'client', 'mcp', 'uvicorn', 'fastapi',
    'openai', 'httpx', 'httpcore'
]

for log_name in noisy_loggers:
    logging.getLogger(log_name).setLevel(logging.ERROR)  # Only show errors and critical

def set_log_level(level: int) -> None:
    """Set the logging level for the application logger."""
    logger.setLevel(level)

# Function to demonstrate logger usage
def test_logging():
    logger.debug("This is a debug message")
    logger.debug("This is an info message")
    logger.warning("This is a warning message")
    logger.debug("This is an error message")

if __name__ == "__main__":
    test_logging() 