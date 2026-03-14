import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler

if getattr(sys, 'frozen', False):
    _app_dir = os.path.dirname(sys.executable)
else:
    _app_dir = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_app_dir, "logs")

_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = os.path.join(LOG_DIR, f"soundboard_{_timestamp}.log")


def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s.%(msecs)03d] %(levelname)-8s "
        "[%(name)s] %(filename)s:%(lineno)d %(funcName)s() — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.DEBUG)

    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(fmt)
    console_handler.setLevel(logging.WARNING)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(file_handler)
    root.addHandler(console_handler)

    # Clean up old log files, keep latest 10
    _cleanup_old_logs(keep=10)


def _cleanup_old_logs(keep=10):
    try:
        logs = sorted(
            [f for f in os.listdir(LOG_DIR) if f.startswith("soundboard_") and f.endswith(".log")],
            reverse=True,
        )
        for old in logs[keep:]:
            os.remove(os.path.join(LOG_DIR, old))
    except Exception:
        pass


def install_excepthook():
    """Replace sys.excepthook so uncaught exceptions are logged before crash."""
    logger = logging.getLogger("soundboard")

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
        try:
            from PySide6.QtWidgets import QMessageBox
            QMessageBox.critical(
                None,
                "SoundBoard Crash",
                f"An unexpected error occurred.\n\n"
                f"{exc_type.__name__}: {exc_value}\n\n"
                f"Log file: {LOG_FILE}",
            )
        except Exception:
            pass

    sys.excepthook = _hook
