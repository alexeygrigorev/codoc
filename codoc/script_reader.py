"""Parse script files for block markers and extract code blocks."""

import re
from dataclasses import dataclass
from pathlib import Path

from codoc.errors import BlockNotFoundError, ScriptNotFoundError

# Pattern to match # @block=name
BLOCK_START_PATTERN = re.compile(r"^#\s*@block\s*=\s*(\S+)\s*$")

# Pattern to match # @end
BLOCK_END_PATTERN = re.compile(r"^#\s*@end\s*$")


@dataclass
class BlockInfo:
    """Information about a parsed block from a script file."""

    block_id: str
    source: str  # Content without markers, trimmed
    full_source: list[str]  # Original lines including markers
    start_line: int  # 1-indexed line number of the block start marker
    end_line: int  # 1-indexed line number of the block end marker


def parse_script_blocks(file_path: Path) -> dict[str, BlockInfo]:
    """
    Parse a script file and extract all blocks marked with # @block=name / # @end.

    Args:
        file_path: Path to the script file

    Returns:
        Dictionary mapping block_id -> BlockInfo

    Raises:
        ScriptNotFoundError: If the file doesn't exist
        ParseError: If blocks are malformed (unclosed, nested, duplicate IDs)
    """
    from codoc.errors import ParseError

    if not file_path.exists():
        raise ScriptNotFoundError(str(file_path))

    try:
        lines = file_path.read_text(encoding="utf-8").splitlines()
    except OSError as e:
        raise ScriptNotFoundError(f"{file_path}: {e}")

    blocks: dict[str, BlockInfo] = {}
    current_block_id: str | None = None
    current_block_start: int = 0
    current_block_lines: list[str] = []
    current_full_lines: list[str] = []

    for line_num, line in enumerate(lines, start=1):
        start_match = BLOCK_START_PATTERN.match(line.strip())
        end_match = BLOCK_END_PATTERN.match(line.strip())

        if start_match:
            if current_block_id is not None:
                raise ParseError(
                    str(file_path),
                    f"Nested block '{start_match.group(1)}' found inside block "
                    f"'{current_block_id}' at line {line_num}",
                )

            block_id = start_match.group(1)
            if block_id in blocks:
                raise ParseError(
                    str(file_path),
                    f"Duplicate block ID '{block_id}' at line {line_num}",
                )

            current_block_id = block_id
            current_block_start = line_num
            current_block_lines = []
            current_full_lines = [line]

        elif end_match:
            if current_block_id is None:
                raise ParseError(
                    str(file_path),
                    f"Found # @end without matching # @block at line {line_num}",
                )

            current_full_lines.append(line)

            # Trim the source content (remove leading/trailing blank lines)
            source = "\n".join(current_block_lines).strip()

            blocks[current_block_id] = BlockInfo(
                block_id=current_block_id,
                source=source,
                full_source=current_full_lines,
                start_line=current_block_start,
                end_line=line_num,
            )

            current_block_id = None
            current_block_lines = []
            current_full_lines = []

        elif current_block_id is not None:
            current_block_lines.append(line)
            current_full_lines.append(line)

    if current_block_id is not None:
        raise ParseError(
            str(file_path),
            f"Unclosed block '{current_block_id}' starting at line {current_block_start}",
        )

    return blocks


def get_block_by_id(file_path: Path, block_id: str) -> BlockInfo:
    """
    Get a specific block from a script file by its ID.

    Args:
        file_path: Path to the script file
        block_id: The block identifier to find

    Returns:
        BlockInfo for the requested block

    Raises:
        ScriptNotFoundError: If the file doesn't exist
        BlockNotFoundError: If the block ID doesn't exist in the file
    """
    blocks = parse_script_blocks(file_path)

    if block_id not in blocks:
        raise BlockNotFoundError(str(file_path), block_id)

    return blocks[block_id]


def detect_language(file_path: Path) -> str:
    """
    Detect the programming language based on file extension.

    Args:
        file_path: Path to the script file

    Returns:
        Language string for use in code fences (e.g., "python")
    """
    if file_path.suffix == ".py":
        return "python"
    return "text"
