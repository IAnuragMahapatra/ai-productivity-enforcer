import asyncio
import json
from pathlib import Path
from typing import Any, List

from mcp.server.fastmcp import FastMCP

# --- Server and File Setup ---

mcp = FastMCP("Memory Store")
MEMORY_FILE = Path(__file__).parent.parent / "data" / "memory.json"


# --- Helper Functions ---
def _load_data() -> dict:
    """Loads memory data from the JSON file."""
    try:
        if MEMORY_FILE.exists() and MEMORY_FILE.stat().st_size > 0:
            with MEMORY_FILE.open("r") as f:
                return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return {}


def _save_data(data: dict):
    """Saves the memory data back to the JSON file."""
    with MEMORY_FILE.open("w") as f:
        json.dump(data, f, indent=2)


# --- MCP Tools ---


@mcp.tool()
def remember(key: str, value: Any) -> str:
    """
    Stores or updates a piece of information (a value) under a specific key.

    Args:
        key (str): The unique identifier for the information (e.g., "favorite_color", "api_key_x").
        value (Any): The information to store. Can be a string, number, list, or dictionary.

    Returns:
        str: A confirmation message.
    """
    data = _load_data()
    data[key] = value
    _save_data(data)
    return f"OK, I've remembered the value for '{key}'."


@mcp.tool()
def recall(key: str) -> Any:
    """
    Warning: Only call this tool after calling `list_memories` to ensure the key exists.
    Retrieves a piece of information that was stored under a specific key.

    Args:
        key (str): The unique identifier for the information to retrieve.

    Returns:
        Any: The stored value, or a JSON object with an error if the key is not found.
    """
    data = _load_data()
    value = data.get(key)
    if value is not None:
        return value
    else:
        return {"error": f"I don't have anything stored under the key '{key}'."}


@mcp.tool()
def forget(key: str) -> str:
    """
    Deletes a piece of information stored under a specific key.

    Args:
        key (str): The unique identifier for the information to forget.

    Returns:
        str: A confirmation message, whether the key existed or not.
    """
    data = _load_data()
    if key in data:
        del data[key]
        _save_data(data)
        return f"OK, I've forgotten the value for '{key}'."
    else:
        return f"Nothing to forget. I didn't have a value for '{key}'."


@mcp.tool()
def list_memories() -> List[str]:
    """
    Lists all the keys currently stored in memory.

    Returns:
        List[str]: A list of all keys.
    """
    data = _load_data()
    return list(data.keys())


# --- To run the server directly ---
if __name__ == "__main__":
    print("Starting Memory Store MCP Server...")
    print("\n--- Available Tools ---")
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        print(f"- {tool.name}")
    print("\nConnect your multi-tool agent to use this server.")
    mcp.run()
