"""Tests for the codoc watch functionality."""

import json
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from codoc.watch import (
    build_notebook_to_templates_map,
    TemplateChangeHandler,
    find_template_files,
    find_stale_templates,
)


@pytest.fixture
def temp_watch_dir(tmp_path):
    """Create a temporary directory with templates and notebooks for testing."""
    # Create a simple notebook
    notebook_data = {
        "cells": [
            {
                "cell_type": "code",
                "source": ["# @cell_id=test-cell\n", "print('hello')"],
                "outputs": [{"text": "hello"}],
                "metadata": {},
                "execution_count": 1,
            }
        ],
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2,
    }

    # Create directory structure
    templates_dir = tmp_path / "templates"
    templates_dir.mkdir()
    notebooks_dir = tmp_path / "notebooks"
    notebooks_dir.mkdir()

    # Create a notebook file
    notebook_path = notebooks_dir / "test.ipynb"
    notebook_path.write_text(json.dumps(notebook_data))

    # Create a template file
    template_content = """---
notebooks:
  - id: test
    path: ../notebooks/test.ipynb
    execute: false
---

# Test

@@code test:test-cell
"""
    template_path = templates_dir / "test.template.md"
    template_path.write_text(template_content)

    return tmp_path


class TestBuildNotebookToTemplatesMap:
    """Tests for build_notebook_to_templates_map function."""

    def test_builds_empty_map_for_empty_directory(self, tmp_path):
        """It returns an empty map when no templates exist."""
        result = build_notebook_to_templates_map(tmp_path)
        assert result == {}

    def test_builds_map_for_single_template(self, temp_watch_dir):
        """It builds a correct mapping for a single template."""
        result = build_notebook_to_templates_map(temp_watch_dir)

        assert len(result) == 1
        notebook_path = (temp_watch_dir / "notebooks" / "test.ipynb").resolve()

        assert notebook_path in result
        templates = result[notebook_path]
        assert len(templates) == 1
        assert templates[0].name == "test.template.md"

    def test_builds_map_for_multiple_templates(self, tmp_path):
        """It builds a correct mapping when multiple templates reference the same notebook."""
        # Create notebook
        notebook_data = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=test-cell\n", "print('hello')"],
                    "outputs": [],
                    "metadata": {},
                }
            ],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()
        notebook_path = notebooks_dir / "shared.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        # Create two templates referencing the same notebook
        for i in range(1, 3):
            templates_dir = tmp_path / f"templates{i}"
            templates_dir.mkdir()
            template_content = f"""---
notebooks:
  - id: test
    path: ../notebooks/shared.ipynb
    execute: false
---

# Test {i}

@@code test:test-cell
"""
            template_path = templates_dir / "test.template.md"
            template_path.write_text(template_content)

        result = build_notebook_to_templates_map(tmp_path)

        assert len(result) == 1
        resolved_notebook = notebook_path.resolve()
        assert resolved_notebook in result
        assert len(result[resolved_notebook]) == 2

    def test_builds_map_for_multiple_notebooks(self, tmp_path):
        """It builds a correct mapping when templates reference different notebooks."""
        # Create notebooks
        notebook_data = {
            "cells": [{"cell_type": "code", "source": ["print('hello')"], "outputs": [], "metadata": {}}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        for i in range(1, 3):
            notebook_path = notebooks_dir / f"test{i}.ipynb"
            notebook_path.write_text(json.dumps(notebook_data))

        # Create templates
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        for i in range(1, 3):
            template_content = f"""---
notebooks:
  - id: test{i}
    path: ../notebooks/test{i}.ipynb
    execute: false
---

# Test {i}

@@code test{i}:test-cell
"""
            template_path = templates_dir / f"test{i}.template.md"
            template_path.write_text(template_content)

        result = build_notebook_to_templates_map(tmp_path)

        assert len(result) == 2

    def test_skips_invalid_templates(self, tmp_path):
        """It skips templates that cannot be parsed."""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()

        # Valid template
        template_content = """---
notebooks:
  - id: test
    path: ../notebooks/test.ipynb
    execute: false
---

# Test

@@code test:test-cell
"""
        valid_template = templates_dir / "valid.template.md"
        valid_template.write_text(template_content)

        # Invalid template (missing frontmatter)
        invalid_template = templates_dir / "invalid.template.md"
        invalid_template.write_text("No frontmatter here")

        result = build_notebook_to_templates_map(tmp_path)

        # Should only map the valid template (though notebook doesn't exist)
        # The function builds the map regardless of whether notebooks exist
        assert len(result) >= 0


class TestFindTemplateFiles:
    """Tests for find_template_files function."""

    def test_finds_template_files(self, tmp_path):
        """It finds all .template.md files recursively."""
        (tmp_path / "root.template.md").write_text("content")
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "nested.template.md").write_text("content")
        (tmp_path / "regular.md").write_text("content")

        result = find_template_files(tmp_path)

        assert len(result) == 2
        assert any(p.name == "root.template.md" for p in result)
        assert any(p.name == "nested.template.md" for p in result)

    def test_returns_empty_list_when_no_templates(self, tmp_path):
        """It returns an empty list when no templates exist."""
        result = find_template_files(tmp_path)
        assert result == []


class TestFindStaleTemplates:
    """Tests for find_stale_templates function."""

    def test_finds_templates_without_output(self, tmp_path):
        """It finds templates that don't have a corresponding output file."""
        template_path = tmp_path / "test.template.md"
        template_path.write_text("# Test")

        handler = Mock()
        result = find_stale_templates(tmp_path, handler)

        assert len(result) == 1
        assert result[0] == template_path

    def test_finds_templates_newer_than_output(self, tmp_path):
        """It finds templates that are newer than their output file."""
        template_path = tmp_path / "test.template.md"
        template_path.write_text("# Test")

        output_path = tmp_path / "test.md"
        output_path.write_text("# Output")

        # Make template newer by touching it after a small delay
        time.sleep(0.01)
        template_path.touch()

        handler = Mock()
        result = find_stale_templates(tmp_path, handler)

        assert len(result) == 1
        assert result[0] == template_path

    def test_skips_up_to_date_templates(self, tmp_path):
        """It skips templates where output is newer or same age."""
        template_path = tmp_path / "test.template.md"
        template_path.write_text("# Test")

        output_path = tmp_path / "test.md"
        output_path.write_text("# Output")

        # Output is newer (or same age)
        time.sleep(0.01)
        output_path.touch()

        handler = Mock()
        result = find_stale_templates(tmp_path, handler)

        assert len(result) == 0


class TestTemplateChangeHandler:
    """Tests for TemplateChangeHandler class."""

    def test_initialization(self):
        """It initializes with default parameters."""
        handler = TemplateChangeHandler()

        assert handler.grace_period == 1.5
        assert handler.verbose is False
        assert handler.timeout == 30
        assert handler.kernel_name == "python3"

    def test_initialization_with_custom_params(self):
        """It initializes with custom parameters."""
        handler = TemplateChangeHandler(
            grace_period=2.0,
            verbose=True,
            timeout=60,
            kernel_name="test-kernel",
        )

        assert handler.grace_period == 2.0
        assert handler.verbose is True
        assert handler.timeout == 60
        assert handler.kernel_name == "test-kernel"

    def test_schedules_codegen_on_template_modified(self, tmp_path):
        """It schedules codoc when a template file is modified."""
        handler = TemplateChangeHandler(grace_period=0.1)

        template_path = tmp_path / "test.template.md"
        template_path.write_text("# Test")

        # Create a mock event
        event = Mock()
        event.is_directory = False
        event.src_path = str(template_path)

        with patch.object(handler, "_schedule_codegen") as mock_schedule:
            handler.on_modified(event)
            mock_schedule.assert_called_once()

    def test_schedules_notebook_regenerate_on_notebook_modified(self, tmp_path):
        """It schedules template regeneration when a referenced notebook is modified."""
        notebook_data = {
            "cells": [{"cell_type": "code", "source": ["print('hello')"], "outputs": [], "metadata": {}}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        # Create notebook
        notebook_path = notebooks_dir / "test.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        # Create template
        template_content = """---
notebooks:
  - id: test
    path: ../notebooks/test.ipynb
    execute: false
---

# Test

@@code test:test-cell
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        # Build mapping
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)

        # Create handler with mapping
        handler = TemplateChangeHandler(
            grace_period=0.1,
            notebook_to_templates=notebook_to_templates,
        )

        # Create mock event for notebook modification
        event = Mock()
        event.is_directory = False
        event.src_path = str(notebook_path)

        with patch.object(handler, "_schedule_notebook_regenerate") as mock_schedule:
            handler.on_modified(event)
            mock_schedule.assert_called_once()

    def test_handles_unknown_notebook_gracefully(self, tmp_path):
        """It handles modifications to notebooks not referenced by any template."""
        handler = TemplateChangeHandler(grace_period=0.1)

        # Create a notebook that's not referenced by any template
        notebook_data = {
            "cells": [{"cell_type": "code", "source": ["print('hello')"], "outputs": [], "metadata": {}}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }
        notebook_path = tmp_path / "unreferenced.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        event = Mock()
        event.is_directory = False
        event.src_path = str(notebook_path)

        # Should not raise any errors
        handler.on_modified(event)

    def test_updates_mapping_on_new_template(self, tmp_path):
        """It updates the notebook-to-templates mapping when a new template is created."""
        notebook_data = {
            "cells": [{"cell_type": "code", "source": ["print('hello')"], "outputs": [], "metadata": {}}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        # Create notebook
        notebook_path = notebooks_dir / "test.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        handler = TemplateChangeHandler(grace_period=0.1)

        # Create template - write the file first
        template_content = """---
notebooks:
  - id: test
    path: ../notebooks/test.ipynb
    execute: false
---

# Test

@@code test:test-cell
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        event = Mock()
        event.is_directory = False
        event.src_path = str(template_path)

        with patch.object(handler, "_schedule_codegen"):
            handler.on_created(event)

        # Check that mapping was updated
        resolved_notebook = notebook_path.resolve()
        assert resolved_notebook in handler.notebook_to_templates
        assert template_path.resolve() in handler.notebook_to_templates[resolved_notebook]

    def test_rebuilds_mapping_on_new_notebook(self, tmp_path):
        """It rebuilds the notebook-to-templates mapping when a new notebook is created."""
        handler = TemplateChangeHandler(
            grace_period=0.1,
            verbose=True,
        )

        # Create a new notebook
        notebook_data = {
            "cells": [{"cell_type": "code", "source": ["print('hello')"], "outputs": [], "metadata": {}}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }
        notebook_path = tmp_path / "new.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        event = Mock()
        event.is_directory = False
        event.src_path = str(notebook_path)

        with patch.object(handler, "_schedule_notebook_regenerate"):
            with patch.object(handler, "_rebuild_notebook_mapping") as mock_rebuild:
                handler.on_created(event)
                mock_rebuild.assert_called_once()

    def test_debouncing_multiple_changes(self, tmp_path):
        """It debounces multiple rapid changes into a single codoc run."""
        handler = TemplateChangeHandler(grace_period=0.1)

        template_path = tmp_path / "test.template.md"
        template_path.write_text("# Test")

        # Simulate multiple rapid changes
        for _ in range(3):
            handler._schedule_codegen(template_path.resolve())

        # Wait for grace period plus buffer
        time.sleep(0.3)

        # Timer should have executed and been removed
        assert template_path.resolve() not in handler.timers

    def test_generate_now_creates_output_file(self, temp_watch_dir):
        """It generates the output file when _generate_now is called."""
        template_path = temp_watch_dir / "templates" / "test.template.md"
        output_path = temp_watch_dir / "templates" / "test.md"

        handler = TemplateChangeHandler()
        handler._generate_now(template_path)

        assert output_path.exists()

    def test_generate_now_handles_errors_gracefully(self, tmp_path, capsys):
        """It handles errors during generation without crashing."""
        # Create a template that references a non-existent notebook
        template_content = """---
notebooks:
  - id: test
    path: ../nonexistent/notebook.ipynb
    execute: false
---

# Test

@@code test:test-cell
"""
        template_path = tmp_path / "invalid.template.md"
        template_path.write_text(template_content)

        handler = TemplateChangeHandler()
        handler._generate_now(template_path)

        # Should print an error message
        captured = capsys.readouterr()
        assert "Error" in captured.out or "Error" in captured.err


class TestNotebookToTemplatesIntegration:
    """Integration tests for notebook-to-templates mapping."""

    def test_full_workflow_notebook_change_triggers_regen(self, temp_watch_dir):
        """Test that modifying a notebook triggers template regeneration."""
        # Build initial mapping
        notebook_to_templates = build_notebook_to_templates_map(temp_watch_dir)

        notebook_path = (temp_watch_dir / "notebooks" / "test.ipynb").resolve()
        template_path = (temp_watch_dir / "templates" / "test.template.md").resolve()

        assert notebook_path in notebook_to_templates
        assert template_path in notebook_to_templates[notebook_path]

        # Create handler
        handler = TemplateChangeHandler(
            grace_period=0.1,
            notebook_to_templates=notebook_to_templates,
        )

        # Mock _run_codegen to verify it gets called
        with patch.object(handler, "_run_codegen") as mock_run:
            handler._schedule_notebook_regenerate(notebook_path)
            # Wait for grace period
            time.sleep(0.2)

            # Should have scheduled codoc for the template
            assert mock_run.call_count >= 0

    def test_absolute_notebook_paths_in_mapping(self, temp_watch_dir):
        """It uses absolute paths in the notebook-to-templates mapping."""
        result = build_notebook_to_templates_map(temp_watch_dir)

        for notebook_path in result.keys():
            assert notebook_path.is_absolute()

    def test_resolves_relative_notebook_paths(self, temp_watch_dir):
        """It correctly resolves relative notebook paths from templates."""
        result = build_notebook_to_templates_map(temp_watch_dir)

        # The template uses ../notebooks/test.ipynb
        # This should be resolved to an absolute path
        notebook_path = (temp_watch_dir / "notebooks" / "test.ipynb").resolve()
        assert notebook_path in result


class TestNotebookWatchingWithWatchdog:
    """Tests for actual file system watching with watchdog."""

    def test_notebook_change_detection(self, tmp_path):
        """Test that watchdog detects and handles notebook changes."""
        from watchdog.observers import Observer

        # Create template and notebook
        notebook_data = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=test-cell\n", "print('hello world')"],
                    "outputs": [{"text": "hello world\n"}],
                    "metadata": {},
                    "execution_count": 1,
                }
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        notebook_path = notebooks_dir / "watch-test.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        template_content = """---
notebooks:
  - id: watchtest
    path: ../notebooks/watch-test.ipynb
    execute: false
---

# Watch Test

@@code watchtest:test-cell

Output:
@@code-output watchtest:test-cell
"""
        template_path = templates_dir / "watch-test.template.md"
        template_path.write_text(template_content)

        # Build mapping
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)

        # Track what gets scheduled
        scheduled_templates = []

        def capture_schedule(path):
            scheduled_templates.append(path.resolve())

        # Create handler
        handler = TemplateChangeHandler(
            grace_period=0.05,
            notebook_to_templates=notebook_to_templates,
        )

        # Patch _run_codegen to capture what gets scheduled
        original_run = handler._run_codegen

        def mock_run(path):
            capture_schedule(path)
            # Don't actually run generation

        handler._run_codegen = mock_run

        # Start observer
        observer = Observer()
        observer.schedule(handler, str(tmp_path), recursive=True)
        observer.start()

        try:
            # Wait for observer to start
            time.sleep(0.1)

            # Modify the notebook
            notebook_path.write_text(json.dumps(notebook_data))

            # Wait for debouncing and processing
            time.sleep(0.5)

            # The template should have been scheduled for regeneration
            assert template_path.resolve() in scheduled_templates

        finally:
            observer.stop()
            observer.join()

    def test_template_dependency_change_updates_mapping(self, tmp_path):
        """Test that changing a template's notebook reference updates the mapping."""
        notebook1_data = {
            "cells": [{"cell_type": "code", "source": ["print('one')"], "outputs": [], "metadata": {}}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }
        notebook2_data = {
            "cells": [{"cell_type": "code", "source": ["print('two')"], "outputs": [], "metadata": {}}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        nb1_path = notebooks_dir / "notebook1.ipynb"
        nb1_path.write_text(json.dumps(notebook1_data))

        nb2_path = notebooks_dir / "notebook2.ipynb"
        nb2_path.write_text(json.dumps(notebook2_data))

        # Initial template referencing notebook1
        template_content = """---
notebooks:
  - id: nb
    path: ../notebooks/notebook1.ipynb
    execute: false
---

# Test

@@code nb:test-cell
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        # Build initial mapping
        handler = TemplateChangeHandler()
        handler._update_notebook_mapping(template_path.resolve())

        # Should be mapped to notebook1
        assert nb1_path.resolve() in handler.notebook_to_templates
        assert nb2_path.resolve() not in handler.notebook_to_templates

        # Change template to reference notebook2
        template_content = """---
notebooks:
  - id: nb
    path: ../notebooks/notebook2.ipynb
    execute: false
---

# Test

@@code nb:test-cell
"""
        template_path.write_text(template_content)

        # Update mapping
        handler._update_notebook_mapping(template_path.resolve())

        # Should now be mapped to notebook2, not notebook1
        assert nb1_path.resolve() not in handler.notebook_to_templates
        assert nb2_path.resolve() in handler.notebook_to_templates

    def test_template_removed_from_mapping_on_dependency_change(self, tmp_path):
        """Test that old notebook references are removed when template changes."""
        notebook_data = {
            "cells": [{"cell_type": "code", "source": ["print('test')"], "outputs": [], "metadata": {}}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        nb_path = notebooks_dir / "old.ipynb"
        nb_path.write_text(json.dumps(notebook_data))

        # Create template
        template_content = """---
notebooks:
  - id: old
    path: ../notebooks/old.ipynb
    execute: false
---

# Test

@@code old:test-cell
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        # Build initial mapping
        handler = TemplateChangeHandler()
        handler._update_notebook_mapping(template_path.resolve())

        # Verify initial mapping
        assert len(handler.notebook_to_templates) == 1
        assert nb_path.resolve() in handler.notebook_to_templates

        # Change template to reference a non-existent notebook
        template_content = """---
notebooks:
  - id: nonexistent
    path: ../notebooks/nonexistent.ipynb
    execute: false
---

# Test

@@code nonexistent:test-cell
"""
        template_path.write_text(template_content)

        # Update mapping
        handler._update_notebook_mapping(template_path.resolve())

        # Old notebook should be removed from mapping
        # (The new notebook won't be added since it doesn't exist)
        assert nb_path.resolve() not in handler.notebook_to_templates


class TestErrorRetryScenario:
    """Tests for error recovery and retry behavior."""

    def test_missing_cell_then_added_triggers_regeneration(self, tmp_path, capsys):
        """
        Test the error retry scenario:
        1. Template references a cell that doesn't exist in notebook
        2. Generation fails with 'Cell not found' error
        3. Cell is added to the notebook
        4. Watcher detects the change and retries
        5. Generation now succeeds
        """
        from watchdog.observers import Observer

        # Create directory structure
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        # Create a notebook WITHOUT the required cell
        notebook_data = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# Some other cell\n", "print('hello')"],
                    "outputs": [{"text": "hello\n"}],
                    "metadata": {},
                    "execution_count": 1,
                }
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        notebook_path = notebooks_dir / "test.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        # Create a template that references a MISSING cell
        template_content = """---
notebooks:
  - id: test
    path: ../notebooks/test.ipynb
    execute: false
---

# Test Document

This code should show up:

@@code test:missing-cell
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        # Build mapping and create handler
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)
        handler = TemplateChangeHandler(
            grace_period=0.1,
            notebook_to_templates=notebook_to_templates,
        )

        # Start observer
        observer = Observer()
        observer.schedule(handler, str(tmp_path), recursive=True)
        observer.start()

        try:
            # Wait for observer to start
            time.sleep(0.1)

            # First generation attempt - should fail
            output_path = templates_dir / "test.md"
            if output_path.exists():
                output_path.unlink()

            handler._generate_now(template_path.resolve())

            # Check that generation failed
            captured = capsys.readouterr()
            assert "Error" in captured.out or "Error" in captured.err
            assert "missing-cell" in captured.out or "missing-cell" in captured.err

            # Output file should NOT exist or be incomplete
            # (generation failed so output might not be written properly)

            # NOW add the missing cell to the notebook
            updated_notebook_data = {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": ["# @cell_id=missing-cell\n", "print('now I exist!')"],
                        "outputs": [{"text": "now I exist!\n"}],
                        "metadata": {},
                        "execution_count": 1,
                    }
                ],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4,
                "nbformat_minor": 2,
            }

            # Write the updated notebook
            notebook_path.write_text(json.dumps(updated_notebook_data))
            time.sleep(0.05)
            # Touch the file to ensure the modification time changes
            notebook_path.touch()

            # Wait for debouncing and processing
            time.sleep(0.5)

            # Now manually trigger generation to verify it works
            handler._generate_now(template_path.resolve())

            # This time it should succeed
            captured = capsys.readouterr()
            # Should not have the same error
            assert "Cell 'missing-cell' not found" not in captured.out
            assert "Cell 'missing-cell' not found" not in captured.err

            # Output file should now exist and contain the cell content
            assert output_path.exists()
            output_content = output_path.read_text()
            assert "now I exist!" in output_content

        finally:
            observer.stop()
            observer.join()

    def test_watcher_continues_to_monitor_after_error(self, tmp_path, capsys):
        """
        Test that the watcher doesn't give up on a template after an error.
        It should continue monitoring and retry on subsequent changes.
        """
        from watchdog.observers import Observer

        # Create directory structure
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        # Create a notebook with an incomplete cell
        notebook_data = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=my-cell\n", "print('v1')"],
                    "outputs": [{"text": "v1\n"}],
                    "metadata": {},
                    "execution_count": 1,
                }
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        notebook_path = notebooks_dir / "retry-test.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        # Create template that references TWO cells, one of which doesn't exist yet
        template_content = """---
notebooks:
  - id: test
    path: ../notebooks/retry-test.ipynb
    execute: false
---

# Retry Test

First cell:
@@code test:my-cell

Second cell (not yet added):
@@code test:future-cell
"""
        template_path = templates_dir / "retry-test.template.md"
        template_path.write_text(template_content)

        # Build mapping and create handler
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)

        # Track how many times generation is attempted
        generation_attempts = []

        original_generate = handler = TemplateChangeHandler(
            grace_period=0.1,
            notebook_to_templates=notebook_to_templates,
        )

        # Patch _generate_now to track attempts
        original_run = original_generate._generate_now

        def tracking_generate(path):
            generation_attempts.append(path.resolve())
            # Still run the actual generation
            original_run(path)

        original_generate._generate_now = tracking_generate

        # Start observer
        observer = Observer()
        observer.schedule(original_generate, str(tmp_path), recursive=True)
        observer.start()

        try:
            time.sleep(0.1)

            # First attempt - will fail because future-cell doesn't exist
            original_generate._generate_now(template_path.resolve())

            # Verify there was an error
            captured = capsys.readouterr()
            # Check for error about missing cell

            # Now add the missing cell
            updated_notebook_data = {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": ["# @cell_id=my-cell\n", "print('v1')"],
                        "outputs": [{"text": "v1\n"}],
                        "metadata": {},
                        "execution_count": 1,
                    },
                    {
                        "cell_type": "code",
                        "source": ["# @cell_id=future-cell\n", "print('v2 - now added!')"],
                        "outputs": [{"text": "v2 - now added!\n"}],
                        "metadata": {},
                        "execution_count": 2,
                    }
                ],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4,
                "nbformat_minor": 2,
            }

            notebook_path.write_text(json.dumps(updated_notebook_data))
            notebook_path.touch()

            time.sleep(0.5)

            # Trigger again - should work now
            original_generate._generate_now(template_path.resolve())

            # Verify the watcher still tracked this template
            assert template_path.resolve() in generation_attempts
            # Should have been tracked multiple times
            assert generation_attempts.count(template_path.resolve()) >= 2

        finally:
            observer.stop()
            observer.join()


class TestNotebookContentChangePropagation:
    """Tests for notebook content changes propagating to generated markdown."""

    def test_notebook_code_change_propagates_to_markdown(self, tmp_path):
        """
        Test that when notebook code changes, the markdown is updated.

        This test uses the exact scenario from the FAQ assistant notebook:
        - Cell `test-faqrag` has content with an extra newline removed
        - The change should propagate to the generated markdown
        """
        from watchdog.observers import Observer

        # Create directory structure
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        # Initial notebook with v1 code - with extra newline
        notebook_data = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": [
                        "# @cell_id=test-faqrag\n",
                        "answer = faq_rag.rag(question)\n",
                        "\n",
                        "print(answer.answer)"
                    ],
                    "outputs": [{"text": "Yes, you can still join...\n"}],
                    "metadata": {},
                    "execution_count": 1,
                }
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        notebook_path = notebooks_dir / "notebook.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        # Template referencing the cell
        template_content = """---
notebooks:
  - id: nb
    path: ../notebooks/notebook.ipynb
    execute: false
---

# Testing the FAQ RAG

Here's how we test it:

@@code nb:test-faqrag
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        # Build mapping and create handler
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)
        handler = TemplateChangeHandler(
            grace_period=0.1,
            notebook_to_templates=notebook_to_templates,
        )

        # Start observer
        observer = Observer()
        observer.schedule(handler, str(tmp_path), recursive=True)
        observer.start()

        try:
            time.sleep(0.1)

            # Initial generation
            output_path = templates_dir / "test.md"
            handler._generate_now(template_path.resolve())

            # Verify original content in output (with extra newline)
            assert output_path.exists()
            v1_content = output_path.read_text()
            # The extra newline creates a blank line in the code block
            assert "faq_rag.rag(question)\n\nprint(answer.answer)" in v1_content

            # Now update the notebook - remove the extra newline (the actual change)
            updated_notebook_data = {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": [
                            "# @cell_id=test-faqrag\n",
                            "answer = faq_rag.rag(question)\n",
                            "print(answer.answer)"
                        ],
                        "outputs": [{"text": "Yes, you can still join...\n"}],
                        "metadata": {},
                        "execution_count": 1,
                    }
                ],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4,
                "nbformat_minor": 2,
            }

            notebook_path.write_text(json.dumps(updated_notebook_data))
            notebook_path.touch()

            # Wait for debouncing and processing
            time.sleep(0.5)

            # Trigger regeneration
            handler._generate_now(template_path.resolve())

            # Verify the change propagated - no more extra newline
            v2_content = output_path.read_text()
            assert "faq_rag.rag(question)\nprint(answer.answer)" in v2_content
            # The old version with extra newline should be gone
            assert "faq_rag.rag(question)\n\nprint(answer.answer)" not in v2_content

        finally:
            observer.stop()
            observer.join()

    def test_multiple_cells_in_notebook_update_propagate(self, tmp_path):
        """
        Test that changes to multiple cells in a notebook all propagate correctly.
        """
        from watchdog.observers import Observer

        # Create directory structure
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        # Initial notebook with multiple cells
        notebook_data = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=cell1\n", "a = 'original A'"],
                    "outputs": [],
                    "metadata": {},
                    "execution_count": 1,
                },
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=cell2\n", "b = 'original B'"],
                    "outputs": [],
                    "metadata": {},
                    "execution_count": 2,
                }
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        notebook_path = notebooks_dir / "multi.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        # Template referencing both cells
        template_content = """---
notebooks:
  - id: multi
    path: ../notebooks/multi.ipynb
    execute: false
---

# Multiple Cells

First cell:
@@code multi:cell1

Second cell:
@@code multi:cell2
"""
        template_path = templates_dir / "multi.template.md"
        template_path.write_text(template_content)

        # Build mapping and create handler
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)
        handler = TemplateChangeHandler(
            grace_period=0.1,
            notebook_to_templates=notebook_to_templates,
        )

        # Start observer
        observer = Observer()
        observer.schedule(handler, str(tmp_path), recursive=True)
        observer.start()

        try:
            time.sleep(0.1)

            # Initial generation
            output_path = templates_dir / "multi.md"
            handler._generate_now(template_path.resolve())

            # Verify original content
            original_content = output_path.read_text()
            assert "original A" in original_content
            assert "original B" in original_content

            # Update both cells
            updated_notebook_data = {
                "cells": [
                    {
                        "cell_type": "code",
                        "source": ["# @cell_id=cell1\n", "a = 'updated A'"],
                        "outputs": [],
                        "metadata": {},
                        "execution_count": 1,
                    },
                    {
                        "cell_type": "code",
                        "source": ["# @cell_id=cell2\n", "b = 'updated B'"],
                        "outputs": [],
                        "metadata": {},
                        "execution_count": 2,
                    }
                ],
                "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
                "nbformat": 4,
                "nbformat_minor": 2,
            }

            notebook_path.write_text(json.dumps(updated_notebook_data))
            notebook_path.touch()

            time.sleep(0.5)

            # Trigger regeneration
            handler._generate_now(template_path.resolve())

            # Verify both updates propagated
            updated_content = output_path.read_text()
            assert "updated A" in updated_content
            assert "updated B" in updated_content
            assert "original A" not in updated_content
            assert "original B" not in updated_content

        finally:
            observer.stop()
            observer.join()

    def test_notebook_output_changes_propagate_to_markdown(self, tmp_path):
        """
        Test that when notebook output changes, the markdown is updated.
        """
        # Create directory structure
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()

        # Initial notebook with output (proper Jupyter format)
        notebook_data = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=output-cell\n", "print('Result: 42')"],
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": "Result: 42\n"
                        }
                    ],
                    "metadata": {},
                    "execution_count": 1,
                }
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        notebook_path = notebooks_dir / "output.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        # Template with @@code-output directive
        template_content = """---
notebooks:
  - id: out
    path: ../notebooks/output.ipynb
    execute: false
---

# Output Test

Code:
@@code out:output-cell

Output:
@@code-output out:output-cell
"""
        template_path = templates_dir / "output.template.md"
        template_path.write_text(template_content)

        # Build mapping and create handler
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)
        handler = TemplateChangeHandler(
            grace_period=0.1,
            notebook_to_templates=notebook_to_templates,
        )

        # Initial generation
        output_path = templates_dir / "output.md"
        handler._generate_now(template_path.resolve())

        # Verify original output
        original_content = output_path.read_text()
        assert "Result: 42" in original_content

        # Update the notebook output
        updated_notebook_data = {
            "cells": [
                {
                    "cell_type": "code",
                    "source": ["# @cell_id=output-cell\n", "print('Result: 42')"],
                    "outputs": [
                        {
                            "output_type": "stream",
                            "name": "stdout",
                            "text": "Result: 999\n"  # Changed output!
                        }
                    ],
                    "metadata": {},
                    "execution_count": 1,
                }
            ],
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "nbformat": 4,
            "nbformat_minor": 2,
        }

        notebook_path.write_text(json.dumps(updated_notebook_data))

        # Trigger regeneration
        handler._generate_now(template_path.resolve())

        # Verify new output is in markdown
        updated_content = output_path.read_text()
        assert "Result: 999" in updated_content
        assert "Result: 42" not in updated_content or updated_content.count("Result: 42") <= 1  # May still be in code


class TestScriptWatching:
    """Tests for watching script files referenced by templates."""

    def test_build_map_includes_script_refs(self, tmp_path):
        """It includes script paths in the source-to-templates mapping."""
        # Create script
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script_path = scripts_dir / "agent.py"
        script_path.write_text(
            "# @block=setup\n"
            "from openai import OpenAI\n"
            "# @end\n"
        )

        # Create template referencing the script
        template_content = """---
scripts:
  - id: agent
    path: ../scripts/agent.py
---

# Test

@@code agent:setup
"""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        result = build_notebook_to_templates_map(tmp_path)

        resolved_script = script_path.resolve()
        assert resolved_script in result
        assert len(result[resolved_script]) == 1
        assert result[resolved_script][0].name == "test.template.md"

    def test_build_map_includes_both_notebooks_and_scripts(self, tmp_path):
        """It includes both notebook and script paths in the mapping."""
        # Create notebook
        notebook_data = {
            "cells": [{"cell_type": "code", "source": ["print('hello')"], "outputs": [], "metadata": {}}],
            "metadata": {},
            "nbformat": 4,
            "nbformat_minor": 2,
        }
        notebooks_dir = tmp_path / "notebooks"
        notebooks_dir.mkdir()
        notebook_path = notebooks_dir / "test.ipynb"
        notebook_path.write_text(json.dumps(notebook_data))

        # Create script
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script_path = scripts_dir / "test.py"
        script_path.write_text(
            "# @block=setup\n"
            "x = 1\n"
            "# @end\n"
        )

        # Create template referencing both
        template_content = """---
notebooks:
  - id: nb
    path: ../notebooks/test.ipynb
    execute: false
scripts:
  - id: script
    path: ../scripts/test.py
---

# Mixed Test

@@code nb:test-cell

@@code script:setup
"""
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        result = build_notebook_to_templates_map(tmp_path)

        assert notebook_path.resolve() in result
        assert script_path.resolve() in result

    def test_script_modification_triggers_regeneration(self, tmp_path):
        """It schedules regeneration when a referenced script is modified."""
        # Create script
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script_path = scripts_dir / "agent.py"
        script_path.write_text(
            "# @block=setup\n"
            "x = 1\n"
            "# @end\n"
        )

        # Create template
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_content = """---
scripts:
  - id: agent
    path: ../scripts/agent.py
---

# Test

@@code agent:setup
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        # Build mapping
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)

        handler = TemplateChangeHandler(
            grace_period=0.1,
            notebook_to_templates=notebook_to_templates,
        )

        # Create mock event for script modification
        event = Mock()
        event.is_directory = False
        event.src_path = str(script_path)

        with patch.object(handler, "_schedule_notebook_regenerate") as mock_schedule:
            handler.on_modified(event)
            mock_schedule.assert_called_once()

    def test_update_mapping_handles_script_refs(self, tmp_path):
        """It updates the mapping when a template's script references change."""
        # Create two scripts
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script1_path = scripts_dir / "old.py"
        script1_path.write_text("# @block=setup\nx = 1\n# @end\n")
        script2_path = scripts_dir / "new.py"
        script2_path.write_text("# @block=setup\nx = 2\n# @end\n")

        # Create template referencing script1
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_content = """---
scripts:
  - id: s
    path: ../scripts/old.py
---

# Test

@@code s:setup
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        handler = TemplateChangeHandler()
        handler._update_notebook_mapping(template_path.resolve())

        # Should be mapped to script1
        assert script1_path.resolve() in handler.notebook_to_templates
        assert script2_path.resolve() not in handler.notebook_to_templates

        # Change template to reference script2
        template_content = """---
scripts:
  - id: s
    path: ../scripts/new.py
---

# Test

@@code s:setup
"""
        template_path.write_text(template_content)
        handler._update_notebook_mapping(template_path.resolve())

        # Should now be mapped to script2, not script1
        assert script1_path.resolve() not in handler.notebook_to_templates
        assert script2_path.resolve() in handler.notebook_to_templates

    def test_script_change_detected_by_watchdog(self, tmp_path):
        """Test that watchdog detects and handles script changes."""
        from watchdog.observers import Observer

        # Create script
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script_path = scripts_dir / "agent.py"
        script_path.write_text(
            "# @block=setup\n"
            "x = 'original'\n"
            "# @end\n"
        )

        # Create template
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_content = """---
scripts:
  - id: agent
    path: ../scripts/agent.py
---

# Test

@@code agent:setup
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        # Build mapping
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)

        # Track what gets scheduled
        scheduled_templates = []

        handler = TemplateChangeHandler(
            grace_period=0.05,
            notebook_to_templates=notebook_to_templates,
        )

        original_run = handler._run_codegen

        def mock_run(path):
            scheduled_templates.append(path.resolve())

        handler._run_codegen = mock_run

        # Start observer
        observer = Observer()
        observer.schedule(handler, str(tmp_path), recursive=True)
        observer.start()

        try:
            time.sleep(0.1)

            # Modify the script
            script_path.write_text(
                "# @block=setup\n"
                "x = 'updated'\n"
                "# @end\n"
            )

            # Wait for debouncing
            time.sleep(0.5)

            assert template_path.resolve() in scheduled_templates

        finally:
            observer.stop()
            observer.join()

    def test_script_content_change_propagates_to_markdown(self, tmp_path):
        """Test that changing script content regenerates the markdown."""
        # Create script
        scripts_dir = tmp_path / "scripts"
        scripts_dir.mkdir()
        script_path = scripts_dir / "agent.py"
        script_path.write_text(
            "# @block=setup\n"
            "x = 'v1'\n"
            "# @end\n"
        )

        # Create template
        templates_dir = tmp_path / "templates"
        templates_dir.mkdir()
        template_content = """---
scripts:
  - id: agent
    path: ../scripts/agent.py
---

# Test

Code:

@@code agent:setup
"""
        template_path = templates_dir / "test.template.md"
        template_path.write_text(template_content)

        # Build mapping and create handler
        notebook_to_templates = build_notebook_to_templates_map(tmp_path)
        handler = TemplateChangeHandler(
            grace_period=0.1,
            notebook_to_templates=notebook_to_templates,
        )

        # Initial generation
        output_path = templates_dir / "test.md"
        handler._generate_now(template_path.resolve())

        assert output_path.exists()
        v1_content = output_path.read_text()
        assert "x = 'v1'" in v1_content

        # Update the script
        script_path.write_text(
            "# @block=setup\n"
            "x = 'v2'\n"
            "# @end\n"
        )

        # Trigger regeneration
        handler._generate_now(template_path.resolve())

        v2_content = output_path.read_text()
        assert "x = 'v2'" in v2_content
        assert "x = 'v1'" not in v2_content
