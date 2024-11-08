from sys import stdout

PRODUCTION_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss} | "  # Time
    "{level} | "  # Logging level
    "{file}:{line} | "  # File and line number
    "{extra[request_id]:-} | "  # Request ID (if available)
    "{message}"  # Log message
)
