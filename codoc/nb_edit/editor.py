"""Fast Jupyter notebook operations using JSON directly.

This module provides faster notebook loading and manipulation by using
the json module directly instead of the heavier nbformat library.
"""

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codoc.errors import CellNotFoundError, NotebookNotFoundError
from codoc.utils import strip_cell_id


# Pattern to match # @cell_id=some-id at the start of a line
CELL_ID_PATTERN = re.compile(r"^#\s*@cell_id\s*=\s*(\S+)\s*$")

# Pattern to match key=value in cell info comments (e.g., # failing=true)
# Allows optional space after # before the key
CELL_INFO_PATTERN = re.compile(r"^#\s*(\w+)\s*=\s*(.+?)\s*$")


def _strip_quotes(value: str) -> str:
    """
    Strip matching quotes from a value.

    If the value starts and ends with matching quotes (single or double),
    removes them. Otherwise returns the value unchanged.

    Args:
        value: The value to process

    Returns:
        The value with matching outer quotes removed if present

    Examples:
        _strip_quotes("'hello'") -> "hello"
        _strip_quotes('"world"') -> "world"
        _strip_quotes('no quotes') -> "no quotes"
        _strip_quotes('"mismatch\'') -> '"mismatch\''
    """
    if len(value) >= 2:
        if value.startswith("'") and value.endswith("'"):
            return value[1:-1]
        if value.startswith('"') and value.endswith('"'):
            return value[1:-1]
    return value


def parse_cell_info(source_lines: list[str]) -> tuple[str | None, dict[str, str], list[str]]:
    """
    Parse cell info (consecutive comment lines at the start).

    The cell must start with '#' (no blank lines before). All consecutive '#'
    lines form the cell info section. The first line must contain @cell_id=value.
    Remaining cell info lines are key=value attribute pairs.

    Args:
        source_lines: List of source code lines from a notebook cell

    Returns:
        Tuple of (cell_id, attributes_dict, remaining_lines)
        - cell_id: The extracted cell ID or None if not found
        - attributes_dict: Dict of key=value pairs from cell info
        - remaining_lines: Source lines with cell info removed

    Example:
        Input:  ["# @cell_id=example", "# failing=true", "", "print('hi')"]
        Output: ("example", {"failing": "true"}, ["print('hi')"])
    """
    if not source_lines or not source_lines[0].startswith("#"):
        return None, {}, source_lines

    # Find all consecutive comment lines (cell info)
    info_lines = []
    remaining_lines = list(source_lines)

    for line in source_lines:
        if line.startswith("#"):
            info_lines.append(line)
            remaining_lines.pop(0)
        else:
            break

    # First line must contain @cell_id
    cell_id = None
    attributes = {}

    if info_lines:
        first_line = info_lines[0].strip()
        match = CELL_ID_PATTERN.match(first_line)
        if match:
            cell_id = match.group(1)

    # Parse remaining info lines as key=value
    for line in info_lines[1:]:
        match = CELL_INFO_PATTERN.match(line.strip())
        if match:
            key, value = match.groups()
            # Strip matching quotes from value if present
            attributes[key] = _strip_quotes(value)

    return cell_id, attributes, remaining_lines


class NotebookDict(dict):
    """A dict subclass that provides attribute access for notebook data.

    This allows code like notebook.cells to work alongside notebook["cells"].
    Also recursively wraps nested cells and metadata.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._wrap_nested()

    def _wrap_nested(self):
        """Recursively wrap nested dicts and lists."""
        # Wrap cells list
        if "cells" in self and isinstance(self["cells"], list):
            self["cells"] = [NotebookDict(cell) if isinstance(cell, dict) else cell for cell in self["cells"]]

        # Wrap metadata dict
        if "metadata" in self and isinstance(self["metadata"], dict):
            self["metadata"] = NotebookDict(self["metadata"])

    def __getattr__(self, key: str) -> Any:
        try:
            return self[key]
        except KeyError:
            raise AttributeError(f"'{type(self).__name__}' object has no attribute '{key}'")

    def __setattr__(self, key: str, value: Any) -> None:
        self[key] = value


@dataclass
class CellInfo:
    """Information about a code cell with a @cell_id marker."""

    cell_id: str
    source: str  # Source code with @cell_id and cell info lines removed and whitespace trimmed
    full_source: list[str]  # Original source lines
    cell_index: int  # Index in the notebook
    attributes: dict[str, str]  # Parsed attributes from cell info comments (e.g., {"failing": "true"})


@dataclass
class CellOutput:
    """Output from executing a notebook cell."""

    text: str
    has_output: bool


def _normalize_source(source: str | list[str]) -> list[str]:
    """Normalize source to list of strings."""
    if isinstance(source, str):
        return source.split("\n")
    return source


def load_notebook(path: Path) -> NotebookDict:
    """
    Load a Jupyter notebook from a file using JSON.

    Args:
        path: Path to the .ipynb file

    Returns:
        NotebookDict (dict with attribute access) representing the notebook

    Raises:
        NotebookNotFoundError: If the file doesn't exist
    """
    path = Path(path)
    if not path.exists():
        raise NotebookNotFoundError(str(path))

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return NotebookDict(data)
    except json.JSONDecodeError as e:
        raise NotebookNotFoundError(f"Failed to load notebook: {e}")
    except Exception as e:
        raise NotebookNotFoundError(f"Failed to load notebook: {e}")


def save_notebook(notebook: NotebookDict, path: Path) -> None:
    """
    Save a notebook dictionary to a file.

    Args:
        notebook: The notebook dictionary
        path: Path to save the .ipynb file
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(notebook, f, indent=1, ensure_ascii=False)
        # Add trailing newline
        f.write("\n")


def find_cells_by_id(notebook: NotebookDict) -> dict[str, CellInfo]:
    """
    Find all code cells with @cell_id markers.

    Args:
        notebook: The notebook dictionary to search

    Returns:
        Dictionary mapping cell_id to CellInfo
    """
    cells_by_id = {}

    for idx, cell in enumerate(notebook.get("cells", [])):
        if cell.get("cell_type") != "code":
            continue

        source_lines = _normalize_source(cell.get("source", ""))

        # Parse cell info (id + attributes from consecutive # lines at start)
        cell_id, attributes, remaining_lines = parse_cell_info(source_lines)

        if cell_id:
            # Strip leading empty lines from remaining code
            cleaned_lines = list(remaining_lines)
            while cleaned_lines and not cleaned_lines[0].strip():
                cleaned_lines.pop(0)

            # Strip trailing whitespace (including newlines) from each line
            # Jupyter stores source with trailing newlines which causes double newlines when joined
            cleaned_lines = [line.rstrip("\r\n") for line in cleaned_lines]

            cells_by_id[cell_id] = CellInfo(
                cell_id=cell_id,
                source="\n".join(cleaned_lines),
                full_source=source_lines,
                cell_index=idx,
                attributes=attributes,
            )

    return cells_by_id


def get_cell_by_id(
    notebook: NotebookDict, cell_id: str, notebook_path: str
) -> CellInfo:
    """
    Get a specific cell by its @cell_id.

    Args:
        notebook: The notebook dictionary to search
        cell_id: The cell ID to find
        notebook_path: Path to notebook (for error messages)

    Returns:
        CellInfo for the requested cell

    Raises:
        CellNotFoundError: If the cell_id doesn't exist
    """
    cells = find_cells_by_id(notebook)

    if cell_id not in cells:
        raise CellNotFoundError(notebook_path, cell_id)

    return cells[cell_id]


def get_cell_output(cell: NotebookDict) -> CellOutput:
    """
    Extract the output from a cell as text.

    Args:
        cell: The cell dictionary to extract output from

    Returns:
        CellOutput with text representation of the output
    """
    outputs = cell.get("outputs", [])
    if not outputs:
        return CellOutput(text="", has_output=False)

    output_parts = []
    for output in outputs:
        output_type = output.get("output_type", "")

        if output_type == "stream":
            text = output.get("text", [])
            if isinstance(text, list):
                output_parts.append("".join(text))
            else:
                output_parts.append(text)
        elif output_type == "execute_result":
            data = output.get("data", {})
            if "text/plain" in data:
                text = data["text/plain"]
                if isinstance(text, list):
                    output_parts.append("".join(text))
                else:
                    output_parts.append(text)
        elif output_type == "error":
            traceback = "\n".join(output.get("traceback", []))
            output_parts.append(f"Error: {traceback}")

    # Trim empty/whitespace-only lines from the top and bottom of the joined
    # output, but preserve leading whitespace on the first real line — that
    # whitespace is meaningful when the code prints indented text.
    lines = "\n".join(output_parts).split("\n")
    start = 0
    end = len(lines)
    while start < end and lines[start].strip() == "":
        start += 1
    while end > start and lines[end - 1].strip() == "":
        end -= 1
    text = "\n".join(lines[start:end])
    return CellOutput(text=text, has_output=bool(text))


def create_notebook() -> NotebookDict:
    """Create a new empty notebook dictionary."""
    return NotebookDict({
        "cells": [],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3"
            },
            "language_info": {
                "name": "python",
                "version": "3.10.0"
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    })


def find_cell_index_by_id(cells: list[NotebookDict], cell_id: str) -> int | None:
    """Find the index of a cell by its @cell_id.

    Args:
        cells: List of cell dictionaries
        cell_id: The cell ID to find

    Returns:
        The 0-based index or None if not found
    """
    for i, cell in enumerate(cells):
        if cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, str):
            source_lines = source.split("\n")
        else:
            source_lines = source

        # Check first non-empty line for cell_id
        for line in source_lines:
            if not line.strip():
                continue
            if line.startswith("# @cell_id="):
                found_id = line[len("# @cell_id="):].strip()
                if found_id == cell_id:
                    return i
                break
    return None


class FastNotebookEditor:
    """Fast notebook editor using JSON directly."""

    def __init__(self, notebook: NotebookDict | None = None, path: Path | None = None):
        """
        Initialize the editor.

        Args:
            notebook: The notebook dictionary (optional, loads from path if not provided)
            path: Optional path to the notebook file
        """
        if notebook is None and path is not None:
            notebook = load_notebook(path)
        elif notebook is None:
            notebook = create_notebook()

        self.notebook = notebook
        self.path = path

    @staticmethod
    def load(path: Path) -> "FastNotebookEditor":
        """Load a notebook from a file."""
        notebook = load_notebook(path)
        return FastNotebookEditor(notebook, path)

    @staticmethod
    def create(path: Path) -> "FastNotebookEditor":
        """Create a new empty notebook."""
        notebook = create_notebook()
        return FastNotebookEditor(notebook, path)

    def save(self, path: Path | None = None) -> None:
        """Save the notebook to a file."""
        save_path = Path(path) if path else self.path
        if save_path is None:
            raise ValueError("No path specified")
        save_notebook(self.notebook, save_path)

    def save_as(self, path: Path) -> None:
        """Save the notebook to a new path."""
        self.save(path)

    def list(self, with_output: bool = False, limit: int = 10, line_numbers: bool = False) -> None:
        """List all cells in the notebook.

        Args:
            with_output: If True, show cell outputs
            limit: Max output lines per cell (only applies when with_output=True)
            line_numbers: If True, show line numbers for code cells
        """
        for i, cell in enumerate(self.notebook.get("cells", []), 1):
            cell_type = cell.get("cell_type", "unknown")
            source = cell.get("source", "")
            if isinstance(source, str):
                source_lines = source.split("\n")
            else:
                source_lines = source

            # Check for cell_id
            cell_id = None
            for line in source_lines:
                if not line.strip():
                    continue
                if line.startswith("# @cell_id="):
                    cell_id = line[len("# @cell_id="):].strip()
                    break
                break

            if cell_id:
                print(f"[{i}] {cell_type:8} | # @cell_id={cell_id}")
                # Remove cell_id line for display
                if source_lines and source_lines[0].startswith("# @cell_id="):
                    display_source = "\n".join(source_lines[1:]).lstrip()
                else:
                    display_source = "\n".join(source_lines)
            else:
                print(f"[{i}] {cell_type:8}")
                display_source = "\n".join(source_lines)

            if line_numbers and cell_type == "code":
                display_lines = display_source.split("\n")
                width = len(str(len(display_lines)))
                for line_num, line in enumerate(display_lines, 1):
                    print(f"{line_num:>{width}} | {line}")
            else:
                print(display_source)

            # Show output if requested
            if with_output and cell_type == "code":
                output = self._format_cell_output(cell, limit)
                if output:
                    print(f"Output: {output}")

            print()

    def get(self, cell_id: str, with_output: bool = False, limit: int = 10) -> None:
        """Get a specific cell by its @cell_id.

        Args:
            cell_id: The cell ID to retrieve
            with_output: If True, show cell output
            limit: Max output lines (only applies when with_output=True)

        Raises:
            ValueError: If the cell_id is not found
        """
        cells = self.notebook.get("cells", [])
        idx = find_cell_index_by_id(cells, cell_id)
        if idx is None:
            raise ValueError(f"Cell with @cell_id={cell_id} not found")

        cell = cells[idx]
        cell_type = cell.get("cell_type", "unknown")
        source = cell.get("source", "")
        if isinstance(source, str):
            source_lines = source.split("\n")
        else:
            source_lines = source

        # Print header with cell ID and index
        print(f"[{idx + 1}] {cell_type:8} | # @cell_id={cell_id}")

        # Print source (without cell_id line)
        if source_lines and source_lines[0].startswith("# @cell_id="):
            display_source = "\n".join(source_lines[1:]).lstrip()
        else:
            display_source = "\n".join(source_lines)
        print(display_source)

        # Show output if requested
        if with_output and cell_type == "code":
            output = self._format_cell_output(cell, limit)
            if output:
                print(f"Output: {output}")

    def _format_cell_output(self, cell: NotebookDict, limit: int) -> str:
        """Format cell output for display.

        Args:
            cell: The cell to get output from
            limit: Max lines to return

        Returns:
            Formatted output string (or type indicator for non-text outputs)
        """
        outputs = cell.get("outputs", [])
        if not outputs:
            return ""

        output_parts = []
        for output in outputs:
            output_type = output.get("output_type", "")

            if output_type == "stream":
                text = output.get("text", [])
                if isinstance(text, list):
                    text = "".join(text)
                output_parts.append(text)

            elif output_type == "execute_result":
                data = output.get("data", {})

                # Check for image data
                if "image/png" in data:
                    output_parts.append("[image/png]")
                    continue
                if "image/jpeg" in data:
                    output_parts.append("[image/jpeg]")
                    continue
                if "image/svg+xml" in data:
                    output_parts.append("[image/svg+xml]")
                    continue

                # Check for other binary/base64 data types
                for key in data:
                    if key.startswith("image/") or key.endswith("+json"):
                        output_parts.append(f"[{key}]")
                        break
                    if key == "application/vnd.dataresource+json":
                        output_parts.append("[data table]")
                        break
                else:
                    # Use text/plain if available
                    if "text/plain" in data:
                        text = data["text/plain"]
                        if isinstance(text, list):
                            text = "".join(text)
                        output_parts.append(text)

            elif output_type == "error":
                traceback = "\n".join(output.get("traceback", []))
                output_parts.append(f"Error: {traceback}")

        # Combine and limit
        full_text = "\n".join(output_parts).strip()
        if not full_text:
            return ""

        lines = full_text.split("\n")
        if len(lines) > limit:
            return "\n".join(lines[:limit]) + f"\n... ({len(lines) - limit} more lines)"
        return full_text

    def add_code(self, code: str, cell_id: str | None = None) -> None:
        """Add a code cell at the end."""
        code = code.strip()
        if cell_id:
            code = f"# @cell_id={cell_id}\n\n{code}"
        cell = {
            "cell_type": "code",
            "source": code,
            "metadata": {},
            "outputs": [],
            "execution_count": None
        }
        self.notebook.setdefault("cells", []).append(cell)

    def add_markdown(self, text: str) -> None:
        """Add a markdown cell at the end."""
        cell = {
            "cell_type": "markdown",
            "source": text.strip(),
            "metadata": {}
        }
        self.notebook.setdefault("cells", []).append(cell)

    def update_by_id(self, cell_id: str, code: str, keep_marker: bool = True) -> None:
        """Update a cell by its @cell_id."""
        cells = self.notebook.get("cells", [])
        idx = find_cell_index_by_id(cells, cell_id)
        if idx is None:
            raise ValueError(f"Cell with @cell_id={cell_id} not found")

        code = code.strip()
        if keep_marker:
            cells[idx]["source"] = f"# @cell_id={cell_id}\n\n{code}"
        else:
            cells[idx]["source"] = code

    def update_by_index(self, index: int, code: str) -> None:
        """Update a cell by index (1-based)."""
        cells = self.notebook.get("cells", [])
        if index < 1 or index > len(cells):
            raise ValueError(f"Cell index {index} out of range (1-{len(cells)})")
        cells[index - 1]["source"] = code.strip()

    def delete_by_id(self, cell_id: str) -> None:
        """Delete a cell with the given ID."""
        cells = self.notebook.get("cells", [])
        idx = find_cell_index_by_id(cells, cell_id)
        if idx is None:
            raise ValueError(f"Cell with @cell_id={cell_id} not found")
        cells.pop(idx)

    def delete_by_index(self, index: int) -> None:
        """Delete a cell by index (1-based)."""
        cells = self.notebook.get("cells", [])
        if index < 1 or index > len(cells):
            raise ValueError(f"Cell index {index} out of range (1-{len(cells)})")
        cells.pop(index - 1)

    def rename_id(self, old_id: str, new_id: str) -> None:
        """Rename a cell's @cell_id."""
        cells = self.notebook.get("cells", [])
        idx = find_cell_index_by_id(cells, old_id)
        if idx is None:
            raise ValueError(f"Cell with @cell_id={old_id} not found")

        source = cells[idx].get("source", "")
        source_was_string = isinstance(source, str)

        if source_was_string:
            lines = source.split("\n", 1)
        else:
            # source is a list - keep it as a list
            lines = list(source)  # Make a copy

        # Replace the first line (cell_id marker)
        if lines:
            lines[0] = f"# @cell_id={new_id}"

        # Preserve the original type (string or list)
        if source_was_string:
            cells[idx]["source"] = "\n".join(lines)
        else:
            cells[idx]["source"] = lines

    def add_id(self, cell_index: int, cell_id: str) -> None:
        """Add or replace @cell_id marker on a cell by index (1-based)."""
        cells = self.notebook.get("cells", [])
        if cell_index < 1 or cell_index > len(cells):
            raise ValueError(f"Cell index {cell_index} out of range (1-{len(cells)})")

        cell = cells[cell_index - 1]
        if cell.get("cell_type") != "code":
            raise ValueError(f"Cell {cell_index} is not a code cell")

        source = cell.get("source", "")
        source_was_string = isinstance(source, str)

        if source_was_string:
            source_lines = source.split("\n")
        else:
            # Source is a list of strings, each may end with \n - strip them
            source_lines = [line.rstrip("\n") for line in source]

        # Check for existing cell_id
        for i, line in enumerate(source_lines):
            if not line.strip():
                continue
            if line.startswith("# @cell_id="):
                # Replace existing - preserve rest of lines including blank line
                remaining = source_lines[i + 1:]
                # Preserve blank line after cell_id if it exists
                if remaining and remaining[0] == "":
                    cell["source"] = f"# @cell_id={cell_id}\n" + "\n".join(remaining)
                else:
                    # Add blank line after cell_id
                    cell["source"] = f"# @cell_id={cell_id}\n\n" + "\n".join(remaining)
                return
            break

        # Add new at beginning - add blank line after marker
        cell["source"] = f"# @cell_id={cell_id}\n\n" + "\n".join(source_lines)

    def insert_after_index(self, index: int, code: str, cell_id: str | None = None) -> None:
        """Insert a code cell after the given index (1-based)."""
        cells = self.notebook.get("cells", [])
        # Convert 1-based to 0-based insertion point
        # insert after cell N (1-based) means insert at index N in 0-based
        # E.g., insert after cell 1 (0-based idx 0) -> insert at 0-based idx 1
        # For empty cells or index 0, insert at beginning
        if index < 1 or index > len(cells):
            raise ValueError(f"Cell index {index} out of range (1-{len(cells)})")
        # Insert at the 0-based position equal to the 1-based index
        insert_idx = index
        code = code.strip()
        if cell_id:
            code = f"# @cell_id={cell_id}\n\n{code}"
        cell = {
            "cell_type": "code",
            "source": code,
            "metadata": {},
            "outputs": [],
            "execution_count": None
        }
        cells.insert(insert_idx, cell)

    def insert_after_id(self, after_id: str, code: str, cell_id: str | None = None) -> None:
        """Insert a code cell after the cell with the given ID."""
        cells = self.notebook.get("cells", [])
        target_idx = find_cell_index_by_id(cells, after_id)
        insert_idx = target_idx + 1 if target_idx is not None else len(cells)

        code = code.strip()
        if cell_id:
            code = f"# @cell_id={cell_id}\n\n{code}"
        cell = {
            "cell_type": "code",
            "source": code,
            "metadata": {},
            "outputs": [],
            "execution_count": None
        }
        cells.insert(insert_idx, cell)

    def move_id_after_id(self, cell_id: str, after_id: str) -> None:
        """Move a cell (by ID) to after another cell (by ID)."""
        cells = self.notebook.get("cells", [])
        cell_idx = find_cell_index_by_id(cells, cell_id)
        if cell_idx is None:
            raise ValueError(f"Cell with @cell_id={cell_id} not found")

        target_idx = find_cell_index_by_id(cells, after_id)
        if target_idx is None:
            return

        if cell_idx == target_idx + 1:
            return

        cell = cells.pop(cell_idx)
        if cell_idx < target_idx:
            insert_idx = target_idx
        else:
            insert_idx = target_idx + 1
        cells.insert(insert_idx, cell)

    def extract_image(
        self,
        identifier: str,
        output_path: Path,
        format: str = "jpg",
        quality: int = 85,
    ) -> None:
        """Extract an image from a cell's output and save it to a file.

        Args:
            identifier: Cell index (number, 1-based) or ID
            output_path: Path where to save the image file
            format: Image format - "jpg" or "png" (default: "jpg")
            quality: JPEG quality (1-100, default: 85). Only used for jpg format.

        Raises:
            ValueError: If cell not found or has no image output
        """
        cells = self.notebook.get("cells", [])

        # Find the cell by index or ID
        if identifier.isdigit():
            idx = int(identifier) - 1
            if idx < 0 or idx >= len(cells):
                raise ValueError(f"Cell index {identifier} out of range (1-{len(cells)})")
            cell = cells[idx]
        else:
            idx = find_cell_index_by_id(cells, identifier)
            if idx is None:
                raise ValueError(f"Cell with @cell_id={identifier} not found")
            cell = cells[idx]

        # Extract image from outputs
        outputs = cell.get("outputs", [])
        if not outputs:
            raise ValueError(f"Cell has no output")

        image_data = None
        image_mimetype = None

        for output in outputs:
            output_type = output.get("output_type", "")
            if output_type == "execute_result":
                data = output.get("data", {})

                # Look for image data in order of preference
                for mimetype in ["image/png", "image/jpeg"]:
                    if mimetype in data:
                        image_data = data[mimetype]
                        image_mimetype = mimetype
                        break
                if image_data:
                    break

        if not image_data:
            raise ValueError(f"Cell has no image output (no image/png or image/jpeg found)")

        # Decode base64 data
        if isinstance(image_data, list):
            image_data = "".join(image_data)

        try:
            binary_data = base64.b64decode(image_data)
        except Exception as e:
            raise ValueError(f"Failed to decode base64 image data: {e}")

        # Determine output format and mimetype
        format = format.lower()
        if format == "jpg" or format == "jpeg":
            save_format = "JPEG"
            output_mimetype = "image/jpeg"
        elif format == "png":
            save_format = "PNG"
            output_mimetype = "image/png"
        else:
            raise ValueError(f"Unsupported format: {format}. Use 'jpg' or 'png'")

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Use PIL to save the image with appropriate format/quality
        try:
            from io import BytesIO
            from PIL import Image

            img = Image.open(BytesIO(binary_data))

            # Convert mode if necessary (e.g., RGBA to RGB for JPEG)
            if save_format == "JPEG" and img.mode in ("RGBA", "LA", "P"):
                # Create white background for transparency
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                if img.mode in ("RGBA", "LA"):
                    background.paste(img, mask=img.split()[-1])
                    img = background
                else:
                    img = img.convert("RGB")

            save_kwargs = {}
            if save_format == "JPEG":
                save_kwargs["quality"] = quality

            img.save(output_path, save_format, **save_kwargs)
        except ImportError:
            raise ValueError("PIL/Pillow is required to save images. Install with: pip install pillow")
        except Exception as e:
            raise ValueError(f"Failed to save image: {e}")

    def remove_all_ids(self) -> int:
        """Remove all @cell_id markers from code cells.

        Returns:
            The number of cell_id markers that were removed
        """
        count = 0
        cells = self.notebook.get("cells", [])

        for cell in cells:
            if cell.get("cell_type") != "code":
                continue

            source = cell.get("source", "")
            source_was_string = isinstance(source, str)

            if source_was_string:
                source_lines = source.split("\n")
            else:
                source_lines = [line.rstrip("\n") for line in source]

            # Check if first non-empty line is a cell_id marker
            first_non_empty_idx = None
            for i, line in enumerate(source_lines):
                if line.strip():
                    first_non_empty_idx = i
                    break

            if first_non_empty_idx is not None:
                line = source_lines[first_non_empty_idx]
                if line.startswith("# @cell_id="):
                    # Remove the cell_id line
                    source_lines.pop(first_non_empty_idx)

                    # Also remove blank line immediately after if it exists
                    if first_non_empty_idx < len(source_lines) and source_lines[first_non_empty_idx].strip() == "":
                        source_lines.pop(first_non_empty_idx)

                    # Update the source
                    if source_was_string:
                        cell["source"] = "\n".join(source_lines)
                    else:
                        cell["source"] = source_lines
                    count += 1

        return count
