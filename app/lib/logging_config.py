import logging
import sys

from pythonjsonlogger import jsonlogger


class CustomJsonFormatter(jsonlogger.JsonFormatter):
    def add_fields(self, log_record, record, message_dict):
        super(CustomJsonFormatter, self).add_fields(log_record, record, message_dict)
        if not log_record.get('timestamp'):
            log_record['timestamp'] = record.created
        if log_record.get('level'):
            log_record['severity'] = log_record['level'].upper()
        else:
            log_record['severity'] = record.levelname

def setup_logging():
    """
    Set up logging to output structured JSON to stdout.
    """
    log_level = logging.INFO

    # Get the root logger
    root_logger = logging.getLogger()

    # Clear any existing handlers
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    root_logger.setLevel(log_level)

    # Use stdout for the log handler
    log_handler = logging.StreamHandler(sys.stdout)

    # Use our custom JSON formatter
    formatter = CustomJsonFormatter(
        '%(timestamp)s %(severity)s %(name)s %(message)s'
    )

    log_handler.setFormatter(formatter)
    root_logger.addHandler(log_handler)

    # Configure uvicorn loggers to use the same handler
    logging.getLogger("uvicorn").handlers = [log_handler]
    logging.getLogger("uvicorn.access").handlers = [log_handler]
    logging.getLogger("uvicorn.error").handlers = [log_handler]

    logging.info("Logging configured to output structured JSON to stdout.")
