"""Tests for utility functions."""

from codoc.utils import strip_cell_id, join_lines, find_template_files, resolve_notebook_path, strip_try_except

import pytest
from pathlib import Path


class TestStripCellId:
    """Tests for strip_cell_id function."""

    def test_strips_cell_id_line(self):
        """It removes the @cell_id marker line."""
        source = ["# @cell_id=test", "x = 1", "y = 2"]
        result = strip_cell_id(source)
        assert result == ["x = 1", "y = 2"]

    def test_strips_leading_whitespace(self):
        """It removes leading empty lines."""
        source = ["# @cell_id=test", "", "", "x = 1", "y = 2"]
        result = strip_cell_id(source)
        assert result == ["x = 1", "y = 2"]

    def test_strips_trailing_whitespace(self):
        """It removes trailing empty lines."""
        source = ["# @cell_id=test", "x = 1", "y = 2", "", ""]
        result = strip_cell_id(source)
        assert result == ["x = 1", "y = 2"]

    def test_strips_both(self):
        """It removes both leading and trailing empty lines."""
        source = ["# @cell_id=test", "", "x = 1", "y = 2", "", ""]
        result = strip_cell_id(source)
        assert result == ["x = 1", "y = 2"]

    def test_preserves_internal_whitespace(self):
        """It keeps empty lines in the middle of the code."""
        source = ["# @cell_id=test", "x = 1", "", "y = 2"]
        result = strip_cell_id(source)
        assert result == ["x = 1", "", "y = 2"]

    def test_handles_whitespace_in_marker(self):
        """It handles markers with extra whitespace."""
        source = ["# @cell_id = test  ", "x = 1"]
        result = strip_cell_id(source)
        assert result == ["x = 1"]

    def test_handles_only_marker(self):
        """It handles a cell with only the marker."""
        source = ["# @cell_id=test", "", ""]
        result = strip_cell_id(source)
        assert result == []

    def test_handles_different_spacing(self):
        """It handles different spacing in the marker."""
        source = ["#    @cell_id=test", "x = 1"]
        result = strip_cell_id(source)
        assert result == ["x = 1"]


class TestJoinLines:
    """Tests for join_lines function."""

    def test_joins_lines_with_newlines(self):
        """It joins lines with newline characters."""
        lines = ["line 1", "line 2", "line 3"]
        result = join_lines(lines)
        assert result == "line 1\nline 2\nline 3"

    def test_empty_list(self):
        """It handles empty list."""
        result = join_lines([])
        assert result == ""

    def test_single_line(self):
        """It handles single line."""
        result = join_lines(["single"])
        assert result == "single"


class TestFindTemplateFiles:
    """Tests for find_template_files function."""

    def test_finds_template_files(self, tmp_path):
        """It finds all *.template.md files recursively."""
        (tmp_path / "test1.template.md").write_text("content")
        (tmp_path / "test2.md").write_text("content")
        (tmp_path / "subdir").mkdir()
        (tmp_path / "subdir" / "test3.template.md").write_text("content")

        result = find_template_files(tmp_path)

        assert len(result) == 2
        paths = [str(p.relative_to(tmp_path)) for p in result]
        assert "test1.template.md" in paths
        assert str(Path("subdir") / "test3.template.md") in paths

    def test_returns_sorted_results(self, tmp_path):
        """It returns results sorted by path."""
        (tmp_path / "z.template.md").write_text("content")
        (tmp_path / "a.template.md").write_text("content")
        (tmp_path / "m.template.md").write_text("content")

        result = find_template_files(tmp_path)
        names = [p.name for p in result]

        assert names == ["a.template.md", "m.template.md", "z.template.md"]

    def test_empty_directory(self, tmp_path):
        """It handles empty directory."""
        result = find_template_files(tmp_path)
        assert result == []


class TestResolveNotebookPath:
    """Tests for resolve_notebook_path function."""

    def test_resolves_relative_path(self, tmp_path):
        """It resolves notebook path relative to template."""
        template_path = tmp_path / "subdir" / "test.template.md"
        template_path.parent.mkdir(parents=True)

        result = resolve_notebook_path(template_path, "../notebook.ipynb")

        assert result == tmp_path / "notebook.ipynb"

    def test_resolves_same_directory(self, tmp_path):
        """It resolves path in same directory."""
        template_path = tmp_path / "test.template.md"

        result = resolve_notebook_path(template_path, "notebook.ipynb")

        assert result == tmp_path / "notebook.ipynb"

    def test_resolves_deep_relative(self, tmp_path):
        """It resolves deeply nested relative paths."""
        template_path = tmp_path / "a" / "b" / "c" / "test.template.md"
        template_path.parent.mkdir(parents=True)

        result = resolve_notebook_path(template_path, "../../notebooks/test.ipynb")

        assert result == tmp_path / "a" / "notebooks" / "test.ipynb"


class TestStripTryExcept:
    """Tests for strip_try_except function."""

    def test_strips_try_except_wrapper(self):
        """It removes try/except wrapper and de-indents code."""
        source = """try:
    x = 1
    print(x)
except Exception as e:
    print(e)"""
        result = strip_try_except(source)
        assert result == "x = 1\nprint(x)"

    def test_strips_with_two_space_indent(self):
        """It handles 2-space indentation."""
        source = """try:
  x = 1
  print(x)
except Exception as e:
  print(e)"""
        result = strip_try_except(source)
        assert result == "x = 1\nprint(x)"

    def test_returns_original_if_no_try(self):
        """It returns original code if no try wrapper."""
        source = "x = 1\nprint(x)"
        result = strip_try_except(source)
        assert result == source

    def test_handles_multiline_code(self):
        """It handles multi-line code blocks."""
        source = """try:
    for i in range(10):
        print(i)
    x = 1 / 0
except Exception as e:
    print(e)"""
        result = strip_try_except(source)
        assert "for i in range(10):" in result
        assert "print(i)" in result
        assert "x = 1 / 0" in result

    def test_strips_leading_trailing_empty_lines(self):
        """It strips empty lines from result."""
        source = """try:
    x = 1

    print(x)
except Exception as e:
    print(e)"""
        result = strip_try_except(source)
        assert result == "x = 1\n\nprint(x)"

    def test_handles_nested_indentation(self):
        """It handles nested indentation in try block."""
        source = """try:
    if True:
        x = 1
        print(x)
except Exception as e:
    print(e)"""
        result = strip_try_except(source)
        assert result == "if True:\n    x = 1\n    print(x)"

    def test_handles_single_line_in_try(self):
        """It handles single line of code in try block."""
        source = """try:
    x = 1 / 0
except Exception as e:
    print(e)"""
        result = strip_try_except(source)
        assert result == "x = 1 / 0"

    def test_handles_tabs(self):
        """It handles tab indentation."""
        source = "try:\n\tx = 1\n\tprint(x)\nexcept Exception as e:\n\tprint(e)"
        result = strip_try_except(source)
        assert result == "x = 1\nprint(x)"

    def test_handles_different_exception_var_names(self):
        """It handles different exception variable names."""
        source = """try:
    x = 1
except Exception as err:
    print(err)"""
        result = strip_try_except(source)
        assert result == "x = 1"

    def test_handles_bare_except(self):
        """It handles bare except clause."""
        source = """try:
    x = 1
except:
    pass"""
        result = strip_try_except(source)
        assert result == "x = 1"

    def test_handles_multiple_except_lines(self):
        """It handles multiple lines in except block."""
        source = """try:
    x = 1 / 0
except Exception as e:
    print(f"Error: {e}")
    raise"""
        result = strip_try_except(source)
        assert result == "x = 1 / 0"

    def test_handles_code_with_comments(self):
        """It handles code with comments."""
        source = """try:
    # This is a comment
    x = 1
    # Another comment
    print(x)
except Exception as e:
    print(e)"""
        result = strip_try_except(source)
        assert "# This is a comment" in result
        assert "x = 1" in result
        assert "# Another comment" in result

    def test_returns_empty_for_only_try(self):
        """It returns empty string for only try: line."""
        source = "try:"
        result = strip_try_except(source)
        assert result == ""

    def test_handles_multiline_try_with_continuation(self):
        """It handles multiline statements with backslash or parens."""
        source = """try:
    x = very_long_function_name(
        arg1,
        arg2
    )
except Exception as e:
    print(e)"""
        result = strip_try_except(source)
        assert "x = very_long_function_name(" in result
        assert "arg1," in result

    def test_preserves_internal_empty_lines(self):
        """It preserves empty lines within the try block."""
        source = """try:
    x = 1

    y = 2
except Exception as e:
    print(e)"""
        result = strip_try_except(source)
        assert result == "x = 1\n\ny = 2"
