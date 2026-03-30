"""Crash reporting — unconditionally writes a timestamped report on any error.

Crash files are always written regardless of DEBUG setting so that errors are
never silently lost, even in production installs where file logging is off.
"""

import traceback
from datetime import datetime, timezone
from logging import getLogger
from pathlib import Path

import platformdirs

logger = getLogger(__name__)

_GITHUB_ISSUES_URL = "https://github.com/tedivm/oscilla/issues"


def write_crash_report(exc: BaseException) -> Path:
    """Write a timestamped crash report file and return its path.

    Uses exc.__traceback__ directly so this can be called from any context,
    not only from inside an active except block.
    """
    timestamp = datetime.now(tz=timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    crash_path = platformdirs.user_data_path("oscilla") / f"oscilla-crash-{timestamp}.log"
    tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    # Add extra details for CSS parse errors
    extra_info = ""
    if exc.__class__.__name__ == "StylesheetParseError":
        extra_info += f"\n\nCSS PARSE ERROR DETAILS:\n{'=' * 30}\n"
        extra_info += f"Exception type: {type(exc)}\n"

        # Try to extract detailed error information from StylesheetErrors object
        if hasattr(exc, "errors"):
            errors_obj = exc.errors
            extra_info += f"Errors object type: {type(errors_obj)}\n"

            # The StylesheetErrors object is likely Rich renderable - try to get plain text
            try:
                # Try Rich Console to render to plain text
                from rich.console import Console

                console = Console(file=None, force_terminal=False, legacy_windows=False)
                with console.capture() as capture:
                    console.print(errors_obj)
                plain_errors = capture.get()
                extra_info += f"Rendered error details:\n{plain_errors}\n"
            except Exception as render_exc:
                extra_info += f"Could not render errors with Rich: {render_exc}\n"

            # Try alternative approaches
            try:
                # Check if it has a __rich__ or __rich_console__ method
                if hasattr(errors_obj, "__rich__"):
                    rich_output = errors_obj.__rich__()
                    extra_info += f"Rich output: {rich_output}\n"
                elif hasattr(errors_obj, "__rich_console__"):
                    # This would need a console parameter but try anyway
                    extra_info += "Has __rich_console__ method\n"
            except Exception as rich_exc:
                extra_info += f"Could not access rich methods: {rich_exc}\n"

            # Try to access internal attributes that might contain the actual errors
            try:
                for attr in dir(errors_obj):
                    if not attr.startswith("_") and attr not in ["render", "__rich__", "__rich_console__"]:
                        try:
                            attr_value = getattr(errors_obj, attr)
                            if callable(attr_value):
                                # Try calling methods with no args
                                try:
                                    result = attr_value()
                                    extra_info += f"Method {attr}(): {result}\n"
                                except Exception:
                                    extra_info += f"Method {attr}(): <callable>\n"
                            else:
                                extra_info += f"Attribute {attr}: {attr_value}\n"
                        except Exception as attr_exc:
                            extra_info += f"Could not access {attr}: {attr_exc}\n"
            except Exception as dir_exc:
                extra_info += f"Could not inspect object: {dir_exc}\n"

        if hasattr(exc, "error_renderable"):
            extra_info += f"Error renderable: {exc.error_renderable}\n"

    crash_content = f"Oscilla crash report\nTimestamp : {timestamp}\nReport at : {_GITHUB_ISSUES_URL}\n{'=' * 60}\n{tb_text}{extra_info}"
    crash_path.write_text(crash_content, encoding="utf-8")
    logger.error("Crash report written to %s", crash_path)
    return crash_path
