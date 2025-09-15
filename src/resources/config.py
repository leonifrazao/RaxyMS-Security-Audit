"""Shared configuration and constants for browser automation.

Centralizes default arguments for the `@browser` decorator and
related helpers so other modules can import a single source of truth.
"""

# Default keyword arguments used by the botasaurus `@browser` decorator
BROWSER_KWARGS: dict = {
    "remove_default_browser_check_argument": True,
    "wait_for_complete_page_load": True,
    "block_images": True,
    "output": None,
    "tiny_profile": True,
}

