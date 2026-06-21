"""Small logging helper so module logs reach stdout (and Railway) at INFO.

uvicorn does not lower the root logger to INFO, so app-module `logger.info(...)`
calls are otherwise swallowed. This attaches a stdout handler once per logger.
"""

import logging


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
