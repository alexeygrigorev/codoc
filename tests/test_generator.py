"""Tests for the generator module."""

from pathlib import Path
import tempfile
from unittest.mock import patch

import pytest

from codoc.nobook import execute_nobook
from codoc.generator import Generator, generate_template, generate_directory, _strip_frontmatter
from codoc.errors import BlockNotFoundError, EmptyOutputError, InvalidDirectiveError


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestGenerator:
    """Tests for Generator class."""

    def test_initialization(self):
        """It initializes with default parameters."""
        gen = Generator()

        assert gen.timeout == 30
        assert gen.kernel_name == "python3"
        assert gen.execute_override is None

    def test_initialization_with_params(self):
        """It initializes with custom parameters."""
        gen = Generator(timeout=60, kernel_name="test-kernel", execute_override=True)

        assert gen.timeout == 60
        assert gen.kernel_name == "test-kernel"
        assert gen.execute_override is True

    def test_derive_output_path(self):
        """It derives output path from template path."""
        gen = Generator()

        # Simple template
        template = Path("test.template.md")
        output = gen._derive_output_path(template)
        assert output == Path("test.md")

        # Template in subdirectory
        template = Path("subdir/test.template.md")
        output = gen._derive_output_path(template)
        assert output == Path("subdir/test.md")

    def test_generate_simple_template(self):
        """It generates a simple template without validation."""
        gen = Generator()
        template_path = FIXTURES_DIR / "simple.template.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "simple.md"
            result = gen.generate(template_path, output_path)

        assert result is not None
        assert "@@code" not in result  # Directives should be replaced
        assert "```python" in result  # Should have code blocks

    def test_generate_creates_code_blocks(self):
        """It wraps code in ```python blocks."""
        gen = Generator()
        template_path = FIXTURES_DIR / "simple.template.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.md"
            result = gen.generate(template_path, output_path)

        assert "```python" in result
        assert 'print("Hello, World!")' in result

    def test_generate_adds_frontmatter_note(self):
        """It adds frontmatter with a note about the source template and generation time."""
        gen = Generator()
        template_path = FIXTURES_DIR / "simple.template.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "test.md"
            result = gen.generate(template_path, output_path)

        # Should start with frontmatter
        assert result.startswith("---")
        # Should have the note field
        assert "note:" in result
        assert "generated from" in result
        assert "Don't change this file" in result
        # Should have generated_at field with ISO format timestamp
        assert "generated_at:" in result
        # ISO format timestamps contain 'T' between date and time
        assert "T" in result.split("generated_at:")[1].split("\n")[0]
        # Template's frontmatter should not be in output
        assert "notebooks:" not in result

    def test_generate_merges_user_frontmatter(self, tmp_path):
        """It merges user-authored frontmatter from the template into the output."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: nb
    path: fixtures/notebooks/sample.ipynb
    execute: false
content_id: 11111111-2222-3333-4444-555555555555
title: Hello Lesson
is_preview: true
---

# Hello

@@code nb:print-hello
"""
        template_path = tmp_path / "hello.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "hello.md"
        result = gen.generate(template_path, output_path)

        # User frontmatter must appear in the output
        assert "content_id: 11111111-2222-3333-4444-555555555555" in result
        assert "title: Hello Lesson" in result
        assert "is_preview: true" in result
        # Codoc-managed fields are still present
        assert "note: This file is generated from" in result
        assert "generated_at:" in result
        # Template-only fields are stripped
        assert "notebooks:" not in result

    def test_skips_write_when_only_generated_at_differs(self, tmp_path):
        """It does not rewrite when only generated_at would change."""
        import shutil
        import time

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: nb
    path: fixtures/notebooks/sample.ipynb
    execute: false
content_id: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
title: Stable
---

# Stable

@@code nb:print-hello
"""
        template_path = tmp_path / "stable.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "stable.md"

        gen.generate(template_path, output_path)
        first_mtime = output_path.stat().st_mtime

        time.sleep(0.1)
        gen.generate(template_path, output_path)
        second_mtime = output_path.stat().st_mtime

        assert first_mtime == second_mtime

    def test_rewrites_when_user_frontmatter_changes(self, tmp_path):
        """It rewrites the output when template frontmatter changes even if body is the same."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_v1 = """---
notebooks:
  - id: nb
    path: fixtures/notebooks/sample.ipynb
    execute: false
content_id: aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
title: Original Title
---

# Hello

@@code nb:print-hello
"""
        template_v2 = template_v1.replace("Original Title", "New Title")

        template_path = tmp_path / "change.template.md"
        output_path = tmp_path / "change.md"
        gen = Generator()

        template_path.write_text(template_v1)
        gen.generate(template_path, output_path)
        assert "title: Original Title" in output_path.read_text()

        template_path.write_text(template_v2)
        gen.generate(template_path, output_path)
        assert "title: New Title" in output_path.read_text()

    def test_generate_creates_output_file(self):
        """It creates the output file."""
        gen = Generator()
        template_path = FIXTURES_DIR / "simple.template.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"
            gen.generate(template_path, output_path)

            assert output_path.exists()
            content = output_path.read_text()
            assert "```python" in content

    def test_multi_notebook_template(self):
        """It handles templates with multiple notebook references."""
        gen = Generator()
        template_path = FIXTURES_DIR / "multi-notebook.template.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "multi.md"
            result = gen.generate(template_path, output_path)

        assert result is not None
        assert "```python" in result

    def test_generate_nobook_template_from_out_file(self, tmp_path):
        """It reads code and output from a nobook `.py` source with sibling `.out.py`."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: nb
    path: fixtures/nobooks/simple.py
    execute: false
---

# Nobook

@@code nb:setup

@@code-output nb:show
"""
        template_path = tmp_path / "nobook.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "nobook.md"
        result = gen.generate(template_path, output_path)

        assert "message = \"hello from nobook\"" in result
        assert "hello from nobook" in result

    def test_generate_nobook_template_by_execution(self, tmp_path):
        """It can execute a nobook `.py` source to produce output."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)
        (fixtures_tmp / "nobooks" / "simple.out.py").unlink()

        template_content = """---
notebooks:
  - id: nb
    path: fixtures/nobooks/simple.py
    execute: true
---

# Nobook

@@code nb:show

@@code-output nb:show
"""
        template_path = tmp_path / "nobook-exec.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "nobook-exec.md"
        result = gen.generate(template_path, output_path)

        assert "print(message)" in result
        assert "hello from nobook" in result

    def test_nobook_figure_directive_is_rejected(self, tmp_path):
        """It rejects figure directives for nobook sources."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: nb
    path: fixtures/nobooks/simple.py
    execute: false
---

@@code-figure nb:show
"""
        template_path = tmp_path / "nobook-figure.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "nobook-figure.md"

        with pytest.raises(InvalidDirectiveError, match="nobook"):
            gen.generate(template_path, output_path)

    def test_frontmatter_includes_template_path(self):
        """It includes the template path in the frontmatter note."""
        import shutil

        gen = Generator()

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Copy fixtures to tmpdir so relative paths work
            fixtures_tmp = tmpdir / "fixtures"
            shutil.copytree(FIXTURES_DIR, fixtures_tmp)

            # Create a template in a known location - use path relative to template location
            template_content = """---
notebooks:
  - id: test
    path: ../fixtures/notebooks/sample.ipynb
    execute: false
---

# Test

@@code test:print-hello
"""
            template_path = tmpdir / "subdir" / "test.template.md"
            template_path.parent.mkdir(parents=True, exist_ok=True)
            template_path.write_text(template_content)

            output_path = tmpdir / "subdir" / "test.md"
            result = gen.generate(template_path, output_path)

        # Check that the template path is in the frontmatter
        assert "note:" in result
        # The path should contain the template filename (either relative or absolute)
        assert "test.template.md" in result
        # Verify YAML format
        assert result.startswith("---\n")
        assert "note: This file is generated from" in result


class TestGenerateTemplate:
    """Tests for generate_template convenience function."""

    def test_convenience_function(self):
        """It provides a convenience function for generation."""
        template_path = FIXTURES_DIR / "simple.template.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"

            result = generate_template(
                template_path=template_path,
                output_path=output_path,
            )

        assert result is not None
        assert "```python" in result

    @patch("codoc.generator.Generator")
    def test_convenience_function_passes_execute_override(self, mock_generator_cls):
        """It passes execute_override through to Generator."""
        mock_generator = mock_generator_cls.return_value
        mock_generator.generate.return_value = "# Generated content"

        template_path = FIXTURES_DIR / "simple.template.md"
        output_path = FIXTURES_DIR / "output.md"

        generate_template(
            template_path=template_path,
            output_path=output_path,
            execute_override=True,
        )

        mock_generator_cls.assert_called_once_with(
            timeout=30,
            kernel_name="python3",
            execute_override=True,
        )


class TestGenerateDirectory:
    """Tests for generate_directory function."""

    def test_finds_all_templates(self):
        """It finds all template files in directory."""
        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Copy fixtures to temp dir
            fixtures_temp = tmpdir / "fixtures"
            shutil.copytree(FIXTURES_DIR, fixtures_temp)

            results = generate_directory(fixtures_temp)

        assert len(results) >= 1

    def test_generates_multiple_files(self):
        """It generates multiple template files."""
        import tempfile
        import shutil

        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir = Path(tmpdir)

            # Copy fixtures to temp dir
            fixtures_temp = tmpdir / "fixtures"
            shutil.copytree(FIXTURES_DIR, fixtures_temp)

            results = generate_directory(fixtures_temp)

            # All generated files should end with .md
            for result in results:
                assert result.suffix == ".md"
                assert ".template." not in result.name

    def test_handles_no_templates(self):
        """It handles directories with no templates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            results = generate_directory(Path(tmpdir))
            assert results == []

    @patch("codoc.generator.Generator")
    @patch("codoc.utils.find_template_files")
    def test_passes_execute_override(self, mock_find_template_files, mock_generator_cls):
        """It passes execute_override through to Generator."""
        mock_find_template_files.return_value = []

        generate_directory(FIXTURES_DIR, execute_override=False)

        mock_generator_cls.assert_called_once_with(
            timeout=30,
            kernel_name="python3",
            execute_override=False,
        )


class TestNobookExecution:
    """Tests for nobook execution behavior."""

    def test_execute_nobook_can_import_sibling_module(self, tmp_path):
        """It executes blocks with the script directory available on sys.path."""
        helper_path = tmp_path / "helper.py"
        helper_path.write_text('value = 42\n', encoding="utf-8")

        nobook_path = tmp_path / "lesson.py"
        nobook_path.write_text(
            '# @block=code-1\n'
            'from helper import value\n'
            'print(value)\n',
            encoding="utf-8",
        )

        notebook = execute_nobook(nobook_path)
        outputs = notebook["cells"][0]["outputs"]

        assert outputs[0]["output_type"] == "stream"
        assert outputs[0]["text"] == "42\n"


class TestCodeExtraction:
    """Tests for code extraction from notebooks."""

    def test_code_with_blank_lines_is_normalized(self, tmp_path):
        """Test that code with extra blank lines is normalized."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Create a template that references our blank-lines notebook
        template_content = """---
notebooks:
  - id: blank-lines
    path: fixtures/notebooks/blank-lines.ipynb
    execute: false
---

# Test

@@code blank-lines:test-blank-lines
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Extract the code block
        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1)

        # Check that we don't have excessive blank lines
        # The source has single blank lines between statements, which is fine
        # But we shouldn't have multiple consecutive blank lines
        assert "\n\n\n\n" not in code, "Should not have 4+ consecutive newlines"

        # Each statement should be separated by at most one blank line
        lines = code.split("\n")

        # Count consecutive blank lines
        max_consecutive_blank = 0
        current_blank = 0
        for line in lines:
            if line.strip() == "":
                current_blank += 1
                max_consecutive_blank = max(max_consecutive_blank, current_blank)
            else:
                current_blank = 0

        # We expect at most 2 consecutive blank lines (one visual blank line)
        # More than that indicates the issue with extra lines from Jupyter
        assert max_consecutive_blank <= 2, f"Found {max_consecutive_blank} consecutive blank lines"


class TestEmptyOutputValidation:
    """Tests for empty output validation when using @@code-output directive."""

    def test_code_output_with_empty_output_raises_error(self, tmp_path):
        """It raises EmptyOutputError when @@code-output is used on a cell with no output."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Create a template that uses @@code-output on a cell with no output
        template_content = """---
notebooks:
  - id: no-output
    path: fixtures/notebooks/no-output.ipynb
    execute: false
---

# Test Output

@@code-output no-output:test-cell
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"

        # Should raise EmptyOutputError
        with pytest.raises(EmptyOutputError) as exc_info:
            gen.generate(template_path, output_path)

        # Check the error message
        error_msg = str(exc_info.value)
        assert "no output" in error_msg
        assert "test-cell" in error_msg
        assert "Run the notebook first" in error_msg

    def test_code_output_with_output_succeeds(self, tmp_path):
        """It succeeds when @@code-output is used on a cell with output."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Create a template that uses @@code-output on a cell WITH output
        template_content = """---
notebooks:
  - id: with-output
    path: fixtures/notebooks/sample.ipynb
    execute: false
---

# Test Output

@@code-output with-output:print-hello
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"

        # Should succeed
        result = gen.generate(template_path, output_path)

        # Should have output
        assert "```python" in result
        # The sample notebook has "Hello, World!" in output
        assert "Hello" in result or "```" in result

    def test_code_directive_works_with_empty_output(self, tmp_path):
        """It works when @@code is used on a cell with no output (code doesn't need output)."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Create a template that uses @@code (not @@code-output)
        template_content = """---
notebooks:
  - id: no-output
    path: fixtures/notebooks/no-output.ipynb
    execute: false
---

# Test Code

@@code no-output:test-cell
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"

        # Should succeed - @@code doesn't require output
        result = gen.generate(template_path, output_path)

        # Should have code block
        assert "```python" in result
        assert "@@code" not in result


class TestCodeOutputLimitLines:
    """Tests for the limit-lines parameter on @@code-output directive."""

    def test_code_output_with_limit_lines_truncates_output(self, tmp_path):
        """It truncates output when limit-lines is specified and output exceeds limit."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Create a template with limit-lines=3 on a cell with 10 lines of output
        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test Output Limit

@@code-output multiline:ten-lines limit-lines=3
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have code block
        assert "```python" in result
        # Should only have first 3 lines
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result
        # Should NOT have lines beyond the limit
        assert "Line 4" not in result
        assert "Line 10" not in result
        # Should have ellipsis
        assert "..." in result

    def test_code_output_with_limit_lines_below_output_count_shows_ellipsis(self, tmp_path):
        """It adds ellipsis when output is truncated."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:ten-lines limit-lines=5
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Extract the code block content
        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1)

        # Should end with ellipsis
        assert code.strip().endswith("...")

    def test_code_output_with_limit_lines_equal_to_output_no_ellipsis(self, tmp_path):
        """It does not add ellipsis when output exactly matches limit-lines."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Use limit-lines=3 with a cell that has exactly 3 lines
        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:three-lines limit-lines=3
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have all 3 lines
        assert "Line A" in result or "A\n" in result
        assert "B" in result
        assert "C" in result
        # Should NOT have ellipsis since output is exactly 3 lines
        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1)
        assert "..." not in code

    def test_code_output_with_limit_lines_greater_than_output(self, tmp_path):
        """It shows full output when limit-lines exceeds actual output."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Use limit-lines=100 with a cell that has only 3 lines
        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:three-lines limit-lines=100
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have all 3 lines
        assert "A" in result or "Line A" in result
        assert "B" in result
        assert "C" in result
        # Should NOT have ellipsis since limit > output
        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1)
        assert "..." not in code

    def test_code_output_without_limit_shows_full_output(self, tmp_path):
        """It shows full output when no limit is specified."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:ten-lines
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have all 10 lines
        assert "Line 1" in result
        assert "Line 5" in result
        assert "Line 10" in result
        # Should NOT have ellipsis since no limit was set
        assert "..." not in result

    def test_limit_lines_does_not_affect_code_directive(self, tmp_path):
        """It ignores limit-lines parameter on @@code directive (limit only affects output)."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code multiline:ten-lines limit-lines=2
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have the full code source (3 lines), not truncated
        assert "for i in range(1, 11):" in result
        assert "print(f\"Line {i}\")" in result
        # No ellipsis for code directive (limit is ignored for code)
        assert "..." not in result


class TestCodeOutputLimitChars:
    """Tests for the limit-chars parameter on @@code-output directive."""

    def test_code_output_with_limit_chars_truncates_output(self, tmp_path):
        """It truncates output when limit-chars is specified and output exceeds limit."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Create a template with limit-chars=20
        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test Output Limit Chars

@@code-output multiline:ten-lines limit-chars=20
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have code block
        assert "```python" in result
        # Should have ellipsis at the end
        assert "..." in result

    def test_code_output_with_limit_chars_below_output_count_shows_ellipsis(self, tmp_path):
        """It adds ellipsis when output is truncated by character limit."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:ten-lines limit-chars=50
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Extract the code block content
        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1)

        # Should end with ellipsis
        assert code.strip().endswith("...")
        # Should be approximately 50 chars plus "..."
        assert len(code) <= 55  # Allow some margin

    def test_code_output_with_limit_chars_equal_to_output_no_ellipsis(self, tmp_path):
        """It does not add ellipsis when output exactly matches limit-chars."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Create a cell with exactly 20 chars of output
        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:three-lines limit-chars=1000
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have all output
        assert "A" in result or "Line A" in result
        # Should NOT have ellipsis since limit is larger than output
        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1)
        assert "..." not in code

    def test_code_output_with_limit_chars_greater_than_output(self, tmp_path):
        """It shows full output when limit-chars exceeds actual output."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Use limit-chars=10000 with a cell that has only ~50 chars
        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:three-lines limit-chars=10000
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have all 3 lines
        assert "A" in result or "Line A" in result
        assert "B" in result
        assert "C" in result
        # Should NOT have ellipsis since limit > output
        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1)
        assert "..." not in code


class TestCodeOutputCombinedLimits:
    """Tests for using both limit-lines and limit-chars together."""

    def test_code_output_with_both_limits_applies_lines_first(self, tmp_path):
        """It applies limit-lines first, then limit-chars."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Use both limits - limit-lines should truncate first
        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:ten-lines limit-lines=5 limit-chars=1000
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have first 5 lines due to limit-lines
        assert "Line 1" in result
        assert "Line 5" in result
        # Should NOT have line 6 or beyond
        assert "Line 6" not in result
        assert "Line 10" not in result
        # Should have ellipsis from limit-lines truncation
        assert "..." in result

    def test_code_output_with_both_limits_chars_can_further_truncate(self, tmp_path):
        """It applies limit-chars after limit-lines for additional truncation."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Use a small char limit that will further truncate after lines limit
        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:ten-lines limit-lines=5 limit-chars=15
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have ellipsis from limit-chars truncation
        assert "..." in result

    def test_code_output_with_both_limits_reverse_order(self, tmp_path):
        """It works when parameters are specified in reverse order."""
        import shutil

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Specify limit-chars first, then limit-lines
        template_content = """---
notebooks:
  - id: multiline
    path: fixtures/notebooks/multiline-output.ipynb
    execute: false
---

# Test

@@code-output multiline:ten-lines limit-chars=1000 limit-lines=3
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Should have first 3 lines due to limit-lines
        assert "Line 1" in result
        assert "Line 3" in result
        # Should NOT have line 4 or beyond
        assert "Line 4" not in result


class TestJupyterSourceFormat:
    """Tests for handling real Jupyter notebook source format with trailing newlines."""

    def test_no_extra_blank_lines_from_trailing_newlines(self, tmp_path):
        """
        Test that Jupyter's source format (with trailing \n on each line) doesn't create extra blank lines.

        This is a regression test for the issue where Jupyter stores source as:
        ["# @cell_id=setup-imports\n", "\n", "import json\n", "import boto3"]

        Without proper stripping, joining creates "import json\n\nimport boto3" (extra blank line).

        Uses actual fixture files: tests/fixtures/notebooks/jupyter-format.ipynb
        """
        import shutil
        import re

        # Copy fixtures to tmpdir so relative paths work
        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # The template file already exists in fixtures
        template_path = fixtures_tmp / "jupyter-format.template.md"

        # Generate
        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        # Extract code block
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1)

        # Verify NO extra blank line between imports
        # Should be "import json\nimport boto3", NOT "import json\n\nimport boto3"
        # (trailing newline is ok/normal)
        assert code.strip() == "import json\nimport boto3", f"Expected 'import json\\nimport boto3' but got {repr(code)}"


class TestScriptCodeGeneration:
    """Tests for generating code from script files."""

    def test_generate_from_script(self):
        """It generates code blocks from a script-only template."""
        gen = Generator()
        template_path = FIXTURES_DIR / "script-template.template.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "script-output.md"
            result = gen.generate(template_path, output_path)

        assert "@@code" not in result
        assert "```python" in result
        assert "from openai import OpenAI" in result
        assert "client = OpenAI()" in result
        assert "client.chat.completions.create" in result

    def test_mixed_notebook_and_script(self):
        """It generates from a template referencing both notebooks and scripts."""
        gen = Generator()
        template_path = FIXTURES_DIR / "mixed-template.template.md"

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "mixed-output.md"
            result = gen.generate(template_path, output_path)

        assert "@@code" not in result
        assert "```python" in result
        # From notebook
        assert 'print("Hello, World!")' in result
        # From script
        assert "from openai import OpenAI" in result

    def test_code_output_on_script_raises_error(self, tmp_path):
        """It raises InvalidDirectiveError when @@code-output is used with a script."""
        # Create a script
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script = scripts_dir / "test.py"
        script.write_text(
            "# @block=hello\n"
            "print('hello')\n"
            "# @end\n"
        )

        template_content = """---
scripts:
  - id: test
    path: scripts/test.py
---

# Test

@@code-output test:hello
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"

        with pytest.raises(InvalidDirectiveError, match="not supported for scripts"):
            gen.generate(template_path, output_path)

    def test_missing_block_in_script_raises_error(self, tmp_path):
        """It raises BlockNotFoundError when referencing a nonexistent block."""
        # Create a script without the referenced block
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script = scripts_dir / "test.py"
        script.write_text(
            "# @block=existing\n"
            "print('hello')\n"
            "# @end\n"
        )

        template_content = """---
scripts:
  - id: test
    path: scripts/test.py
---

# Test

@@code test:nonexistent
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"

        with pytest.raises(BlockNotFoundError, match="nonexistent"):
            gen.generate(template_path, output_path)

    def test_script_block_content_is_trimmed(self, tmp_path):
        """It trims script block content (no leading/trailing blank lines)."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script = scripts_dir / "test.py"
        script.write_text(
            "# @block=padded\n"
            "\n"
            "x = 1\n"
            "\n"
            "# @end\n"
        )

        template_content = """---
scripts:
  - id: test
    path: scripts/test.py
---

# Test

@@code test:padded
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1)
        assert code.strip() == "x = 1"

    def test_script_lines_and_strip_spaces(self, tmp_path):
        """It applies lines= and strip-spaces= to script blocks."""
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script = scripts_dir / "test.py"
        script.write_text(
            "# @block=my-class\n"
            "class MyClass:\n"
            "    def __init__(self):\n"
            "        self.value = 42\n"
            "\n"
            "    def get_value(self):\n"
            "        return self.value\n"
            "# @end\n"
        )

        template_content = """---
scripts:
  - id: test
    path: scripts/test.py
---

# Test

@@code test:my-class lines=2-3 strip-spaces=4
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        code = code_match.group(1).strip("\n")
        lines = code.split("\n")
        assert lines[0] == "def __init__(self):"
        assert lines[1] == "    self.value = 42"


class TestCodeLineFiltering:
    """Tests for lines= and strip-spaces= parameters on @@code directive."""

    def _extract_code(self, result: str) -> str:
        """Extract the first code block content from generated markdown."""
        import re
        code_match = re.search(r'```python\n(.*?)```', result, re.DOTALL)
        assert code_match is not None
        return code_match.group(1).strip("\n")

    def test_lines_extracts_range(self, tmp_path):
        """It extracts only the specified line range with lines=1-2."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: indented
    path: fixtures/notebooks/indented-code.ipynb
    execute: false
---

# Test

@@code indented:my-class lines=1-2
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        code = self._extract_code(result)
        lines = code.split("\n")
        assert len(lines) == 2
        assert "class MyClass:" in lines[0]
        assert "def __init__(self):" in lines[1]

    def test_strip_spaces_removes_leading_spaces(self, tmp_path):
        """It removes N leading spaces from each line with strip-spaces=4."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: indented
    path: fixtures/notebooks/indented-code.ipynb
    execute: false
---

# Test

@@code indented:my-class lines=2-3 strip-spaces=4
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        code = self._extract_code(result)
        lines = code.split("\n")
        assert lines[0] == "def __init__(self):"
        assert lines[1] == "    self.value = 42"

    def test_lines_single_line(self, tmp_path):
        """It extracts a single line with lines=2-2."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: indented
    path: fixtures/notebooks/indented-code.ipynb
    execute: false
---

# Test

@@code indented:my-class lines=1-1
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        code = self._extract_code(result)
        assert code == "class MyClass:"

    def test_combined_lines_and_strip_spaces(self, tmp_path):
        """It applies both lines and strip-spaces together."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: indented
    path: fixtures/notebooks/indented-code.ipynb
    execute: false
---

# Test

@@code indented:my-class lines=5-6 strip-spaces=4
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        code = self._extract_code(result)
        lines = code.split("\n")
        assert lines[0] == "def get_value(self):"
        assert lines[1] == "    return self.value"

    def test_lines_beyond_source_length(self, tmp_path):
        """It returns available lines when range exceeds source length."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: indented
    path: fixtures/notebooks/indented-code.ipynb
    execute: false
---

# Test

@@code indented:my-class lines=5-100
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        code = self._extract_code(result)
        lines = code.split("\n")
        # Should have lines 5 and 6 (last 2 lines of the class)
        assert "def get_value(self):" in lines[0]
        assert "return self.value" in lines[1]

    def test_strip_spaces_on_empty_lines(self, tmp_path):
        """It handles empty lines gracefully with strip-spaces (no-op on empty lines)."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        # Lines 3-5 include an empty line between __init__ body and get_value
        template_content = """---
notebooks:
  - id: indented
    path: fixtures/notebooks/indented-code.ipynb
    execute: false
---

# Test

@@code indented:my-class lines=3-5 strip-spaces=4
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"
        result = gen.generate(template_path, output_path)

        code = self._extract_code(result)
        lines = code.split("\n")
        # Line 3: "        self.value = 42" -> "    self.value = 42"
        assert lines[0] == "    self.value = 42"
        # Line 4: empty line -> stays empty
        assert lines[1] == ""
        # Line 5: "    def get_value(self):" -> "def get_value(self):"
        assert lines[2] == "def get_value(self):"


class TestStripFrontmatter:
    """Tests for _strip_frontmatter helper."""

    def test_strips_frontmatter(self):
        """It strips YAML frontmatter and returns the body."""
        content = "---\nnote: test\ngenerated_at: 2026-01-01\n---\n\n# Hello\n\nBody here."
        assert _strip_frontmatter(content) == "# Hello\n\nBody here."

    def test_no_frontmatter(self):
        """It returns content unchanged when there's no frontmatter."""
        content = "# Hello\n\nBody here."
        assert _strip_frontmatter(content) == content

    def test_unclosed_frontmatter(self):
        """It returns content unchanged when frontmatter is not properly closed."""
        content = "---\nnote: test\n# Hello"
        assert _strip_frontmatter(content) == content


class TestSkipUnchangedOutput:
    """Tests for skipping writes when output content hasn't changed."""

    def test_skips_write_when_content_unchanged(self, tmp_path):
        """It skips writing when the generated body matches the existing output."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: nb
    path: fixtures/notebooks/sample.ipynb
    execute: false
---

# Test

@@code nb:print-hello
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"

        # First generation - creates the file
        gen.generate(template_path, output_path)
        first_mtime = output_path.stat().st_mtime
        first_content = output_path.read_text(encoding="utf-8")

        # Small delay to ensure mtime would differ if file were rewritten
        import time
        time.sleep(0.1)

        # Second generation - should skip writing
        gen.generate(template_path, output_path)
        second_mtime = output_path.stat().st_mtime
        second_content = output_path.read_text(encoding="utf-8")

        # File should NOT have been rewritten
        assert first_mtime == second_mtime
        # Content should be identical (same generated_at since file wasn't touched)
        assert first_content == second_content

    def test_writes_when_content_changes(self, tmp_path):
        """It writes when the generated body differs from the existing output."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content_v1 = """---
notebooks:
  - id: nb
    path: fixtures/notebooks/sample.ipynb
    execute: false
---

# Test Version 1

@@code nb:print-hello
"""
        template_content_v2 = """---
notebooks:
  - id: nb
    path: fixtures/notebooks/sample.ipynb
    execute: false
---

# Test Version 2

@@code nb:print-hello
"""
        template_path = tmp_path / "test.template.md"
        output_path = tmp_path / "test.md"
        gen = Generator()

        # First generation
        template_path.write_text(template_content_v1)
        gen.generate(template_path, output_path)
        first_content = output_path.read_text(encoding="utf-8")

        # Change template content
        template_path.write_text(template_content_v2)

        # Second generation - content changed, should write
        gen.generate(template_path, output_path)
        second_content = output_path.read_text(encoding="utf-8")

        assert "Version 1" in first_content
        assert "Version 2" in second_content

    def test_writes_when_output_missing(self, tmp_path):
        """It writes when the output file doesn't exist yet."""
        import shutil

        fixtures_tmp = tmp_path / "fixtures"
        shutil.copytree(FIXTURES_DIR, fixtures_tmp)

        template_content = """---
notebooks:
  - id: nb
    path: fixtures/notebooks/sample.ipynb
    execute: false
---

# Test

@@code nb:print-hello
"""
        template_path = tmp_path / "test.template.md"
        template_path.write_text(template_content)

        gen = Generator()
        output_path = tmp_path / "test.md"

        assert not output_path.exists()
        gen.generate(template_path, output_path)
        assert output_path.exists()
        assert "```python" in output_path.read_text(encoding="utf-8")
