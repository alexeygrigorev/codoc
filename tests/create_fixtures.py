"""Create test notebook fixtures programmatically, execute them, and save with outputs."""

from pathlib import Path
import nbformat as nbf
from nbconvert.preprocessors import ExecutePreprocessor
import tempfile


def create_and_execute_notebook(cells, path: Path, timeout=30):
    """Create a notebook, execute it, and save with outputs."""
    nb = nbf.v4.new_notebook()
    nb['cells'] = cells

    # Execute the notebook
    executor = ExecutePreprocessor(timeout=timeout, kernel_name='python3')

    with tempfile.TemporaryDirectory() as tmpdir:
        # Execute in temp directory
        executed_nb, _ = executor.preprocess(nb, {'metadata': {'path': tmpdir}})

    # Save with outputs
    with open(path, 'w') as f:
        nbf.write(executed_nb, f)


def create_sample_notebook(path: Path):
    """Create sample.ipynb with various cell types and markers."""
    cells = [
        nbf.v4.new_code_cell(
            """# @cell_id=print-hello
print("Hello, World!")"""),
        nbf.v4.new_code_cell(
            """# @cell_id=answer

42"""),
        nbf.v4.new_code_cell(
            """# @cell_id=import-math
import math
result = math.sqrt(16)"""),
        nbf.v4.new_code_cell(
            """# @cell_id=no-output

# This only has output from print
print([1, 2, 3])"""),
        nbf.v4.new_markdown_cell(
            """## This is a markdown cell
It should be ignored."""
        ),
        nbf.v4.new_code_cell(
            """# This cell has no @cell_id marker
x = 42"""
        ),
    ]

    create_and_execute_notebook(cells, path)


def create_sample2_notebook(path: Path):
    """Create sample2.ipynb with a list result."""
    cells = [
        nbf.v4.new_code_cell(
            """# @cell_id=list-result
result = ['a', 'b', 'c']
result"""),
    ]

    create_and_execute_notebook(cells, path)


def create_error_test_notebook(path: Path):
    """Create error-test.ipynb with a working cell."""
    cells = [
        nbf.v4.new_code_cell(
            """# @cell_id=working-cell
print("Success!")"""),
    ]

    create_and_execute_notebook(cells, path)


if __name__ == "__main__":
    fixtures_dir = Path(__file__).parent / "fixtures" / "notebooks"
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    print("Creating and executing test notebooks...")
    create_sample_notebook(fixtures_dir / "sample.ipynb")
    create_sample2_notebook(fixtures_dir / "sample2.ipynb")
    create_error_test_notebook(fixtures_dir / "error-test.ipynb")

    print("Created test notebook fixtures:")
    print(f"  {fixtures_dir / 'sample.ipynb'}")
    print(f"  {fixtures_dir / 'sample2.ipynb'}")
    print(f"  {fixtures_dir / 'error-test.ipynb'}")
