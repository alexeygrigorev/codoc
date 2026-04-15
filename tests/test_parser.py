"""Tests for template parsing."""

from pathlib import Path

import pytest

from codoc.parser import parse_template, _parse_notebook_refs, _parse_script_refs, _find_directives
from codoc.errors import ParseError


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestParseTemplate:
    """Tests for parse_template function."""

    def test_parse_simple_template(self):
        """It parses a simple template with frontmatter and directives."""
        template_path = FIXTURES_DIR / "simple.template.md"
        result = parse_template(template_path)

        assert result.frontmatter is not None
        assert "notebooks" in result.frontmatter
        assert len(result.notebook_refs) == 1
        assert "sample" in result.notebook_refs
        assert result.notebook_refs["sample"].path == "notebooks/sample.ipynb"

    def test_parse_multi_notebook_template(self):
        """It parses a template with multiple notebook references."""
        template_path = FIXTURES_DIR / "multi-notebook.template.md"
        result = parse_template(template_path)

        assert len(result.notebook_refs) == 2
        assert "first" in result.notebook_refs
        assert "second" in result.notebook_refs

    def test_extracts_body_content(self):
        """It extracts the body content without frontmatter."""
        template_path = FIXTURES_DIR / "simple.template.md"
        result = parse_template(template_path)

        assert "# Simple Template" in result.body
        assert "@@code" in result.body
        assert "---" not in result.body  # Frontmatter delimiter should not be in body

    def test_finds_directives(self):
        """It finds all @@code and @@code-output directives."""
        template_path = FIXTURES_DIR / "simple.template.md"
        result = parse_template(template_path)

        assert len(result.directives) == 6

        code_directives = [d for d in result.directives if d.type == "code"]
        output_directives = [d for d in result.directives if d.type == "code-output"]

        assert len(code_directives) == 4
        assert len(output_directives) == 2

    def test_directive_properties(self):
        """It correctly parses directive properties."""
        template_path = FIXTURES_DIR / "simple.template.md"
        result = parse_template(template_path)

        first_code = next(d for d in result.directives if d.type == "code")
        assert first_code.notebook_id == "sample"
        assert first_code.cell_id == "print-hello"
        assert first_code.line_number > 0

    def test_nonexistent_file(self):
        """It raises ParseError for nonexistent file."""
        with pytest.raises(ParseError) as exc_info:
            parse_template(Path("/nonexistent/file.template.md"))

        assert "File not found" in str(exc_info.value)

    def test_invalid_frontmatter(self, tmp_path):
        """It raises ParseError for invalid frontmatter."""
        template = tmp_path / "test.template.md"
        template.write_text("---\ninvalid yaml: [\n---\ncontent")

        with pytest.raises(ParseError) as exc_info:
            parse_template(template)

        assert "Invalid frontmatter" in str(exc_info.value)

    def test_missing_notebooks_in_frontmatter(self, tmp_path):
        """It raises error when notebooks field is missing."""
        template = tmp_path / "test.template.md"
        template.write_text("---\nother: value\n---\n@@code test:cell")

        result = parse_template(template)
        assert result.notebook_refs == {}


class TestParseNotebookRefs:
    """Tests for _parse_notebook_refs function."""

    def test_parse_single_ref(self):
        """It parses a single notebook reference."""
        frontmatter = {
            "notebooks": [
                {"id": "test", "path": "test.ipynb"}
            ]
        }

        result = _parse_notebook_refs(frontmatter, Path("test.md"))

        assert len(result) == 1
        assert "test" in result
        assert result["test"].path == "test.ipynb"
        assert result["test"].execute is True  # Default value

    def test_parse_ref_with_execute_true(self):
        """It parses a notebook reference with execute=True."""
        frontmatter = {
            "notebooks": [
                {"id": "test", "path": "test.ipynb", "execute": True}
            ]
        }

        result = _parse_notebook_refs(frontmatter, Path("test.md"))

        assert len(result) == 1
        assert result["test"].execute is True

    def test_parse_ref_with_execute_false(self):
        """It parses a notebook reference with execute=False."""
        frontmatter = {
            "notebooks": [
                {"id": "test", "path": "test.ipynb", "execute": False}
            ]
        }

        result = _parse_notebook_refs(frontmatter, Path("test.md"))

        assert len(result) == 1
        assert result["test"].execute is False

    def test_execute_must_be_boolean(self):
        """It raises error when execute is not a boolean."""
        frontmatter = {
            "notebooks": [
                {"id": "test", "path": "test.ipynb", "execute": "yes"}
            ]
        }

        with pytest.raises(ParseError) as exc_info:
            _parse_notebook_refs(frontmatter, Path("test.md"))

        assert "'execute' must be a boolean" in str(exc_info.value)

    def test_parse_multiple_refs(self):
        """It parses multiple notebook references."""
        frontmatter = {
            "notebooks": [
                {"id": "first", "path": "first.ipynb"},
                {"id": "second", "path": "second.ipynb"},
            ]
        }

        result = _parse_notebook_refs(frontmatter, Path("test.md"))

        assert len(result) == 2
        assert "first" in result
        assert "second" in result

    def test_missing_id_raises_error(self):
        """It raises error when id is missing."""
        frontmatter = {
            "notebooks": [
                {"path": "test.ipynb"}
            ]
        }

        with pytest.raises(ParseError) as exc_info:
            _parse_notebook_refs(frontmatter, Path("test.md"))

        assert "missing 'id'" in str(exc_info.value)

    def test_missing_path_raises_error(self):
        """It raises error when path is missing."""
        frontmatter = {
            "notebooks": [
                {"id": "test"}
            ]
        }

        with pytest.raises(ParseError) as exc_info:
            _parse_notebook_refs(frontmatter, Path("test.md"))

        assert "missing 'path'" in str(exc_info.value)

    def test_non_list_notebooks_raises_error(self):
        """It raises error when notebooks is not a list."""
        frontmatter = {
            "notebooks": "not a list"
        }

        with pytest.raises(ParseError) as exc_info:
            _parse_notebook_refs(frontmatter, Path("test.md"))

        assert "must be a list" in str(exc_info.value)


class TestFindDirectives:
    """Tests for _find_directives function."""

    def test_finds_code_directive(self):
        """It finds @@code directives."""
        body = "Some text\n@@code notebook:cell-id\nMore text"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].type == "code"
        assert result[0].notebook_id == "notebook"
        assert result[0].cell_id == "cell-id"

    def test_finds_code_output_directive(self):
        """It finds @@code-output directives."""
        body = "@@code-output notebook:cell-id"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].type == "code-output"

    def test_finds_multiple_directives(self):
        """It finds multiple directives in the body."""
        body = """
@@code nb1:cell1
Some text
@@code-output nb1:cell1
@@code nb2:cell2
"""

        result = _find_directives(body, start_line=1)

        assert len(result) == 3

    def test_ignores_non_directive_lines(self):
        """It ignores lines that don't start with @@."""
        body = """
Regular text
@@code nb:cell
More text
@not-a-directive
"""

        result = _find_directives(body, start_line=1)

        assert len(result) == 1

    def test_handles_extra_whitespace(self):
        """It handles extra whitespace around directives."""
        body = "  @@code  nb:cell  \n"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].notebook_id == "nb"
        assert result[0].cell_id == "cell"

    def test_tracks_line_numbers(self):
        """It correctly tracks line numbers."""
        body = "Line 1\nLine 2\n@@code nb:cell\nLine 4"

        result = _find_directives(body, start_line=5)

        assert len(result) == 1
        assert result[0].line_number == 7  # 5 + 2

    def test_handles_underscores_in_ids(self):
        """It handles underscores in notebook and cell IDs."""
        body = "@@code my_notebook:my_cell_id"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].notebook_id == "my_notebook"
        assert result[0].cell_id == "my_cell_id"

    def test_handles_hyphens_in_ids(self):
        """It handles hyphens in notebook and cell IDs."""
        body = "@@code my-notebook:my-cell-id"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].notebook_id == "my-notebook"
        assert result[0].cell_id == "my-cell-id"

    def test_parses_limit_lines_with_code_directive(self):
        """It parses limit-lines parameter on @@code directive (ignored but accepted)."""
        body = "@@code notebook:cell-id limit-lines=5"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].type == "code"

    def test_parses_limit_lines_parameter(self):
        """It parses the optional limit-lines parameter."""
        body = "@@code-output notebook:cell-id limit-lines=10"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].limit_lines == 10
        assert result[0].limit_chars is None

    def test_parses_limit_chars_parameter(self):
        """It parses the optional limit-chars parameter."""
        body = "@@code-output notebook:cell-id limit-chars=100"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].limit_chars == 100
        assert result[0].limit_lines is None

    def test_parses_both_limit_parameters(self):
        """It parses both limit-lines and limit-chars parameters."""
        body = "@@code-output notebook:cell-id limit-lines=10 limit-chars=100"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].limit_lines == 10
        assert result[0].limit_chars == 100

    def test_parses_both_limit_parameters_reverse_order(self):
        """It parses both limit parameters in reverse order."""
        body = "@@code-output notebook:cell-id limit-chars=100 limit-lines=10"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].limit_lines == 10
        assert result[0].limit_chars == 100

    def test_limits_default_to_none(self):
        """It defaults limits to None when not specified."""
        body = "@@code-output notebook:cell-id"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].limit_lines is None
        assert result[0].limit_chars is None

    def test_parses_limit_lines_with_code_directive(self):
        """It parses limit-lines parameter on @@code directive (though it's only used for code-output)."""
        body = "@@code notebook:cell-id limit-lines=5"

        result = _find_directives(body, start_line=1)

        # CodeDirective doesn't store limit_lines since it's not used
        assert len(result) == 1
        assert result[0].type == "code"
        assert not hasattr(result[0], "limit_lines") or result[0].limit_lines is None

    def test_handles_different_limit_values(self):
        """It handles various limit values."""
        body = """
@@code-output nb:cell1 limit-lines=1
@@code-output nb:cell2 limit-lines=100
@@code-output nb:cell3 limit-chars=999
"""

        result = _find_directives(body, start_line=1)

        assert len(result) == 3
        assert result[0].limit_lines == 1
        assert result[1].limit_lines == 100
        assert result[2].limit_chars == 999

    def test_handles_extra_whitespace_with_limits(self):
        """It handles extra whitespace around directives with limits."""
        body = "  @@code-output  nb:cell  limit-lines=10  "

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].notebook_id == "nb"
        assert result[0].cell_id == "cell"
        assert result[0].limit_lines == 10


class TestCodeFigureDirective:
    """Tests for @@code-figure directive parsing."""

    def test_parses_code_figure_directive(self):
        """It parses the basic code-figure directive."""
        body = "@@code-figure notebook:cell-id"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].type == "code-figure"
        assert result[0].notebook_id == "notebook"
        assert result[0].cell_id == "cell-id"

    def test_parses_code_figure_with_format_jpg(self):
        """It parses the format parameter for jpg."""
        body = "@@code-figure notebook:cell-id format=jpg"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].format == "jpg"

    def test_parses_code_figure_with_format_png(self):
        """It parses the format parameter for png."""
        body = "@@code-figure notebook:cell-id format=png"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].format == "png"

    def test_parses_code_figure_with_quality(self):
        """It parses the quality parameter."""
        body = "@@code-figure notebook:cell-id quality=90"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].quality == 90

    def test_parses_code_figure_with_format_and_quality(self):
        """It parses both format and quality parameters."""
        body = "@@code-figure notebook:cell-id format=jpg quality=90"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].format == "jpg"
        assert result[0].quality == 90

    def test_parses_code_figure_with_format_and_quality_reverse(self):
        """It parses format and quality in reverse order."""
        body = "@@code-figure notebook:cell-id quality=90 format=png"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].format == "png"
        assert result[0].quality == 90

    def test_code_figure_defaults_to_jpg_and_quality_85(self):
        """It sets default format to jpg and quality to 85 when not specified."""
        body = "@@code-figure notebook:cell-id"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].format == "jpg"
        assert result[0].quality == 85


class TestNotebookRefImageFolder:
    """Tests for image_folder in notebook references."""

    def test_parse_notebook_ref_with_image_folder(self):
        """It parses the optional image_folder field."""
        frontmatter_data = {
            "notebooks": [
                {"id": "nb1", "path": "notebook.ipynb", "image_folder": "images/nb1"}
            ]
        }

        result = _parse_notebook_refs(frontmatter_data, Path("test.md"))

        assert "nb1" in result
        assert result["nb1"].image_folder == "images/nb1"

    def test_parse_notebook_ref_without_image_folder(self):
        """It handles missing image_folder (defaults to None)."""
        frontmatter_data = {
            "notebooks": [
                {"id": "nb1", "path": "notebook.ipynb"}
            ]
        }

        result = _parse_notebook_refs(frontmatter_data, Path("test.md"))

        assert "nb1" in result
        assert result["nb1"].image_folder is None

    def test_image_folder_must_be_string(self):
        """It raises error when image_folder is not a string."""
        frontmatter_data = {
            "notebooks": [
                {"id": "nb1", "path": "notebook.ipynb", "image_folder": 123}
            ]
        }

        with pytest.raises(ParseError, match="image_folder.*must be a string"):
            _parse_notebook_refs(frontmatter_data, Path("test.md"))

    def test_parse_notebook_ref_with_all_fields(self):
        """It parses notebook ref with execute and image_folder."""
        frontmatter_data = {
            "notebooks": [
                {
                    "id": "nb1",
                    "path": "notebook.ipynb",
                    "execute": False,
                    "image_folder": "assets/images"
                }
            ]
        }

        result = _parse_notebook_refs(frontmatter_data, Path("test.md"))

        assert "nb1" in result
        assert result["nb1"].execute is False
        assert result["nb1"].image_folder == "assets/images"


class TestParseScriptRefs:
    """Tests for _parse_script_refs function."""

    def test_parse_single_ref(self):
        """It parses a single script reference."""
        frontmatter = {
            "scripts": [
                {"id": "test", "path": "test_agent.py"}
            ]
        }

        result = _parse_script_refs(frontmatter, Path("test.md"))

        assert len(result) == 1
        assert "test" in result
        assert result["test"].path == "test_agent.py"

    def test_parse_multiple_refs(self):
        """It parses multiple script references."""
        frontmatter = {
            "scripts": [
                {"id": "first", "path": "first.py"},
                {"id": "second", "path": "second.py"},
            ]
        }

        result = _parse_script_refs(frontmatter, Path("test.md"))

        assert len(result) == 2
        assert "first" in result
        assert "second" in result

    def test_missing_id_raises_error(self):
        """It raises error when id is missing."""
        frontmatter = {
            "scripts": [
                {"path": "test.py"}
            ]
        }

        with pytest.raises(ParseError, match="missing 'id'"):
            _parse_script_refs(frontmatter, Path("test.md"))

    def test_missing_path_raises_error(self):
        """It raises error when path is missing."""
        frontmatter = {
            "scripts": [
                {"id": "test"}
            ]
        }

        with pytest.raises(ParseError, match="missing 'path'"):
            _parse_script_refs(frontmatter, Path("test.md"))

    def test_non_list_scripts_raises_error(self):
        """It raises error when scripts is not a list."""
        frontmatter = {
            "scripts": "not a list"
        }

        with pytest.raises(ParseError, match="must be a list"):
            _parse_script_refs(frontmatter, Path("test.md"))

    def test_non_dict_entry_raises_error(self):
        """It raises error when a script entry is not a dictionary."""
        frontmatter = {
            "scripts": ["not a dict"]
        }

        with pytest.raises(ParseError, match="must be a dictionary"):
            _parse_script_refs(frontmatter, Path("test.md"))

    def test_no_scripts_key_returns_empty(self):
        """It returns empty dict when no scripts key in frontmatter."""
        frontmatter = {"notebooks": []}

        result = _parse_script_refs(frontmatter, Path("test.md"))
        assert result == {}


class TestScriptRefsInTemplate:
    """Tests for script refs in full template parsing."""

    def test_parse_script_template(self):
        """It parses a template with script references."""
        template_path = FIXTURES_DIR / "script-template.template.md"
        result = parse_template(template_path)

        assert len(result.script_refs) == 1
        assert "test" in result.script_refs
        assert result.script_refs["test"].path == "scripts/sample.py"

    def test_parse_mixed_template(self):
        """It parses a template with both notebook and script references."""
        template_path = FIXTURES_DIR / "mixed-template.template.md"
        result = parse_template(template_path)

        assert len(result.notebook_refs) == 1
        assert len(result.script_refs) == 1
        assert "nb" in result.notebook_refs
        assert "script" in result.script_refs

    def test_id_collision_raises_error(self, tmp_path):
        """It raises ParseError when a notebook and script share the same ID."""
        template = tmp_path / "test.template.md"
        template.write_text(
            "---\n"
            "notebooks:\n"
            "  - id: shared\n"
            "    path: notebook.ipynb\n"
            "scripts:\n"
            "  - id: shared\n"
            "    path: script.py\n"
            "---\n"
            "\n"
            "@@code shared:cell\n"
        )

        with pytest.raises(ParseError, match="ID collision"):
            parse_template(template)

    def test_template_without_scripts_has_empty_script_refs(self):
        """It has empty script_refs for templates without scripts."""
        template_path = FIXTURES_DIR / "simple.template.md"
        result = parse_template(template_path)

        assert result.script_refs == {}


class TestCodeDirectiveLineParams:
    """Tests for lines= and strip-spaces= parameters on @@code directive."""

    def test_parse_lines_range(self):
        """It parses lines=2-5 into a (2, 5) tuple."""
        body = "@@code notebook:cell lines=2-5"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].type == "code"
        assert result[0].lines == (2, 5)

    def test_parse_lines_single(self):
        """It parses lines=3 (single line) into a (3, 3) tuple."""
        body = "@@code notebook:cell lines=3"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].lines == (3, 3)

    def test_parse_strip_spaces(self):
        """It parses strip-spaces=4 into integer 4."""
        body = "@@code notebook:cell strip-spaces=4"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].strip_spaces == 4

    def test_parse_lines_and_strip_spaces_together(self):
        """It parses both lines and strip-spaces together."""
        body = "@@code notebook:cell lines=2-4 strip-spaces=4"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].lines == (2, 4)
        assert result[0].strip_spaces == 4

    def test_parse_reverse_order(self):
        """It parses strip-spaces and lines in reverse order."""
        body = "@@code notebook:cell strip-spaces=4 lines=2-4"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].lines == (2, 4)
        assert result[0].strip_spaces == 4

    def test_defaults_to_none(self):
        """It defaults lines and strip_spaces to None when not specified."""
        body = "@@code notebook:cell"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].lines is None
        assert result[0].strip_spaces is None

    def test_with_extra_whitespace(self):
        """It handles extra whitespace around directive with line params."""
        body = "  @@code  notebook:cell  lines=1-3  strip-spaces=2  "

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].lines == (1, 3)
        assert result[0].strip_spaces == 2

    def test_lines_not_parsed_for_code_output(self):
        """It does not pass lines to CodeOutputDirective."""
        body = "@@code-output notebook:cell lines=2-5"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].type == "code-output"
        assert not hasattr(result[0], "lines")

    def test_strip_spaces_not_parsed_for_code_output(self):
        """It does not pass strip-spaces to CodeOutputDirective."""
        body = "@@code-output notebook:cell strip-spaces=4"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].type == "code-output"
        assert not hasattr(result[0], "strip_spaces")

    def test_lines_clamps_from_to_1(self):
        """It clamps the 'from' value to 1 minimum."""
        body = "@@code notebook:cell lines=0-5"

        result = _find_directives(body, start_line=1)

        assert len(result) == 1
        assert result[0].lines == (1, 5)
