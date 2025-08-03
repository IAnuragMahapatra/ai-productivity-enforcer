import asyncio
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Prompt")

PROMPT_DATA_DIR = Path(__file__).parent.parent / "data"
LOGIC_PROMPT_FILE = PROMPT_DATA_DIR / "system.md"
BELPHIE_PROMPT_FILE = PROMPT_DATA_DIR / "belphie.md"


@mcp.tool()
def get_prompt() -> str:
    """
    When user sends "/prompt" or "\\prompt" or "/<persona>" or "\\<persona>" command, directly call this tool without mentioning "now I will...".
    here <persona> is the name of the persona, e.g. "Belphie".
    Returns the system prompt for the Productivity Assistant.
    WARNING: Never call this tool without users request.
    Note: if the command is with persona name, call the corresponding
    persona prompt tool after this one.
    then IMMEDIATELY begin Step 1 of the prompt — don't explain the content of the prompt/prompts or acknowledge recieving them.
    """
    try:
        # Ensure the 'data' directory and the prompt file exist.
        if not LOGIC_PROMPT_FILE.is_file():
            return "Error: prompt file not found."

        with LOGIC_PROMPT_FILE.open("r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        return f"Error: Could not read the prompt file. Reason: {e}"


@mcp.tool()
def get_belphie_prompt() -> str:
    """
    When user sends "/belphie" or "\belphie" command, first call the "get_prompt()" tool, then this tool without mentioning "now I will...".
    then IMMEDIATELY begin Step 1 of the prompt — don't explain the content of the prompt/prompts or acknowledge recieving them.
    also consistently adhere to the Belphie persona throughout the interaction.

    Returns the prompt for the 'Belphie' persona.

    This prompt defines the assistant's communication style, tone, and specific
    phrasing. It should be called at the beginning of a session whenever the
    user invokes the 'Belphie' persona, establishing the
    demonic servant character for the interaction.
    """
    try:
        if not BELPHIE_PROMPT_FILE.is_file():
            return "Error: prompt file not found."

        with BELPHIE_PROMPT_FILE.open("r", encoding="utf-8") as f:
            return f.read()

    except Exception as e:
        return f"Error: Could not read the prompt file. Reason: {e}"


if __name__ == "__main__":
    print("Starting MCP Prompt Server...")
    print("\n--- Available Tools ---")
    tools = asyncio.run(mcp.list_tools())
    for tool in tools:
        print(f"- {tool.name}")
    print("\nConnect your multi-tool agent to use this server.")
    mcp.run()
