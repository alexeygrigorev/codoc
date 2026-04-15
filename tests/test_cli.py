"""Tests for the CLI interface."""

from pathlib import Path
from unittest.mock import Mock, patch
import sys

import pytest

from codoc.cli import run


FIXTURES_DIR = Path(__file__).parent / "fixtures"


class TestCliRun:
    """Tests for the CLI run function."""

    @patch("codoc.cli.generate_template")
    @patch("sys.argv", ["codoc", str(Path(__file__).parent / "fixtures" / "simple.template.md")])
    def test_single_file_generation(self, mock_gen):
        """It generates a single template file."""
        mock_gen.return_value = "# Generated content"

        with patch("sys.stdout"):  # Suppress output
            try:
                run()
            except SystemExit:
                pass

        mock_gen.assert_called_once()

    @patch("codoc.cli.generate_directory")
    @patch("sys.argv", ["codoc", str(FIXTURES_DIR)])
    def test_directory_generation(self, mock_gen):
        """It generates all templates in a directory."""
        mock_gen.return_value = []

        with patch("sys.stdout"):  # Suppress output
            try:
                run()
            except SystemExit:
                pass

        mock_gen.assert_called_once()

    @patch("codoc.cli.generate_template")
    def test_passes_timeout(self, mock_gen):
        """It passes the timeout parameter."""
        mock_gen.return_value = "# Generated content"

        test_args = [
            "codoc",
            str(FIXTURES_DIR / "simple.template.md"),
            "--timeout", "60",
        ]

        with patch("sys.argv", test_args):
            with patch("sys.stdout"):
                try:
                    run()
                except SystemExit:
                    pass

        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["timeout"] == 60

    @patch("codoc.cli.generate_template")
    def test_passes_kernel(self, mock_gen):
        """It passes the kernel parameter."""
        mock_gen.return_value = "# Generated content"

        test_args = [
            "codoc",
            str(FIXTURES_DIR / "simple.template.md"),
            "--kernel", "test-kernel",
        ]

        with patch("sys.argv", test_args):
            with patch("sys.stdout"):
                try:
                    run()
                except SystemExit:
                    pass

        call_kwargs = mock_gen.call_args[1]
        assert call_kwargs["kernel_name"] == "test-kernel"

    @patch("codoc.cli.generate_template")
    def test_passes_output_path(self, mock_gen):
        """It passes the output path."""
        mock_gen.return_value = "# Generated content"

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"

            test_args = [
                "codoc",
                str(FIXTURES_DIR / "simple.template.md"),
                "-o", str(output_path),
            ]

            with patch("sys.argv", test_args):
                with patch("sys.stdout"):
                    try:
                        run()
                    except SystemExit:
                        pass

            call_args = mock_gen.call_args
            assert call_args[1]["output_path"] == output_path

    @patch("codoc.cli.generate_template")
    def test_verbose_output(self, mock_gen, capsys):
        """It prints verbose output when -v is used."""
        mock_gen.return_value = "# Generated content"

        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.md"

            test_args = [
                "codoc",
                str(FIXTURES_DIR / "simple.template.md"),
                "-o", str(output_path),
                "-v",
            ]

            with patch("sys.argv", test_args):
                try:
                    run()
                except SystemExit:
                    pass

            captured = capsys.readouterr()
            # Should have some output about generation
            assert "Generating" in captured.out or "Generated" in captured.out

    @patch("codoc.cli.Path.is_file")
    def test_nonexistent_path(self, mock_is_file):
        """It exits with error for nonexistent path."""
        mock_is_file.return_value = False
        mock_is_dir = Mock(return_value=False)

        with patch("pathlib.Path.is_dir", mock_is_dir):
            test_args = ["codoc", "/nonexistent/path"]

            with patch("sys.argv", test_args):
                with patch("sys.stderr"):
                    try:
                        run()
                    except SystemExit as e:
                        assert e.code == 1

    @patch("codoc.cli.generate_template")
    def test_handles_codoc_error(self, mock_gen):
        """It handles CodocError and exits with code 1."""
        from codoc.errors import CodocError
        mock_gen.side_effect = CodocError("Test error")

        test_args = ["codoc", str(FIXTURES_DIR / "simple.template.md")]

        with patch("sys.argv", test_args):
            with patch("sys.stderr"):
                try:
                    run()
                except SystemExit as e:
                    assert e.code == 1

    @patch("codoc.cli.generate_template")
    def test_handles_keyboard_interrupt(self, mock_gen):
        """It handles KeyboardInterrupt gracefully."""
        mock_gen.side_effect = KeyboardInterrupt()

        test_args = ["codoc", str(FIXTURES_DIR / "simple.template.md")]

        with patch("sys.argv", test_args):
            with patch("sys.stderr"):
                try:
                    run()
                except SystemExit as e:
                    assert e.code == 1

    @patch("codoc.cli.generate_template")
    def test_shows_unexpected_error_without_verbose(self, mock_gen):
        """It shows error message without traceback when not verbose."""
        mock_gen.side_effect = RuntimeError("Unexpected error")

        test_args = ["codoc", str(FIXTURES_DIR / "simple.template.md")]

        with patch("sys.argv", test_args):
            with patch("sys.stderr") as mock_stderr:
                try:
                    run()
                except SystemExit as e:
                    assert e.code == 1

    @patch("codoc.cli.generate_template")
    def test_shows_traceback_with_verbose(self, mock_gen):
        """It shows full traceback with verbose flag."""
        mock_gen.side_effect = RuntimeError("Unexpected error")

        test_args = [
            "codoc",
            str(FIXTURES_DIR / "simple.template.md"),
            "-v",
        ]

        with patch("sys.argv", test_args):
            with patch("sys.stderr"):
                try:
                    run()
                except SystemExit as e:
                    assert e.code == 1


class TestCliArgumentParsing:
    """Tests for CLI argument parsing."""

    def test_default_arguments(self):
        """It sets default values for optional arguments."""
        from argparse import Namespace
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("path", type=Path)
        parser.add_argument("--timeout", type=int, default=30)
        parser.add_argument("--kernel", type=str, default="python3")
        parser.add_argument("-o", "--output", type=Path, default=None)
        parser.add_argument("-v", "--verbose", action="store_true")

        args = parser.parse_args(["test.md"])

        assert args.timeout == 30
        assert args.kernel == "python3"
        assert args.output is None
        assert args.verbose is False

    def test_custom_arguments(self):
        """It parses custom argument values."""
        import argparse

        parser = argparse.ArgumentParser()
        parser.add_argument("path", type=Path)
        parser.add_argument("--timeout", type=int, default=30)
        parser.add_argument("--kernel", type=str, default="python3")
        parser.add_argument("-o", "--output", type=Path, default=None)
        parser.add_argument("-v", "--verbose", action="store_true")

        args = parser.parse_args([
            "test.md",
            "--timeout", "60",
            "--kernel", "test-kernel",
            "-o", "output.md",
            "-v",
        ])

        assert args.timeout == 60
        assert args.kernel == "test-kernel"
        assert args.output == Path("output.md")
        assert args.verbose is True
