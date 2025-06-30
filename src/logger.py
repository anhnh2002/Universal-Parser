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
logger = logging.getLogger('my_app')
logger.setLevel(logging.INFO)
# Don't add the handler to your logger - it will inherit from root
# logger.addHandler(console_handler)  # Remove this line!

# Set explicit levels for libraries you want to silence
noisy_loggers = [
    'litellm', '_client', 'sse', 'cost_calculator', 
    'utils', 'client', 'mcp', 'uvicorn', 'fastapi'
]

for log_name in noisy_loggers:
    logging.getLogger(log_name).setLevel(logging.ERROR)  # Only show errors and critical

# Function to demonstrate logger usage
def test_logging():
    logger.debug("This is a debug message")
    logger.info("This is an info message")
    logger.warning("This is a warning message")
    logger.error("This is an error message")

if __name__ == "__main__":
    test_logging()