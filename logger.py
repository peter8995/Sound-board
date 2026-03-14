import logging
import os
import sys
from logging.handlers import RotatingFileHandler

if getattr(sys, 'frozen', False):
    _app_dir = os.path.dirname(sys.executable)
else:
    _app_dir = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(_app_dir, "logs")
LOG_FILE = os.path.join(LOG_DIR, "soundboard.log")

def setup_logging():
    os.makedirs(LOG_DIR, exist_ok=True)

    fmt = logging.Formatter(
        "[%(asctime)s] %(levelname)s %(name)s: %(message)s",
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


def install_excepthook():
    """Replace sys.excepthook so uncaught exceptions are logged before crash."""
    logger = logging.getLogger("soundboard")

    def _hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return
        logger.critical("Uncaught exception", exc_info=(exc_type, exc_value, exc_tb))
        # Try to show a dialog (best-effort; app may already be broken)
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