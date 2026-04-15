"""Tests for the script_reader module."""

from pathlib import Path

import pytest

from codoc.script_reader import (
    parse_script_blocks,
    get_block_by_id,
    detect_language,
    BLOCK_START_PATTERN,
    BLOCK_END_PATTERN,
)
from codoc.errors import ScriptNotFoundError, BlockNotFoundError, ParseError


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SCRIPTS_DIR = FIXTURES_DIR / "scripts"


class TestBlockPatterns:
    """Tests for the regex patterns."""

    def test_block_start_pattern_matches(self):
        """It matches a valid block start marker."""
        match = BLOCK_START_PATTERN.match("# @block=setup")
        assert match is not None
        assert match.group(1) == "setup"

    def test_block_start_pattern_with_spaces(self):
        """It matches block start with extra spaces."""
        match = BLOCK_START_PATTERN.match("# @block = setup")
        assert match is not None
        assert match.group(1) == "setup"

    def test_block_start_pattern_with_hyphen_id(self):
        """It matches block IDs with hyphens."""
        match = BLOCK_START_PATTERN.match("# @block=make-request")
        assert match is not None
        assert match.group(1) == "make-request"

    def test_block_start_pattern_with_underscore_id(self):
        """It matches block IDs with underscores."""
        match = BLOCK_START_PATTERN.match("# @block=my_block")
        assert match is not None
        assert match.group(1) == "my_block"

    def test_block_start_pattern_rejects_non_comment(self):
        """It rejects lines that don't start with #."""
        match = BLOCK_START_PATTERN.match("@block=setup")
        assert match is None

    def test_block_end_pattern_matches(self):
        """It matches a valid block end marker."""
        match = BLOCK_END_PATTERN.match("# @end")
        assert match is not None

    def test_block_end_pattern_with_spaces(self):
        """It matches block end with extra spaces."""
        match = BLOCK_END_PATTERN.match("#  @end  ")
        assert match is not None

    def test_block_end_pattern_rejects_non_comment(self):
        """It rejects lines that don't start with #."""
        match = BLOCK_END_PATTERN.match("@end")
        assert match is None


class TestParseScriptBlocks:
    """Tests for parse_script_blocks function."""

    def test_parse_sample_script(self):
        """It parses the sample.py fixture correctly."""
        blocks = parse_script_blocks(SCRIPTS_DIR / "sample.py")

        assert len(blocks) == 3
        assert "setup" in blocks
        assert "make-request" in blocks
        assert "print-result" in blocks

    def test_setup_block_content(self):
        """It extracts the correct content for the setup block."""
        blocks = parse_script_blocks(SCRIPTS_DIR / "sample.py")

        setup = blocks["setup"]
        assert "from openai import OpenAI" in setup.source
        assert "client = OpenAI()" in setup.source
        # Should NOT contain the markers
        assert "# @block" not in setup.source
        assert "# @end" not in setup.source

    def test_block_line_numbers(self):
        """It tracks correct line numbers."""
        blocks = parse_script_blocks(SCRIPTS_DIR / "sample.py")

        setup = blocks["setup"]
        assert setup.start_line > 0
        assert setup.end_line > setup.start_line

    def test_block_full_source_includes_markers(self):
        """It includes markers in full_source."""
        blocks = parse_script_blocks(SCRIPTS_DIR / "sample.py")

        setup = blocks["setup"]
        assert any("@block=setup" in line for line in setup.full_source)
        assert any("@end" in line for line in setup.full_source)

    def test_nonexistent_file_raises_error(self):
        """It raises ScriptNotFoundError for a nonexistent file."""
        with pytest.raises(ScriptNotFoundError):
            parse_script_blocks(Path("/nonexistent/script.py"))

    def test_unclosed_block_raises_error(self, tmp_path):
        """It raises ParseError for an unclosed block."""
        script = tmp_path / "bad.py"
        script.write_text("# @block=open\nprint('hello')\n")

        with pytest.raises(ParseError, match="Unclosed block"):
            parse_script_blocks(script)

    def test_nested_block_raises_error(self, tmp_path):
        """It raises ParseError for nested blocks."""
        script = tmp_path / "bad.py"
        script.write_text(
            "# @block=outer\n"
            "print('outer')\n"
            "# @block=inner\n"
            "print('inner')\n"
            "# @end\n"
            "# @end\n"
        )

        with pytest.raises(ParseError, match="Nested block"):
            parse_script_blocks(script)

    def test_duplicate_block_id_raises_error(self, tmp_path):
        """It raises ParseError for duplicate block IDs."""
        script = tmp_path / "bad.py"
        script.write_text(
            "# @block=dup\n"
            "print('first')\n"
            "# @end\n"
            "# @block=dup\n"
            "print('second')\n"
            "# @end\n"
        )

        with pytest.raises(ParseError, match="Duplicate block ID"):
            parse_script_blocks(script)

    def test_end_without_start_raises_error(self, tmp_path):
        """It raises ParseError for # @end without a matching # @block."""
        script = tmp_path / "bad.py"
        script.write_text("print('hello')\n# @end\n")

        with pytest.raises(ParseError, match="without matching"):
            parse_script_blocks(script)

    def test_empty_file_returns_empty_dict(self, tmp_path):
        """It returns an empty dict for a file with no blocks."""
        script = tmp_path / "empty.py"
        script.write_text("# No blocks here\nprint('hello')\n")

        blocks = parse_script_blocks(script)
        assert blocks == {}

    def test_block_content_is_trimmed(self, tmp_path):
        """It trims leading and trailing blank lines from block content."""
        script = tmp_path / "padded.py"
        script.write_text(
            "# @block=trimmed\n"
            "\n"
            "print('hello')\n"
            "\n"
            "# @end\n"
        )

        blocks = parse_script_blocks(script)
        assert blocks["trimmed"].source == "print('hello')"

    def test_multiline_block_content(self, tmp_path):
        """It preserves multiple lines in block content."""
        script = tmp_path / "multi.py"
        script.write_text(
            "# @block=multi\n"
            "a = 1\n"
            "b = 2\n"
            "c = a + b\n"
            "# @end\n"
        )

        blocks = parse_script_blocks(script)
        assert blocks["multi"].source == "a = 1\nb = 2\nc = a + b"

class TestGetBlockById:
    """Tests for get_block_by_id function."""

    def test_get_existing_block(self):
        """It returns the correct block by ID."""
        block = get_block_by_id(SCRIPTS_DIR / "sample.py", "setup")

        assert block.block_id == "setup"
        assert "from openai import OpenAI" in block.source

    def test_get_nonexistent_block_raises_error(self):
        """It raises BlockNotFoundError for a missing block ID."""
        with pytest.raises(BlockNotFoundError, match="nonexistent"):
            get_block_by_id(SCRIPTS_DIR / "sample.py", "nonexistent")

    def test_get_block_from_nonexistent_file_raises_error(self):
        """It raises ScriptNotFoundError for a missing file."""
        with pytest.raises(ScriptNotFoundError):
            get_block_by_id(Path("/nonexistent/script.py"), "setup")


class TestDetectLanguage:
    """Tests for detect_language function."""

    def test_python_extension(self):
        """It detects Python from .py extension."""
        assert detect_language(Path("test.py")) == "python"

    def test_unknown_extension_returns_text(self):
        """It returns 'text' for unknown extensions."""
        assert detect_language(Path("test.xyz")) == "text"
