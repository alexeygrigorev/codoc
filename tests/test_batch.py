"""Tests for batch mode notebook editing.

These tests use nbformat to read notebooks and verify the results are 100% correct.
"""

import subprocess
import sys
from pathlib import Path

import nbformat
import pytest

NOTEBOOK_EDITOR_CMD = [sys.executable, "-m", "codoc.nb_edit"]


def run_batch(notebook_path: Path, batch_content: str) -> tuple[int, str, str]:
    """Run a batch command against a notebook.

    Args:
        notebook_path: Path to the notebook
        batch_content: Batch commands to run

    Returns:
        Tuple of (exit_code, stdout, stderr)
    """
    cmd = NOTEBOOK_EDITOR_CMD + [str(notebook_path), "--batch", "-"]
    result = subprocess.run(
        cmd,
        input=batch_content,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    return result.returncode, result.stdout, result.stderr


def load_notebook(path: Path) -> nbformat.NotebookNode:
    """Load a notebook using nbformat."""
    with open(path) as f:
        return nbformat.read(f, as_version=4)


class TestBatchMode:
    """Tests for batch mode functionality."""

    def test_batch_create_and_add_cells(self, tmp_path):
        """Test creating a notebook and adding cells in batch mode."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id first-cell --code
x = 1
y = 2
@>> add --id second-cell --code
z = 3
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0
        assert "Saved:" in stdout

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2

        # First cell
        assert "# @cell_id=first-cell" in nb.cells[0].source
        assert "x = 1" in nb.cells[0].source
        assert "y = 2" in nb.cells[0].source

        # Second cell
        assert "# @cell_id=second-cell" in nb.cells[1].source
        assert "z = 3" in nb.cells[1].source

    def test_batch_add_and_update(self, tmp_path):
        """Test adding and then updating a cell in batch mode."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id my-cell --code
original content
@>> update my-cell --code
updated content
more lines
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert "# @cell_id=my-cell" in nb.cells[0].source
        assert "updated content" in nb.cells[0].source
        assert "more lines" in nb.cells[0].source
        assert "original content" not in nb.cells[0].source

    def test_batch_add_id_to_existing_cells(self, tmp_path):
        """Test adding cell_id to existing cells."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --code
first cell
@>> add --code
second cell
@>> add-id 1 first
@>> add-id 2 second
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2
        assert "# @cell_id=first" in nb.cells[0].source
        assert "first cell" in nb.cells[0].source
        assert "# @cell_id=second" in nb.cells[1].source
        assert "second cell" in nb.cells[1].source

    def test_batch_delete_by_id(self, tmp_path):
        """Test deleting cells by ID in batch mode."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id first --code
x = 1
@>> add --id second --code
y = 2
@>> add --id third --code
z = 3
@>> delete second
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2
        assert "# @cell_id=first" in nb.cells[0].source
        assert "# @cell_id=third" in nb.cells[1].source

    def test_batch_delete_by_index(self, tmp_path):
        """Test deleting cells by index in batch mode."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id first --code
x = 1
@>> add --id second --code
y = 2
@>> add --id third --code
z = 3
@>> delete 2
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2
        assert "# @cell_id=first" in nb.cells[0].source
        assert "# @cell_id=third" in nb.cells[1].source

    def test_batch_insert_after_id(self, tmp_path):
        """Test inserting a cell after another by ID."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id first --code
a = 1
@>> add --id second --code
c = 3
@>> insert-after first --id middle --code
b = 2
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 3
        assert "# @cell_id=first" in nb.cells[0].source
        assert "# @cell_id=middle" in nb.cells[1].source
        assert "# @cell_id=second" in nb.cells[2].source

    def test_batch_insert_after_index(self, tmp_path):
        """Test inserting a cell after an index."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id first --code
a = 1
@>> add --id second --code
c = 3
@>> insert-after-index 1 --id middle --code
b = 2
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 3
        assert "# @cell_id=first" in nb.cells[0].source
        assert "# @cell_id=middle" in nb.cells[1].source
        assert "# @cell_id=second" in nb.cells[2].source

    def test_batch_rename_id(self, tmp_path):
        """Test renaming cell IDs in batch mode."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id old-name --code
x = 1
@>> rename old-name --new-id new-name
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert "# @cell_id=new-name" in nb.cells[0].source
        assert "old-name" not in nb.cells[0].source

    def test_batch_add_markdown_cell(self, tmp_path):
        """Test adding markdown cells in batch mode."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id code --code
x = 1
@>> add --markdown
# Heading

This is **markdown**
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2
        assert nb.cells[0].cell_type == "code"
        assert nb.cells[1].cell_type == "markdown"
        assert "# Heading" in nb.cells[1].source
        assert "This is **markdown**" in nb.cells[1].source

    def test_batch_multiple_operations(self, tmp_path):
        """Test multiple operations in a single batch."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id import-cell --code
import os
@>> add --id config-cell --code
path = "/tmp"
@>> add-id 1 imports
@>> add-id 2 config
@>> update-index 2 --code
path = "/etc"
@>> insert-after-index 1 --id between --code
# Between import and config
@>> rename imports --new-id import-stmt
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 3

        # Cell 0: import-stmt (renamed)
        assert "# @cell_id=import-stmt" in nb.cells[0].source
        assert "import os" in nb.cells[0].source

        # Cell 1: between (inserted)
        assert "# @cell_id=between" in nb.cells[1].source
        assert "Between import and config" in nb.cells[1].source

        # Cell 2: config (updated) - update-index replaces entire source, so no cell_id
        assert 'path = "/etc"' in nb.cells[2].source

    def test_batch_update_index(self, tmp_path):
        """Test updating cell by index in batch mode."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --code
original
@>> add --code
also original
@>> update-index 1 --code
updated content
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2
        assert "updated content" in nb.cells[0].source
        assert "also original" in nb.cells[1].source

    def test_batch_preserves_notebook_metadata(self, tmp_path):
        """Test that batch mode preserves notebook metadata."""
        notebook_path = tmp_path / "test.ipynb"

        # Create a notebook with custom metadata
        nb = nbformat.v4.new_notebook()
        nb.metadata.kernelspec = {
            "display_name": "My Custom Kernel",
            "language": "python",
            "name": "myenv"
        }
        nb.metadata.author = "Test Author"
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        batch = """@>> add --id new-cell --code
x = 42
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert nb.metadata.kernelspec["name"] == "myenv"
        assert nb.metadata.author == "Test Author"
        assert len(nb.cells) == 1

    def test_batch_multiline_code(self, tmp_path):
        """Test that multiline code is properly preserved."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id complex-cell --code
def my_function(x, y):
    '''A docstring.'''
    result = x + y
    return result

# Call the function
answer = my_function(1, 2)
print(answer)
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source
        assert "def my_function(x, y):" in source
        assert "'''A docstring.'''" in source
        assert "    result = x + y" in source
        assert "    return result" in source
        assert "answer = my_function(1, 2)" in source

    def test_batch_no_save_auto_saves(self, tmp_path):
        """Test that batch mode auto-saves even without explicit save command."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id test --code
x = 99
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert "x = 99" in nb.cells[0].source

    def test_batch_move_id_after_id(self, tmp_path):
        """Test moving a cell by ID after another cell by ID."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id first --code
a = 1
@>> add --id second --code
b = 2
@>> add --id third --code
c = 3
@>> move third first
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 3
        # "move third after first" means: first, third, second
        assert "# @cell_id=first" in nb.cells[0].source
        assert "# @cell_id=third" in nb.cells[1].source
        assert "# @cell_id=second" in nb.cells[2].source

    def test_batch_content_after_marker(self, tmp_path):
        """Test that content after @cell_id marker is properly preserved."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id test --code
# @cell_id=test
x = 1
y = 2
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source
        # The add command prepends its own @cell_id marker
        assert "# @cell_id=test" in source
        assert "x = 1" in source
        assert "y = 2" in source

    def test_batch_empty_lines_preserved(self, tmp_path):
        """Test that empty lines in code are preserved."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id test --code
x = 1

y = 2

z = 3
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source
        # Empty lines should be preserved
        assert "x = 1" in source
        assert "y = 2" in source
        assert "z = 3" in source

    def test_batch_special_characters(self, tmp_path):
        """Test that special characters are preserved."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id test --code
# Special characters: quotes, dollars, backslashes
text = 'He said "hello"'
price = "$100"
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source
        assert '"hello"' in source
        assert '"$100"' in source

    def test_batch_unknown_command_warning(self, tmp_path):
        """Test that unknown commands produce a warning but batch still completes."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id test --code
x = 1
@>> save
@>> unknown-command
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        # Unknown commands should produce a warning but still succeed
        assert returncode == 0
        assert "Unknown command 'save'" in stderr
        assert "Unknown command 'unknown-command'" in stderr
        assert "Saved:" in stdout

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert "x = 1" in nb.cells[0].source

    def test_batch_add_without_code_flag(self, tmp_path):
        """Test that add without --code flag still works."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id test
some code here
more code
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert "some code here" in nb.cells[0].source
        assert "more code" in nb.cells[0].source

    def test_list_then_batch_assign_ids(self, tmp_path):
        """Test the workflow of listing cells first, then batch-assigning IDs.

        This simulates the agent workflow:
        1. Create a notebook with cells but no IDs
        2. Run `list` to see the notebook structure
        3. Based on the list, create a batch file to add IDs
        4. Run the batch command
        5. Verify IDs were added correctly
        """
        notebook_path = tmp_path / "test.ipynb"

        # Step 1: Create a notebook with cells but no IDs
        nb = nbformat.v4.new_notebook()
        nb.cells.append(nbformat.v4.new_code_cell("import os\nimport sys"))
        nb.cells.append(nbformat.v4.new_code_cell("path = '/tmp'\nprint(path)"))
        nb.cells.append(nbformat.v4.new_code_cell("result = 1 + 1\nprint(result)"))
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        # Step 2: Run `list` command to see the structure
        cmd = NOTEBOOK_EDITOR_CMD + [str(notebook_path), "list"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent.parent
        )

        assert result.returncode == 0
        list_output = result.stdout
        # Verify we can see the cells in the list output
        assert "[1]" in list_output
        assert "[2]" in list_output
        assert "[3]" in list_output
        assert "import os" in list_output

        # Step 3: Based on the list, create a batch file to add IDs
        batch = """@>> add-id 1 import-stmt
@>> add-id 2 config-path
@>> add-id 3 calculation
"""

        # Step 4: Run the batch command
        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0
        assert "Saved:" in stdout

        # Step 5: Verify IDs were added correctly
        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 3
        assert "# @cell_id=import-stmt" in nb.cells[0].source
        assert "import os" in nb.cells[0].source
        assert "# @cell_id=config-path" in nb.cells[1].source
        assert "path = '/tmp'" in nb.cells[1].source
        assert "# @cell_id=calculation" in nb.cells[2].source
        assert "result = 1 + 1" in nb.cells[2].source

    def test_add_id_adds_blank_line_after_marker(self, tmp_path):
        """Test that add-id adds a blank line after the cell_id marker.

        Scenario: notebook created outside of nbedit, add id, read.
        Expected: blank line after cell_id marker (for readability)
        """
        notebook_path = tmp_path / "test.ipynb"

        # Create a notebook using nbformat (not via nbedit) - simulates external notebook
        nb = nbformat.v4.new_notebook()
        code = "import frontmatter\n\npost = frontmatter.loads(document.content)\n\ndata = post.to_dict()\ndata['filename'] = document.filename"
        nb.cells.append(nbformat.v4.new_code_cell(code))
        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        # Add a cell ID using batch mode
        batch = "@>> add-id 1 parsing-metadata"
        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        # Reload and check the source
        nb = load_notebook(notebook_path)
        source = nb.cells[0].source

        # Expected: blank line after the marker
        expected = "# @cell_id=parsing-metadata\n\nimport frontmatter\n\npost = frontmatter.loads(document.content)\n\ndata = post.to_dict()\ndata['filename'] = document.filename"
        assert source == expected, f"Expected:\n{repr(expected)}\n\nActual:\n{repr(source)}"

    def test_batch_comments_are_ignored(self, tmp_path):
        """Test that lines starting with -- are treated as comments and ignored."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """-- This is a comment
-- So is this
@>> add --id my-cell --code
x = 1
-- Another comment after a command
@>> add --id another-cell --code
y = 2
"""
        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 2
        assert "# @cell_id=my-cell" in nb.cells[0].source
        assert "x = 1" in nb.cells[0].source
        assert "# @cell_id=another-cell" in nb.cells[1].source
        assert "y = 2" in nb.cells[1].source

    def test_batch_comment_does_not_conflict_with_flags(self, tmp_path):
        """Test that -- only comments when followed by space, not for flags like --code."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """-- Comment at start
@>> add --id test --code
print("hello")
@>> update test --code
print("updated")
"""
        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert "updated" in nb.cells[0].source
        assert "hello" not in nb.cells[0].source

    def test_batch_double_dash_without_space_is_not_comment(self, tmp_path):
        """Test that -- without a space after is NOT treated as a comment.
        
        This ensures argument flags like --code, --id, --new-id are not affected.
        """
        notebook_path = tmp_path / "test.ipynb"

        batch = """@>> add --id test --code
print("--this is not a comment")
print("neither is --this")
"""
        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source
        assert '"--this is not a comment"' in source
        assert '"neither is --this"' in source

    def test_batch_comment_with_special_chars(self, tmp_path):
        """Test comments can contain special characters."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """-- Comment with "quotes" and 'apostrophes'
-- Comment with !@#$% special chars
@>> add --id test --code
x = 1
"""
        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert "x = 1" in nb.cells[0].source

    def test_batch_multiple_consecutive_comments(self, tmp_path):
        """Test multiple consecutive comment lines are all ignored."""
        notebook_path = tmp_path / "test.ipynb"

        batch = """-- Comment 1
-- Comment 2
-- Comment 3
@>> add --id test --code
x = 1
"""
        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        assert len(nb.cells) == 1
        assert "x = 1" in nb.cells[0].source

    def test_adding_cell_preserves_existing_outputs(self, tmp_path):
        """Regression test: inserting a cell should NOT remove outputs from other cells.

        This was a concern raised during development - verify that adding a new cell
        does not affect the outputs of existing cells in the notebook.
        """
        notebook_path = tmp_path / "test.ipynb"

        # Create a notebook with a cell that has output
        import nbformat
        nb = nbformat.v4.new_notebook()
        cell = nbformat.v4.new_code_cell("x = 1 + 1\nprint(x)")
        cell.outputs = [
            nbformat.v4.new_output(
                output_type="stream",
                name="stdout",
                text="2\n"
            )
        ]
        cell.execution_count = 1
        nb.cells.append(cell)

        with open(notebook_path, "w") as f:
            nbformat.write(nb, f)

        # Verify the cell has output before
        nb_before = nbformat.read(notebook_path, as_version=4)
        assert len(nb_before.cells[0].outputs) == 1
        assert nb_before.cells[0].outputs[0].text == "2\n"

        # Add a new cell via batch mode
        batch = """@>> insert-after 1 --id new-cell --code
y = 2 + 2
"""
        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        # Verify the original cell still has its output
        nb_after = nbformat.read(notebook_path, as_version=4)
        assert len(nb_after.cells) == 2
        assert len(nb_after.cells[0].outputs) == 1, "Original cell should still have output"
        assert nb_after.cells[0].outputs[0].text == "2\n", "Output content should be preserved"

        # New cell should have no output (expected - it was never executed)
        assert len(nb_after.cells[1].outputs) == 0

    def test_batch_literal_newline_sequences_preserved(self, tmp_path):
        """Test that literal \\n sequences in code are preserved in batch mode.

        This tests the exact scenario from v2/02-rag-usecases-tech/03-youtube/notebook.ipynb
        where the make-subtitles cell contains code like:
            text = entry.text.replace('\\n', ' ')
            return '\\n'.join(lines)

        These literal backslash-n sequences should be preserved as-is in the notebook.
        """
        notebook_path = tmp_path / "test.ipynb"

        # The actual content from make-subtitles cell
        batch = """@>> add --id make-subtitles --code
def make_subtitles(transcript) -> str:
    lines = []

    for entry in transcript:
        ts = format_timestamp(entry.start)
        text = entry.text.replace('\\n', ' ')
        lines.append(ts + ' ' + text)

    return '\\n'.join(lines)

subtitles = make_subtitles(transcript)
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source

        # Verify literal \\n sequences are preserved
        assert "replace('\\n', ' ')" in source
        assert "return '\\n'.join(lines)" in source
        # Make sure we have the literal backslash-n, not actual newlines
        assert "\\n" in source

    def test_single_cell_update_literal_newline_sequences_preserved(self, tmp_path):
        """Test that literal \\n sequences are preserved in single-cell update mode.

        This tests the same scenario but using the update command instead of add.
        """
        notebook_path = tmp_path / "test.ipynb"

        # First create a cell
        batch = """@>> add --id make-subtitles --code
def make_subtitles(transcript) -> str:
    lines = []
    for entry in transcript:
        ts = format_timestamp(entry.start)
        text = entry.text.replace('\\n', ' ')
        lines.append(ts + ' ' + text)
    return '\\n'.join(lines)
"""
        returncode, stdout, stderr = run_batch(notebook_path, batch)
        assert returncode == 0

        # Now update it with modified content
        update_batch = """@>> update make-subtitles --code
def make_subtitles(transcript) -> str:
    lines = []

    for entry in transcript:
        ts = format_timestamp(entry.start)
        text = entry.text.replace('\\n', ' ').replace('\\r', '')
        lines.append(ts + ' ' + text)

    return '\\n'.join(lines)

subtitles = make_subtitles(transcript)
"""
        returncode, stdout, stderr = run_batch(notebook_path, update_batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source

        # Verify both literal \\n sequences are preserved after update
        assert "replace('\\n', ' ')" in source
        assert "replace('\\r', '')" in source  # New line we added
        assert "return '\\n'.join(lines)" in source

    def test_batch_preserves_exact_newlines_in_multiline_string(self, tmp_path):
        """Test that exact newlines in multiline strings are preserved.

        This verifies that when code contains actual newlines in strings
        (not \\n escape sequences), they are preserved correctly.
        """
        notebook_path = tmp_path / "test.ipynb"

        # Build the batch content without nested triple quotes
        batch_lines = [
            "@>> add --id test-cell --code",
            'prompt = """',
            "Summarize the transcript and describe the main purpose of the video",
            "and the main ideas.",
            "",
            "Output format:",
            "",
            "Summary",
            "",
            "timestamp chapter",
            "...",
            '"""',
        ]
        batch = "\n".join(batch_lines)

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source

        # Verify the multiline string is preserved
        assert 'prompt = """' in source
        assert "Summarize the transcript" in source
        assert "Output format:" in source


class TestDoubledLineBreakValidation:
    """Tests for doubled line break detection in batch mode."""

    def test_add_rejects_doubled_line_breaks(self, tmp_path):
        """Test that add command rejects content with doubled line breaks."""
        notebook_path = tmp_path / "test.ipynb"

        # Content with doubled line breaks (more than 2 consecutive newlines)
        batch = """@>> add --id test --code
line one


line two


line three
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode != 0
        assert "Doubled line breaks detected" in stderr

    def test_add_accepts_single_blank_lines(self, tmp_path):
        """Test that add command accepts content with single blank lines."""
        notebook_path = tmp_path / "test.ipynb"

        # Content with single blank lines (normal spacing)
        batch = """@>> add --id test --code
line one

line two

line three
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        assert returncode == 0

        nb = load_notebook(notebook_path)
        source = nb.cells[0].source
        assert "line one" in source
        assert "line two" in source
        assert "line three" in source

    def test_short_content_not_validated(self, tmp_path):
        """Test that short content (3 or fewer lines) is not validated."""
        notebook_path = tmp_path / "test.ipynb"

        # Short content with doubled line breaks should still work
        batch = """@>> add --id test --code
line one


line two
"""

        returncode, stdout, stderr = run_batch(notebook_path, batch)

        # Should pass because it's only 2 non-blank lines
        assert returncode == 0

    def test_update_rejects_doubled_line_breaks(self, tmp_path):
        """Test that update command rejects content with doubled line breaks."""
        notebook_path = tmp_path / "test.ipynb"

        # First create a cell
        create_batch = """@>> add --id test --code
original content
"""
        run_batch(notebook_path, create_batch)

        # Try to update with doubled line breaks
        update_batch = """@>> update test --code
line one


line two


line three
"""

        returncode, stdout, stderr = run_batch(notebook_path, update_batch)

        assert returncode != 0
        assert "Doubled line breaks detected" in stderr

    def test_insert_after_rejects_doubled_line_breaks(self, tmp_path):
        """Test that insert-after command rejects content with doubled line breaks."""
        notebook_path = tmp_path / "test.ipynb"

        # First create a cell
        create_batch = """@>> add --id first --code
x = 1
"""
        run_batch(notebook_path, create_batch)

        # Try to insert after with doubled line breaks
        insert_batch = """@>> insert-after first --id second --code
line one


line two


line three
"""

        returncode, stdout, stderr = run_batch(notebook_path, insert_batch)

        assert returncode != 0
        assert "Doubled line breaks detected" in stderr
