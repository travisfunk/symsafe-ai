"""
config.py — Application configuration, path resolution, and API client initialization.

Handles environment variable loading from .env, resolves the project root
directory for consistent file access across modules, and provides factory
functions for the Anthropic client and base prompt.
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from anthropic import Anthropic

# Project root directory (parent of the symsafe/ package).
# All file paths (prompts/, logs/, reports/) are resolved relative to this.
BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

# Path to the SQLite database for session persistence and clinician review.
DB_PATH = BASE_DIR / "data" / "symsafe.db"


def get_client():
    """Create and return an Anthropic API client using the configured API key.

    Returns:
        Anthropic: An initialized Anthropic client instance.
    """
    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def load_base_prompt():
    """Load the system prompt from prompts/base_prompt.txt.

    Returns:
        str: The full text of the base system prompt.

    Raises:
        FileNotFoundError: If prompts/base_prompt.txt does not exist.
    """
    prompt_path = BASE_DIR / "prompts" / "base_prompt.txt"
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()
