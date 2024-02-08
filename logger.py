import logging

from uvicorn.config import LOGGING_CONFIG as UVICORN_LOGGING_CONFIG

from config import DEBUG


class Colors:
    """ ANSI color codes """
    BLACK = "\033[0;30m"
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    BROWN = "\033[0;33m"
    BLUE = "\033[0;34m"
    PURPLE = "\033[0;35m"
    CYAN = "\033[0;36m"
    LIGHT_GRAY = "\033[0;37m"
    DARK_GRAY = "\033[1;30m"
    LIGHT_RED = "\033[1;31m"
    LIGHT_GREEN = "\033[1;32m"
    YELLOW = "\033[1;33m"
    LIGHT_BLUE = "\033[1;34m"
    LIGHT_PURPLE = "\033[1;35m"
    LIGHT_CYAN = "\033[1;36m"
    LIGHT_WHITE = "\033[1;37m"
    BOLD = "\033[1m"
    FAINT = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"
    BLINK = "\033[5m"
    NEGATIVE = "\033[7m"
    CROSSED = "\033[9m"
    END = "\033[0m"

    # cancel SGR codes if we don't write to a terminal
    if not __import__("sys").stdout.isatty():
        for _ in dir():
            if isinstance(_, str) and _[0] != "_":
                locals()[_] = ""
    else:
        # set Windows console in VT mode
        if __import__("platform").system() == "Windows":
            kernel32 = __import__("ctypes").windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            del kernel32


class LoggerFormatter(logging.Formatter):

    FORMATS = {
        logging.DEBUG: Colors.CYAN + '%(levelname)s: ' + Colors.END + "%(message)s",
        logging.INFO: Colors.BLUE + '%(levelname)s: ' + Colors.END + "%(message)s",
        logging.WARNING: Colors.YELLOW + '%(levelname)s: ' + Colors.END + "%(message)s",
        logging.ERROR: Colors.RED + '%(levelname)s: ' + Colors.END + "%(message)s",
        logging.CRITICAL: Colors.LIGHT_RED + '%(levelname)s: ' + Colors.END + "%(message)s",
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)


logger = logging.getLogger(__name__)
formatter = LoggerFormatter()

handler = logging.StreamHandler()
handler.setLevel(logging.DEBUG if DEBUG else logging.INFO)
handler.setFormatter(formatter)

UVICORN_LOGGING_CONFIG['formatters']['default'] = {
    '()': LoggerFormatter,
    'fmt': '%(levelprefix)s %(message)s'
}

logger.setLevel(logging.DEBUG if DEBUG else logging.INFO)
logger.addHandler(handler)

__all__ = [
    "logger"
]
