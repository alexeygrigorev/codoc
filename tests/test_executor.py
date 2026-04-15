"""Tests for notebook execution and validation."""

from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from nbformat import NotebookNode

from codoc.executor import validate_notebook, validate_notebook_for_cells
from codoc.errors import ExecutionError
from codoc.nb_edit.editor import load_notebook


FIXTURES_DIR = Path(__file__).parent / "fixtures" / "notebooks"


class TestValidateNotebook:
    """Tests for validate_notebook function."""

    @patch("codoc.executor.ExecutePreprocessor")
    def test_validates_successful_execution(self, mock_ep_class):
        """It successfully validates a notebook that runs without errors."""
        # Mock the executor
        mock_executor = Mock()
        mock_executor.preprocess.return_value = (Mock(), {})
        mock_ep_class.return_value = mock_executor

        notebook_path = FIXTURES_DIR / "error-test.ipynb"
        result = validate_notebook(notebook_path)

        assert result is not None
        mock_executor.preprocess.assert_called_once()

    @patch("codoc.executor.ExecutePreprocessor")
    def test_passes_timeout_to_executor(self, mock_ep_class):
        """It passes the timeout parameter to the executor."""
        mock_executor = Mock()
        mock_executor.preprocess.return_value = (Mock(), {})
        mock_ep_class.return_value = mock_executor

        notebook_path = FIXTURES_DIR / "error-test.ipynb"
        validate_notebook(notebook_path, timeout=60)

        # Check ExecutePreprocessor was called with timeout=60
        mock_ep_class.assert_called_once()
        call_kwargs = mock_ep_class.call_args[1]
        assert call_kwargs["timeout"] == 60

    @patch("codoc.executor.ExecutePreprocessor")
    def test_passes_kernel_name_to_executor(self, mock_ep_class):
        """It passes the kernel_name parameter to the executor."""
        mock_executor = Mock()
        mock_executor.preprocess.return_value = (Mock(), {})
        mock_ep_class.return_value = mock_executor

        notebook_path = FIXTURES_DIR / "error-test.ipynb"
        validate_notebook(notebook_path, kernel_name="python3-test")

        # Check ExecutePreprocessor was called with kernel_name
        mock_ep_class.assert_called_once()
        call_kwargs = mock_ep_class.call_args[1]
        assert call_kwargs["kernel_name"] == "python3-test"

    @patch("codoc.executor.ExecutePreprocessor")
    def test_raises_error_on_execution_failure(self, mock_ep_class):
        """It raises ExecutionError when notebook execution fails."""
        mock_executor = Mock()
        mock_executor.preprocess.side_effect = Exception("Cell execution failed")
        mock_ep_class.return_value = mock_executor

        notebook_path = FIXTURES_DIR / "error-test.ipynb"

        with pytest.raises(ExecutionError) as exc_info:
            validate_notebook(notebook_path)

        assert "error-test.ipynb" in str(exc_info.value)
        assert "Cell execution failed" in str(exc_info.value)

    @patch("codoc.executor.ExecutePreprocessor")
    def test_allows_errors_false(self, mock_ep_class):
        """It configures executor to stop on errors."""
        mock_executor = Mock()
        mock_executor.preprocess.return_value = (Mock(), {})
        mock_ep_class.return_value = mock_executor

        notebook_path = FIXTURES_DIR / "error-test.ipynb"
        validate_notebook(notebook_path)

        # Check that allow_errors is False
        call_kwargs = mock_ep_class.call_args[1]
        assert call_kwargs["allow_errors"] is False


class TestValidateNotebookForCells:
    """Tests for validate_notebook_for_cells function."""

    def test_validates_all_required_cells_exist(self):
        """It checks that all required cells exist in the notebook."""
        notebook_path = FIXTURES_DIR / "sample.ipynb"

        # Mock the validation to avoid actual execution
        with patch("codoc.executor.validate_notebook") as mock_validate:
            mock_validate.return_value = load_notebook(notebook_path)
            result = validate_notebook_for_cells(
                notebook_path,
                cell_ids=["print-hello", "answer"],
            )
            assert result is not None

    def test_raises_error_for_missing_cells(self):
        """It raises error when required cells are not found."""
        notebook_path = FIXTURES_DIR / "sample.ipynb"

        with patch("codoc.executor.validate_notebook") as mock_validate:
            mock_validate.return_value = load_notebook(notebook_path)

            with pytest.raises(ExecutionError) as exc_info:
                validate_notebook_for_cells(
                    notebook_path,
                    cell_ids=["print-hello", "nonexistent-cell"],
                )

            assert "not found" in str(exc_info.value)
            assert "nonexistent-cell" in str(exc_info.value)

    def test_passes_params_to_validate_notebook(self):
        """It passes timeout and kernel_name to validate_notebook."""
        notebook_path = FIXTURES_DIR / "sample.ipynb"

        with patch("codoc.executor.validate_notebook") as mock_validate:
            mock_validate.return_value = load_notebook(notebook_path)

            validate_notebook_for_cells(
                notebook_path,
                cell_ids=["print-hello"],
                timeout=45,
                kernel_name="test-kernel",
            )

            mock_validate.assert_called_once_with(
                notebook_path,
                timeout=45,
                kernel_name="test-kernel",
            )

    def test_handles_empty_cell_list(self):
        """It handles an empty list of cell IDs."""
        notebook_path = FIXTURES_DIR / "sample.ipynb"

        with patch("codoc.executor.validate_notebook") as mock_validate:
            mock_validate.return_value = load_notebook(notebook_path)

            # Empty list should just validate the notebook
            result = validate_notebook_for_cells(
                notebook_path,
                cell_ids=[],
            )
            assert result is not None


class TestExecutorIntegration:
    """Integration tests for the executor module."""

    def test_notebook_loading(self):
        """It can load notebooks without execution."""
        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")
        assert notebook is not None
        assert len(notebook.cells) > 0

    def test_cell_extraction_before_validation(self):
        """It can extract cells before validating."""
        from codoc.nb_edit.editor import find_cells_by_id

        notebook = load_notebook(FIXTURES_DIR / "sample.ipynb")
        cells = find_cells_by_id(notebook)

        assert "print-hello" in cells
        assert "answer" in cells
        assert "import-math" in cells
        assert "no-output" in cells
