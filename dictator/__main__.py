"""Entry point for Dictator: CLI arg parsing, exception boundary, crash reporting."""

from __future__ import annotations

import argparse
import sys
import traceback
from datetime import datetime
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dictator - Privacy-first voice assistant"
    )
    parser.add_argument(
        "--device", type=str, default=None,
        help="Microphone device name or index",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Whisper model size (tiny.en, base.en, small.en, medium.en)",
    )
    parser.add_argument(
        "--no-partial", action="store_true",
        help="Disable live partial typing during dictation",
    )
    parser.add_argument(
        "--log-level", type=str, default=None,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity level",
    )
    parser.add_argument(
        "--first-run", action="store_true",
        help="Force the first-run setup wizard",
    )
    return parser.parse_args()


def _crash_report(error: Exception) -> None:
    """Write crash report to disk and show a user-friendly error message."""
    from dictator.utils.paths import get_app_data_dir

    crash_path = get_app_data_dir() / "crash_report.txt"
    try:
        crash_path.write_text(
            f"Dictator crashed at {datetime.now().isoformat()}\n"
            f"Python {sys.version}\n"
            f"Platform: {sys.platform}\n\n"
            f"{traceback.format_exc()}",
            encoding="utf-8",
        )
    except Exception:
        pass

    # Try to show a GUI error dialog
    try:
        import tkinter as tk
        import tkinter.messagebox as mb
        root = tk.Tk()
        root.withdraw()
        mb.showerror(
            "Dictator - Error",
            f"An unexpected error occurred:\n\n{error}\n\n"
            f"Crash report saved to:\n{crash_path}",
        )
        root.destroy()
    except Exception:
        print(f"\nDictator crashed: {error}", file=sys.stderr)
        print(f"Crash report: {crash_path}", file=sys.stderr)


def main() -> None:
    args = parse_args()

    # Setup logging first
    from dictator.core.logging import setup_logging
    from dictator.core.config import AppConfig

    config = AppConfig.load()
    log_level = args.log_level or config.log_level
    setup_logging(level=log_level)

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Dictator starting...")

    # First-run wizard
    if not config.first_run_complete or args.first_run:
        try:
            from dictator.ui.first_run import FirstRunWizard

            completed = False

            def on_complete():
                nonlocal completed
                completed = True

            wizard = FirstRunWizard(on_complete=on_complete)
            wizard.show()

            if completed:
                config.first_run_complete = True
                config.save()
        except Exception as e:
            logger.warning(f"First-run wizard failed: {e}")
            config.first_run_complete = True
            config.save()

    # Build and start the app
    from dictator.app import AppBuilder

    try:
        builder = AppBuilder().with_config(config)

        if args.device:
            builder = builder.with_device(args.device)
        if args.model:
            builder = builder.with_model(args.model)
        if args.no_partial:
            builder = builder.with_partial_typing(False)

        app = builder.build()
        app.start()

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        _crash_report(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
