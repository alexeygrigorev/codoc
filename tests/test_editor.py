"""Tests for the notebook editor.

These tests use nbformat (external Jupyter library) to verify that notebooks
are correctly saved and readable by external tools.
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import nbformat
import pytest
from codoc.nb_edit.editor import FastNotebookEditor, parse_cell_info, find_cells_by_id, NotebookDict, CellInfo, _strip_quotes


def create_notebook_with_source(source, temp_path):
    """Create a notebook file with the given source."""
    nb = nbformat.v4.new_notebook()
    nb.cells.append(nbformat.v4.new_code_cell(source))
    nbformat.write(nb, temp_path)
    return temp_path


def test_list_source_no_blank_line():
    """Test rename_id with list source, no blank line after cell_id."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ipynb', delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Create notebook with LIST source (no blank line)
        source_list = [
            "# @cell_id=rag",
            "def rag(query):",
            "    search_results = search(query)",
            "    prompt = build_prompt(query, search_results)",
            "    return llm_structured(prompt, instructions, SimpleAnswer)",
        ]
        create_notebook_with_source(source_list, temp_path)

        # Read raw JSON to verify format on disk
        with open(temp_path, 'r') as f:
            nb_before = json.load(f)
            original_source = nb_before['cells'][0]['source']
            print("Before: source type =", type(original_source).__name__)
            print("Before: source =", original_source)

        # Load with nbedit and rename
        editor = FastNotebookEditor.load(temp_path)
        editor.rename_id("rag", "rag-structured-simple")
        editor.save()

        # Read raw JSON to verify what's on disk
        with open(temp_path, 'r') as f:
            nb_after = json.load(f)
            new_source = nb_after['cells'][0]['source']
            print()
            print("After: source type =", type(new_source).__name__)
            print("After: source =", new_source)

        # Verify: should still be a list
        assert isinstance(new_source, list), f"Source should be list, got {type(new_source)}"

        # Verify: first line is new cell_id
        assert new_source[0] == "# @cell_id=rag-structured-simple"

        # Verify: second line is code (no extra blank line added)
        assert new_source[1] == "def rag(query):", f"Expected 'def rag(query):', got {new_source[1]!r}"

        # Verify: rest unchanged
        assert new_source[2] == "    search_results = search(query)"
        assert new_source[3] == "    prompt = build_prompt(query, search_results)"
        assert new_source[4] == "    return llm_structured(prompt, instructions, SimpleAnswer)"

        print("\nPASS: List source (no blank line) preserved correctly")

    finally:
        temp_path.unlink()


def test_list_source_with_blank_line():
    """Test rename_id with list source, blank line after cell_id."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ipynb', delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Create notebook with LIST source (with blank line)
        source_list = [
            "# @cell_id=rag",
            "",  # blank line
            "def rag(query):",
            "    return search(query)",
        ]
        create_notebook_with_source(source_list, temp_path)

        # Read raw JSON to verify
        with open(temp_path, 'r') as f:
            nb_before = json.load(f)
            print("Before: source =", nb_before['cells'][0]['source'])

        # Load with nbedit and rename
        editor = FastNotebookEditor.load(temp_path)
        editor.rename_id("rag", "rag-new")
        editor.save()

        # Read raw JSON to verify
        with open(temp_path, 'r') as f:
            nb_after = json.load(f)
            new_source = nb_after['cells'][0]['source']
            print("After: source =", new_source)

        # Verify: blank line preserved
        assert new_source[0] == "# @cell_id=rag-new"
        assert new_source[1] == "", "Blank line should be preserved"
        assert new_source[2] == "def rag(query):"

        print("\nPASS: List source (with blank line) preserved correctly")

    finally:
        temp_path.unlink()


def test_string_source_no_blank_line():
    """Test rename_id with string source, no blank line after cell_id."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ipynb', delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Create notebook with STRING source (no blank line)
        # We manually write JSON to preserve the string format
        nb_json = {
            "cells": [{
                "cell_type": "code",
                "source": "# @cell_id=rag\ndef rag(query):\n    return search(query)",
                "metadata": {},
                "outputs": [],
                "execution_count": None
            }],
            "metadata": {
                "kernelspec": {
                    "display_name": "Python 3",
                    "language": "python",
                    "name": "python3"
                }
            },
            "nbformat": 4,
            "nbformat_minor": 2
        }
        with open(temp_path, 'w') as f:
            json.dump(nb_json, f, indent=1)

        # Read raw JSON to verify
        with open(temp_path, 'r') as f:
            nb_before = json.load(f)
            print("Before: source type =", type(nb_before['cells'][0]['source']).__name__)
            print("Before: source (repr) =", repr(nb_before['cells'][0]['source']))

        # Load with nbedit and rename
        editor = FastNotebookEditor.load(temp_path)
        editor.rename_id("rag", "rag-new")
        editor.save()

        # Read raw JSON to verify
        with open(temp_path, 'r') as f:
            nb_after = json.load(f)
            new_source = nb_after['cells'][0]['source']
            print()
            print("After: source type =", type(new_source).__name__)
            print("After: source (repr) =", repr(new_source))

        # String source should stay as string
        assert isinstance(new_source, str), f"Source should be str, got {type(new_source)}"

        # Check content - no extra blank line
        parts = new_source.split("\n")
        assert parts[0] == "# @cell_id=rag-new"
        assert parts[1] == "def rag(query):", "No extra blank line should be added"

        print("\nPASS: String source (no blank line) preserved correctly")

    finally:
        temp_path.unlink()


def test_string_source_with_blank_line():
    """Test rename_id with string source, blank line after cell_id."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.ipynb', delete=False) as f:
        temp_path = Path(f.name)

    try:
        # Create notebook with STRING source (with blank line = \n\n)
        nb_json = {
            "cells": [{
                "cell_type": "code",
                "source": "# @cell_id=rag\n\ndef rag(query):\n    return search(query)",
                "metadata": {},
                "outputs": [],
                "execution_count": None
            }],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        }
        with open(temp_path, 'w') as f:
            json.dump(nb_json, f, indent=1)

        # Read raw JSON to verify
        with open(temp_path, 'r') as f:
            nb_before = json.load(f)
            print("Before: source (repr) =", repr(nb_before['cells'][0]['source']))

        # Load with nbedit and rename
        editor = FastNotebookEditor.load(temp_path)
        editor.rename_id("rag", "rag-new")
        editor.save()

        # Read raw JSON to verify
        with open(temp_path, 'r') as f:
            nb_after = json.load(f)
            new_source = nb_after['cells'][0]['source']
            print("After: source (repr) =", repr(new_source))

        # String source should stay as string
        assert isinstance(new_source, str), f"Source should be str, got {type(new_source)}"

        # Verify blank line preserved
        parts = new_source.split("\n")
        assert parts[0] == "# @cell_id=rag-new"
        assert parts[1] == "", "Blank line should be preserved"
        assert parts[2] == "def rag(query):"

        print("\nPASS: String source (with blank line) preserved correctly")

    finally:
        temp_path.unlink()


if __name__ == "__main__":
    print("=" * 60)
    print("TEST 1: List source, no blank line")
    print("=" * 60)
    test_list_source_no_blank_line()
    print()
    print("=" * 60)
    print("TEST 2: List source, with blank line")
    print("=" * 60)
    test_list_source_with_blank_line()
    print()
    print("=" * 60)
    print("TEST 3: String source, no blank line")
    print("=" * 60)
    test_string_source_no_blank_line()
    print()
    print("=" * 60)
    print("TEST 4: String source, with blank line")
    print("=" * 60)
    test_string_source_with_blank_line()
    print()
    print("=" * 60)
    print("ALL TESTS PASSED!")
    print("=" * 60)


class TestParseCellInfo:
    """Tests for parse_cell_info function."""

    def test_parses_cell_id_only(self):
        """It parses cell with only @cell_id."""
        source = ["# @cell_id=example", "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {}
        assert remaining == ["print('hi')"]

    def test_parses_cell_with_single_attribute(self):
        """It parses cell with one attribute."""
        source = ["# @cell_id=example", "# failing=true", "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"failing": "true"}
        assert remaining == ["print('hi')"]

    def test_parses_cell_with_multiple_attributes(self):
        """It parses cell with multiple attributes."""
        source = ["# @cell_id=example", "# failing=true", "# timeout=30", "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"failing": "true", "timeout": "30"}
        assert remaining == ["print('hi')"]

    def test_parses_with_blank_line_after_info(self):
        """It handles blank line after cell info."""
        source = ["# @cell_id=example", "# failing=true", "", "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"failing": "true"}
        assert remaining == ["", "print('hi')"]

    def test_returns_none_if_not_starting_with_hash(self):
        """It returns None if cell doesn't start with #."""
        source = ["print('hi')", "# @cell_id=example"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id is None
        assert attributes == {}
        assert remaining == source

    def test_returns_none_if_starts_with_blank(self):
        """It returns None if cell starts with blank line."""
        source = ["", "# @cell_id=example", "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id is None
        assert attributes == {}
        assert remaining == source

    def test_stops_parsing_at_non_comment_line(self):
        """It stops parsing attributes at first non-comment line."""
        source = ["# @cell_id=example", "# failing=true", "x = 1", "# not_an_attribute=true"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"failing": "true"}
        assert remaining == ["x = 1", "# not_an_attribute=true"]

    def test_handles_attribute_with_spaces(self):
        """It parses attributes with spaces around =."""
        source = ["# @cell_id=example", "# failing = true", "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"failing": "true"}
        assert remaining == ["print('hi')"]

    def test_handles_attribute_with_value_containing_spaces(self):
        """It parses attributes whose values contain spaces."""
        source = ["# @cell_id=example", "# message=hello world", "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"message": "hello world"}
        assert remaining == ["print('hi')"]

    def test_handles_empty_source(self):
        """It handles empty source."""
        cell_id, attributes, remaining = parse_cell_info([])
        assert cell_id is None
        assert attributes == {}
        assert remaining == []

    def test_handles_only_cell_info(self):
        """It handles cell with only info, no code."""
        source = ["# @cell_id=example", "# failing=true"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"failing": "true"}
        assert remaining == []

    def test_ignores_non_key_value_comments(self):
        """It ignores comment lines that aren't key=value."""
        source = ["# @cell_id=example", "# This is just a comment", "# failing=true", "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"failing": "true"}  # Non-key-value comment ignored
        assert remaining == ["print('hi')"]

    def test_strips_single_quotes_from_value(self):
        """It strips single quotes from attribute values."""
        source = ["# @cell_id=example", "# message='hello world'", "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"message": "hello world"}
        assert remaining == ["print('hi')"]

    def test_strips_double_quotes_from_value(self):
        """It strips double quotes from attribute values."""
        source = ["# @cell_id=example", '# message="hello world"', "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"message": "hello world"}
        assert remaining == ["print('hi')"]

    def test_handles_mixed_quotes(self):
        """It handles mixed single and double quotes in different attributes."""
        source = ["# @cell_id=example", "# one='single'", '# two="double"', "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"one": "single", "two": "double"}
        assert remaining == ["print('hi')"]

    def test_keeps_mismatched_quotes(self):
        """It keeps mismatched quotes as-is."""
        source = ["# @cell_id=example", '# message="mismatch\'', "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"message": '"mismatch\''}
        assert remaining == ["print('hi')"]

    def test_handles_value_with_internal_quotes(self):
        """It preserves internal quotes when outer quotes match."""
        source = ["# @cell_id=example", '# text="it\'s great"', "print('hi')"]
        cell_id, attributes, remaining = parse_cell_info(source)
        assert cell_id == "example"
        assert attributes == {"text": "it's great"}
        assert remaining == ["print('hi')"]


class TestFindCellsWithAttributes:
    """Tests for find_cells_by_id with attributes."""

    def test_finds_cell_with_attributes(self):
        """It populates attributes dict when found."""
        nb = NotebookDict({
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=test", "# failing=true", "# timeout=30", "x = 1"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        })

        cells = find_cells_by_id(nb)
        assert "test" in cells
        assert cells["test"].attributes == {"failing": "true", "timeout": "30"}

    def test_empty_attributes_when_not_present(self):
        """It has empty attributes dict when none present."""
        nb = NotebookDict({
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=test", "x = 1"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        })

        cells = find_cells_by_id(nb)
        assert "test" in cells
        assert cells["test"].attributes == {}

    def test_multiple_cells_with_different_attributes(self):
        """It handles multiple cells with different attributes."""
        nb = NotebookDict({
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=test1", "# failing=true", "x = 1"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None
                },
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=test2", "# timeout=60", "y = 2"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        })

        cells = find_cells_by_id(nb)
        assert cells["test1"].attributes == {"failing": "true"}
        assert cells["test2"].attributes == {"timeout": "60"}

    def test_jupyter_source_format_with_trailing_newlines(self):
        """It handles Jupyter's source format with trailing newlines on each line."""
        nb = NotebookDict({
            "cells": [
                {
                    "cell_type": "code",
                    # Jupyter stores source as list of strings, each with trailing \n
                    "source": ["# @cell_id=imports\n", "\n", "import json\n", "import boto3"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        })

        cells = find_cells_by_id(nb)
        # Should not have double newlines when joined
        assert cells["imports"].source == "import json\nimport boto3"


class TestExtractImage:
    """Tests for extract_image method."""

    # A minimal 1x1 red PNG image (base64 encoded)
    RED_PNG_BASE64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8DwHwAFBQIAX8jx0gAAAABJRU5ErkJggg=="

    # A minimal 1x1 red JPEG image (base64 encoded)
    RED_JPG_BASE64 = "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0aHBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/2wBDAQkJCQwLDBgNDRgyIRwhMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjIyMjL/wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAv/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFQEBAQAAAAAAAAAAAAAAAAAAAAX/xAAUEQEAAAAAAAAAAAAAAAAAAAAA/9oADAMBAAIRAxEAPwCwAB//2Q=="

    def create_notebook_with_image_output(self, image_data, mimetype="image/png"):
        """Create a notebook with a cell containing image output."""
        return NotebookDict({
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=test-image\n", "import matplotlib.pyplot as plt"],
                    "metadata": {},
                    "outputs": [
                        {
                            "output_type": "execute_result",
                            "data": {
                                mimetype: image_data
                            },
                            "metadata": {}
                        }
                    ],
                    "execution_count": 1
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        })

    def test_extract_image_by_cell_id(self, tmp_path):
        """It extracts image by cell ID."""
        nb = self.create_notebook_with_image_output(self.RED_PNG_BASE64)
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.png"

        editor.extract_image("test-image", output_path, format="png")

        assert output_path.exists()
        # Verify it's a valid PNG by checking header
        with open(output_path, "rb") as f:
            header = f.read(8)
        assert header == b'\x89PNG\r\n\x1a\n'

    def test_extract_image_by_index(self, tmp_path):
        """It extracts image by cell index."""
        nb = self.create_notebook_with_image_output(self.RED_PNG_BASE64)
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.jpg"

        editor.extract_image("1", output_path, format="jpg")

        assert output_path.exists()
        # Verify it's a valid JPEG by checking header
        with open(output_path, "rb") as f:
            header = f.read(2)
        assert header == b'\xff\xd8'

    def test_extract_image_creates_directories(self, tmp_path):
        """It creates output directories if they don't exist."""
        nb = self.create_notebook_with_image_output(self.RED_PNG_BASE64)
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "subdir" / "nested" / "output.png"

        editor.extract_image("test-image", output_path, format="png")

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_extract_image_from_png_to_jpg(self, tmp_path):
        """It converts PNG to JPG format."""
        nb = self.create_notebook_with_image_output(self.RED_PNG_BASE64, "image/png")
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.jpg"

        editor.extract_image("test-image", output_path, format="jpg", quality=90)

        assert output_path.exists()
        # Verify it's a JPEG
        with open(output_path, "rb") as f:
            header = f.read(2)
        assert header == b'\xff\xd8'

    def test_extract_image_from_jpg_to_png(self, tmp_path):
        """It converts JPEG to PNG format."""
        nb = self.create_notebook_with_image_output(self.RED_JPG_BASE64, "image/jpeg")
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.png"

        editor.extract_image("test-image", output_path, format="png")

        assert output_path.exists()
        # Verify it's a PNG
        with open(output_path, "rb") as f:
            header = f.read(8)
        assert header == b'\x89PNG\r\n\x1a\n'

    def test_extract_image_error_cell_not_found(self, tmp_path):
        """It raises error when cell ID not found."""
        nb = self.create_notebook_with_image_output(self.RED_PNG_BASE64)
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.png"

        with pytest.raises(ValueError, match="Cell with @cell_id=nonexistent not found"):
            editor.extract_image("nonexistent", output_path, format="png")

    def test_extract_image_error_index_out_of_range(self, tmp_path):
        """It raises error when cell index out of range."""
        nb = self.create_notebook_with_image_output(self.RED_PNG_BASE64)
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.png"

        with pytest.raises(ValueError, match="Cell index 99 out of range"):
            editor.extract_image("99", output_path, format="png")

    def test_extract_image_error_no_output(self, tmp_path):
        """It raises error when cell has no output."""
        nb = NotebookDict({
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=no-output\n", "x = 1"],
                    "metadata": {},
                    "outputs": [],
                    "execution_count": None
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        })
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.png"

        with pytest.raises(ValueError, match="Cell has no output"):
            editor.extract_image("no-output", output_path, format="png")

    def test_extract_image_error_no_image_data(self, tmp_path):
        """It raises error when cell has no image output."""
        nb = NotebookDict({
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=text-output\n", "print('hello')"],
                    "metadata": {},
                    "outputs": [
                        {
                            "output_type": "stream",
                            "text": ["hello\n"]
                        }
                    ],
                    "execution_count": 1
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        })
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.png"

        with pytest.raises(ValueError, match="no image output"):
            editor.extract_image("text-output", output_path, format="png")

    def test_extract_image_error_invalid_format(self, tmp_path):
        """It raises error for invalid format."""
        nb = self.create_notebook_with_image_output(self.RED_PNG_BASE64)
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.webp"

        with pytest.raises(ValueError, match="Unsupported format: webp"):
            editor.extract_image("test-image", output_path, format="webp")

    def test_extract_image_handles_list_image_data(self, tmp_path):
        """It handles image data stored as list (common in Jupyter)."""
        # Jupyter often stores base64 as list of strings
        image_list = list(self.RED_PNG_BASE64)  # Split into chars to simulate list
        nb = NotebookDict({
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=list-image\n", "plt.show()"],
                    "metadata": {},
                    "outputs": [
                        {
                            "output_type": "execute_result",
                            "data": {
                                "image/png": image_list
                            },
                            "metadata": {}
                        }
                    ],
                    "execution_count": 1
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2
        })
        editor = FastNotebookEditor(nb, None)
        output_path = tmp_path / "output.png"

        editor.extract_image("list-image", output_path, format="png")

        assert output_path.exists()
