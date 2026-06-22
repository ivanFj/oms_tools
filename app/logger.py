import logging

def set_logger_config(fn, level = logging.INFO, encoding = "utf-8", filemode = "a", format = "{asctime}:{levelname}: {message}", style = "{", datefmt = "%Y-%m-%d %H:%M:%S", **kwargs):
    logging.basicConfig(
        level = level,
        filename = fn,
        encoding = encoding,
        filemode = filemode,
        format = format,
        style = style, # type: ignore
        datefmt = datefmt,
        **kwargs
    )

def info(message, **kwargs):
    logging.info(message, **kwargs)

def debug(message, **kwargs):
    logging.debug(message, **kwargs)

def warning(message, **kwargs):
    logging.warning(message, **kwargs)

def error(message, **kwargs):
    logging.error(message, exc_info = True, **kwargs)

def critical(message, **kwargs):
    logging.critical(message, exc_info = True, **kwargs)