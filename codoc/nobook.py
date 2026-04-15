"""Support plain `.py` nobook files as notebook-like sources."""

import contextlib
import io
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from codoc.errors import ParseError
from codoc.nb_edit.editor import NotebookDict


BLOCK_START_PREFIX = "# @block="
OUTPUT_PREFIX = "# >>>"
ERROR_PREFIX = "# !!!"


@dataclass
class NobookBlock:
    """A single nobook block."""

    name: str
    lines: list[str]
    start_line: int

    @property
    def source(self) -> str:
        return "\n".join(self.lines).strip()


def load_nobook(path: Path) -> NotebookDict:
    """Load a nobook `.py` file and attach outputs from `.out.py` when present."""
    text = path.read_text(encoding="utf-8")
    blocks = parse_nobook(text, str(path))
    block_outputs = _parse_out_file(path)
    return _build_notebook_dict(blocks, block_outputs)


def execute_nobook(path: Path, block_ids: list[str] | None = None) -> NotebookDict:
    """Execute a nobook `.py` file and return a notebook-like structure."""
    text = path.read_text(encoding="utf-8")
    blocks = parse_nobook(text, str(path))
    block_outputs = _execute_blocks(blocks, block_ids)
    return _build_notebook_dict(blocks, block_outputs)


def parse_nobook(text: str, file_name: str) -> list[NobookBlock]:
    """Parse nobook-formatted Python code into blocks."""
    raw_lines = text.splitlines()
    blocks: list[NobookBlock] = []
    seen_names: set[str] = set()

    current_name: str | None = None
    current_lines: list[str] = []
    current_start = -1

    for i, line in enumerate(raw_lines):
        if line.startswith(BLOCK_START_PREFIX):
            if current_name is not None:
                blocks.append(
                    NobookBlock(name=current_name, lines=current_lines, start_line=current_start)
                )

            name = line[len(BLOCK_START_PREFIX) :].strip()
            if not name:
                raise ParseError(file_name, f"Line {i + 1}: missing block name")
            if name in seen_names:
                raise ParseError(file_name, f"Line {i + 1}: duplicate block name '{name}'")

            seen_names.add(name)
            current_name = name
            current_lines = []
            current_start = i + 1
        elif current_name is not None:
            current_lines.append(line)

    if current_name is not None:
        blocks.append(NobookBlock(name=current_name, lines=current_lines, start_line=current_start))

    if not blocks:
        raise ParseError(file_name, "No nobook blocks found. Expected lines starting with '# @block='")

    return blocks


def _parse_out_file(path: Path) -> dict[str, list[dict[str, Any]]]:
    """Parse a sibling `.out.py` file into notebook-style outputs."""
    out_path = path.with_suffix(".out.py")
    if not out_path.exists():
        return {}
    return _parse_out_text(out_path.read_text(encoding="utf-8"))


def _parse_out_text(text: str) -> dict[str, list[dict[str, Any]]]:
    block_outputs: dict[str, list[dict[str, Any]]] = {}
    current_block: str | None = None
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []

    def flush_outputs() -> None:
        nonlocal stdout_lines, stderr_lines
        if current_block is None:
            stdout_lines = []
            stderr_lines = []
            return

        outputs: list[dict[str, Any]] = []
        if stdout_lines:
            outputs.append(
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": "\n".join(stdout_lines) + "\n",
                }
            )
        if stderr_lines:
            outputs.append(
                {
                    "output_type": "error",
                    "traceback": stderr_lines,
                }
            )
        if outputs:
            block_outputs[current_block] = outputs
        stdout_lines = []
        stderr_lines = []

    for line in text.splitlines():
        if line.startswith(BLOCK_START_PREFIX):
            flush_outputs()
            current_block = line[len(BLOCK_START_PREFIX) :].strip()
            continue

        if current_block is None:
            continue

        if line == OUTPUT_PREFIX:
            continue
        if line.startswith(f"{OUTPUT_PREFIX} "):
            stdout_lines.append(line[len(f"{OUTPUT_PREFIX} ") :])
            continue
        if line.startswith(f"{ERROR_PREFIX} "):
            stderr_lines.append(line[len(f"{ERROR_PREFIX} ") :])

    flush_outputs()
    return block_outputs


def _execute_blocks(
    blocks: list[NobookBlock], block_ids: list[str] | None
) -> dict[str, list[dict[str, Any]]]:
    selected = _select_blocks(blocks, block_ids)
    shared_globals: dict[str, Any] = {"__name__": "__codoc_nobook__"}
    results: dict[str, list[dict[str, Any]]] = {}

    for block in selected:
        stdout_buf = io.StringIO()
        error = None

        try:
            with contextlib.redirect_stdout(stdout_buf):
                exec(compile("\n".join(block.lines), f"<block:{block.name}>", "exec"), shared_globals)
        except Exception:
            error = traceback.format_exc().rstrip("\n")

        block_outputs: list[dict[str, Any]] = []
        stdout = stdout_buf.getvalue()
        if stdout:
            block_outputs.append(
                {
                    "output_type": "stream",
                    "name": "stdout",
                    "text": stdout,
                }
            )
        if error:
            block_outputs.append(
                {
                    "output_type": "error",
                    "traceback": error.splitlines(),
                }
            )
        if block_outputs:
            results[block.name] = block_outputs

        if error:
            break

    return results


def _select_blocks(blocks: list[NobookBlock], block_ids: list[str] | None) -> list[NobookBlock]:
    if not block_ids:
        return blocks

    missing = [block_id for block_id in block_ids if block_id not in {block.name for block in blocks}]
    if missing:
        raise KeyError(f"Block '{missing[0]}' not found")

    max_index = max(i for i, block in enumerate(blocks) if block.name in block_ids)
    return blocks[: max_index + 1]


def _build_notebook_dict(
    blocks: list[NobookBlock], block_outputs: dict[str, list[dict[str, Any]]]
) -> NotebookDict:
    cells: list[dict[str, Any]] = []

    for block in blocks:
        source = [f"# @cell_id={block.name}\n"]
        if block.lines:
            source.extend(
                line + ("\n" if index < len(block.lines) - 1 else "")
                for index, line in enumerate(block.lines)
            )

        cells.append(
            {
                "cell_type": "code",
                "metadata": {"nobook": {"block": block.name}},
                "source": source,
                "outputs": block_outputs.get(block.name, []),
                "execution_count": None,
            }
        )

    return NotebookDict(
        {
            "cells": cells,
            "metadata": {"language_info": {"name": "python"}, "nobook": True},
            "nbformat": 4,
            "nbformat_minor": 5,
        }
    )
