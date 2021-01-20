import logging
import os

import coloredlogs


def make_logger(sublogger_name: str = None):
    logger_name = "np_web_api"

    if sublogger_name:
        logger_name = f"{logger_name}.{sublogger_name}"

    return logging.getLogger(logger_name)


def configure_logging(level: int = None):
    # default to info level
    if level is None:
        level = logging.INFO

    force_colors = "FORCE_COLORS" in os.environ

    fmt = "%(asctime)s,%(msecs)03d %(name)s [%(levelname)s] %(message)s"

    # define nicer colors
    styles = coloredlogs.DEFAULT_FIELD_STYLES
    styles["pathname"] = {
        "color": "magenta",
    }
    styles["levelname"] = {
        "color": "cyan",
    }

    kwargs = {}

    if force_colors:
        kwargs["isatty"] = True

    base_logger = make_logger()

    coloredlogs.install(level=level, fmt=fmt, logger=base_logger, **kwargs)

    # silence the annoying asyncio loggers
    logging.getLogger("asyncio").disabled = True
