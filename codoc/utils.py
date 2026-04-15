"""Utility functions for the codoc tool."""

import re
import sys
from pathlib import Path


def set_terminal_title(title: str) -> None:
    """
    Set the terminal window title.

    Tries multiple methods:
    1. Windows API (SetConsoleTitleW) for cmd.exe
    2. OSC escape sequence for xterm, GNOME Terminal, Windows Terminal, etc.
    3. title command for Windows cmd.exe

    Note: Git Bash/mintty doesn't support OSC sequences properly, so title
    changes won't be visible there. Use Windows Terminal, PowerShell, or cmd.exe.

    Args:
        title: The title to set
    """
    import os

    # Method 1: Windows API (works for cmd.exe, some Windows terminals)
    if os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW(title)
        except Exception:
            pass

    # Method 2: OSC escape sequence for terminals that support it
    # This works in Windows Terminal, PowerShell, xterm, GNOME Terminal, etc.
    # It does NOT work in Git Bash/mintty - the sequence just gets ignored
    osc_sequence = f"\x1b]0;{title}\x07"
    try:
        sys.stdout.write(os.linesep + osc_sequence + "\r")
        sys.stdout.flush()
    except Exception:
        pass

    # Method 3: For Windows cmd.exe, try the title command
    if os.name == 'nt':
        try:
            import subprocess
            subprocess.run(f'title "{title}"', shell=True, capture_output=True)
        except Exception:
            pass


def strip_cell_id(source: list[str]) -> list[str]:
    """
    Remove the @cell_id line from cell source and strip surrounding whitespace.

    Args:
        source: List of source code lines from a notebook cell

    Returns:
        List of lines with @cell_id removed and leading/trailing empty lines stripped
    """
    # Filter out the cell_id marker line (allow optional whitespace around =)
    lines = [line for line in source if not re.match(r"^#\s*@cell_id\s*=\s*\S+", line)]

    # Strip trailing whitespace (including newlines) from each line
    # Jupyter stores source with trailing newlines which causes issues when joining
    lines = [line.rstrip("\r\n") for line in lines]

    # Strip leading empty lines
    while lines and not lines[0].strip():
        lines.pop(0)

    # Strip trailing empty lines
    while lines and not lines[-1].strip():
        lines.pop()

    return lines


def strip_try_except(source: str) -> str:
    """
    Strip try/except wrapper from code and de-indent.

    Handles patterns like:
        try:
            code here
        except Exception as e:
            print(e)

    Args:
        source: Source code that may be wrapped in try/except

    Returns:
        Unwrapped code with indentation reduced by 4 spaces (or 2 if 4 not found)
    """
    lines = source.split("\n")
    if not lines:
        return source

    # Check if starts with try:
    first_line = lines[0].strip()
    if not first_line.startswith("try:"):
        return source

    # Find the indentation level by looking at the first non-empty line after try:
    indent_to_remove = "    "  # Default to 4 spaces
    for line in lines[1:]:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("except "):
            break
        # Found the first line of code - detect its indentation
        if line.startswith("\t"):
            indent_to_remove = "\t"
        elif line.startswith("  ") and not line.startswith("    "):
            indent_to_remove = "  "
        break

    # Process lines: skip first (try:) and stop at except clause
    # Remove indent from remaining lines
    result_lines = []

    for i, line in enumerate(lines[1:], start=1):
        # Stop at except clause (or bare except)
        stripped = line.strip()
        if stripped.startswith("except"):
            break
        # Preserve empty lines as-is
        if not line:
            result_lines.append(line)
        # Remove the indent from non-empty lines
        elif line.startswith(indent_to_remove):
            result_lines.append(line[len(indent_to_remove):])
        elif stripped:  # Non-empty line without expected indent
            result_lines.append(line)

    # Strip leading/trailing empty lines from result
    while result_lines and not result_lines[0].strip():
        result_lines.pop(0)
    while result_lines and not result_lines[-1].strip():
        result_lines.pop()

    return "\n".join(result_lines)


def join_lines(lines: list[str]) -> str:
    """Join lines with newline characters."""
    return "\n".join(lines)


def find_template_files(directory: Path) -> list[Path]:
    """
    Recursively find all *.template.md files in a directory.

    Args:
        directory: Root directory to search

    Returns:
        List of Path objects for each template file found
    """
    return sorted(directory.rglob("*.template.md"))


def resolve_notebook_path(template_path: Path, notebook_rel_path: str) -> Path:
    """
    Resolve a notebook path relative to a template file.

    Args:
        template_path: Path to the template file
        notebook_rel_path: Relative path from template to notebook

    Returns:
        Absolute Path to the notebook
    """
    return (template_path.parent / notebook_rel_path).resolve()
