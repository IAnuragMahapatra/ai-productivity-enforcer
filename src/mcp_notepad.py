import asyncio
import datetime
from pathlib import Path
from typing import List

from mcp.server.fastmcp import FastMCP

# --- Server and File Setup ---
mcp = FastMCP("Notepad")
NOTES_DIR = Path(__file__).parent.parent / "data" / "notes"


# --- Helper Function ---
def _ensure_notes_dir():
    """Creates the 'notes' directory if it doesn't exist."""
    NOTES_DIR.mkdir(exist_ok=True)


# --- MCP Tools ---


@mcp.tool()
def list_notes() -> List[str]:
    """
    Lists all available notes by their title.

    Returns:
        List[str]: A list of note titles (without the .md extension).
    """
    _ensure_notes_dir()
    notes = [f.stem for f in NOTES_DIR.glob("*.md")]
    return notes


@mcp.tool()
def create_note(title: str, content: str) -> str:
    """
    Creates a new note with a given title and initial content.

    Args:
        title (str): The title of the note. This will be the filename (e.g., "meeting_summary").
        content (str): The initial Markdown content for the note.

    Returns:
        str: A confirmation or error message.
    """
    _ensure_notes_dir()
    filepath = NOTES_DIR / f"{title}.md"
    if filepath.exists():
        return f"Error: A note with the title '{title}' already exists. Use 'overwrite_note' to replace it."
    filepath.write_text(content, encoding="utf-8")
    return f"Successfully created note: '{title}'."


@mcp.tool()
def read_note(title: str) -> str:
    """
    Reads and returns the full content of a specified note.

    Args:
        title (str): The title of the note to read.

    Returns:
        str: The content of the note, or an error message if not found.
    """
    _ensure_notes_dir()
    filepath = NOTES_DIR / f"{title}.md"
    try:
        return filepath.read_text(encoding="utf-8")
    except FileNotFoundError:
        return f"Error: Note with title '{title}' not found."


@mcp.tool()
def append_to_note(title: str, content: str) -> str:
    """
    Appends content to an existing note. Adds a newline before the new content.

    Args:
        title (str): The title of the note to append to.
        content (str): The Markdown content to add.

    Returns:
        str: A confirmation or error message.
    """
    _ensure_notes_dir()
    filepath = NOTES_DIR / f"{title}.md"
    if not filepath.exists():
        return f"Error: Note with title '{title}' not found. Create it first."
    with filepath.open("a", encoding="utf-8") as f:
        f.write(
            f"\n\n---\n*Appended on {datetime.date.today().isoformat()}*\n\n{content}"
        )
    return f"Successfully appended content to note '{title}'."


@mcp.tool()
def overwrite_note(title: str, new_content: str) -> str:
    """
    Completely overwrites an existing note with new content.

    Args:
        title (str): The title of the note to overwrite.
        new_content (str): The new content that will replace the old content.

    Returns:
        str: A confirmation or error message.
    """
    _ensure_notes_dir()
    filepath = NOTES_DIR / f"{title}.md"
    if not filepath.exists():
        return f"Error: Note with title '{title}' not found. Use 'create_note' instead."
    filepath.write_text(new_content, encoding="utf-8")
    return f"Successfully overwrote note: '{title}'."


# --- To run the server directly ---
if __name__ == "__main__":
    print("Starting Notepad MCP Server...")
    print("\n--- Available Tools ---")
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        print(f"- {tool.name}")
    print("\nConnect your multi-tool agent to use this server.")
    mcp.run()
