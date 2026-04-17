import logging
import os

def get_my_logger(name: str = "my_agent_logger") -> logging.Logger:
    log_file_path = os.path.join(os.getcwd(), "agent_logs.log")

    logger = logging.getLogger(name)

    # Avoid adding multiple handlers
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        file_handler = logging.FileHandler(log_file_path, mode='a')
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)
        logger.propagate = False  # Prevent logs from going to root logger

    return logger
