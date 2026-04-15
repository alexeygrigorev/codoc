"""CLI argument parsing and command handling for the notebook editor."""

import argparse
import io
import sys

from pathlib import Path
from codoc.nb_edit.editor import FastNotebookEditor, NotebookDict
from codoc.nb_edit.batch import validate_content


# Configure UTF-8 output for Windows console
# Skip when running under pytest to avoid conflicts with pytest's capture mechanism
if sys.platform == "win32" and "pytest" not in sys.argv[0]:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")


def run_batch_mode(notebook: str, batch_file: str) -> None:
    """
    Run the notebook editor in batch mode.

    Args:
        notebook: Path to the notebook file
        batch_file: Path to batch file, or '-' for stdin
    """
    from codoc.nb_edit.batch import BatchExecutor, parse_batch_commands

    # Read batch commands
    if batch_file == "-":
        lines = sys.stdin.readlines()
    else:
        with open(batch_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

    commands = parse_batch_commands(lines)
    executor = BatchExecutor(notebook, commands, auto_save=True)
    executor.execute()


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the notebook editor CLI."""
    parser = argparse.ArgumentParser(
        description="Fast notebook editor for convenient Jupyter notebook manipulation",
        prog="nbedit",
    )
    parser.add_argument("notebook", type=str, help="Path to the notebook file")
    parser.add_argument("--batch", type=str, help="Run batch commands from file (use '-' for stdin)")
    parser.add_argument("--batch-help", action="store_true", help="Show comprehensive batch mode help")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # list command
    list_parser = subparsers.add_parser("list", help="List all cells")
    list_parser.add_argument("--with-output", action="store_true", help="Show cell outputs")
    list_parser.add_argument("--limit", type=int, default=10, help="Limit output lines (only applies with --with-output, default: 10)")
    list_parser.add_argument("--line-numbers", "-n", action="store_true", help="Show line numbers for code cells")

    # get command
    get_parser = subparsers.add_parser("get", help="Get a cell by ID")
    get_parser.add_argument("cell_id", type=str, help="Cell ID to retrieve")
    get_parser.add_argument("--with-output", action="store_true", help="Show cell output")
    get_parser.add_argument("--limit", type=int, default=10, help="Limit output lines (only applies with --with-output, default: 10)")

    # add command
    add_parser = subparsers.add_parser("add", help="Add a cell")
    add_parser.add_argument("--code", type=str, help="Code content (use '-' for stdin)")
    add_parser.add_argument("--markdown", type=str, help="Markdown content")
    add_parser.add_argument("--id", type=str, help="Cell ID for @cell_id marker")

    # insert-after command
    insert_parser = subparsers.add_parser("insert-after", help="Insert after a cell by ID")
    insert_parser.add_argument("after_id", type=str, help="Cell ID to insert after")
    insert_parser.add_argument("--code", type=str, help="Code to insert (use '-' for stdin)")
    insert_parser.add_argument("--id", type=str, help="Cell ID for new cell")

    # insert-after-index command
    insert_index_parser = subparsers.add_parser("insert-after-index", help="Insert after cell by index (1-based)")
    insert_index_parser.add_argument("index", type=int, help="Cell index (1-based)")
    insert_index_parser.add_argument("--code", type=str, help="Code to insert (use '-' for stdin)")
    insert_index_parser.add_argument("--id", type=str, help="Cell ID for new cell")

    # update command
    update_parser = subparsers.add_parser("update", help="Update a cell by ID")
    update_parser.add_argument("cell_id", type=str, help="Cell ID to update")
    update_parser.add_argument("--code", type=str, help="New code content (use '-' for stdin)")

    # update-index command
    update_index_parser = subparsers.add_parser("update-index", help="Update a cell by index")
    update_index_parser.add_argument("index", type=int, help="Cell index (1-based)")
    update_index_parser.add_argument("--code", type=str, help="New code content (use '-' for stdin)")

    # delete command (works with both index and ID)
    delete_parser = subparsers.add_parser("delete", help="Delete a cell (by index or ID)")
    delete_parser.add_argument("identifier", type=str, help="Cell index (number) or ID")

    # rename command
    rename_parser = subparsers.add_parser("rename", help="Rename a cell ID")
    rename_parser.add_argument("cell_id", type=str, help="Current cell ID")
    rename_parser.add_argument("--new-id", type=str, required=True, help="New cell ID")

    # add-id command
    add_id_parser = subparsers.add_parser("add-id", help="Add @cell_id to a cell")
    add_id_parser.add_argument("index", type=int, help="Cell index (1-based)")
    add_id_parser.add_argument("cell_id", type=str, help="Cell ID to add")

    # move command
    move_parser = subparsers.add_parser("move", help="Move a cell after another cell")
    move_parser.add_argument("cell_id", type=str, help="Cell ID to move")
    move_parser.add_argument("after_id", type=str, help="Move after this cell ID")

    # execute command
    execute_parser = subparsers.add_parser("execute", help="Execute the notebook and save outputs")
    execute_parser.add_argument("--kernel", type=str, default="python3", help="Kernel name to use (default: python3)")

    # export-image command
    export_image_parser = subparsers.add_parser("export-image", help="Export an image from a cell's output")
    export_image_parser.add_argument("identifier", type=str, help="Cell index (number) or ID")
    export_image_parser.add_argument("output", type=str, help="Output file path")
    export_image_parser.add_argument("--format", type=str, choices=["jpg", "png"], default="jpg", help="Output format (default: jpg)")
    export_image_parser.add_argument("--quality", type=int, default=85, help="JPEG quality 1-100 (default: 85, only for jpg format)")

    # remove-ids command
    subparsers.add_parser("remove-ids", help="Remove all @cell_id markers from the notebook")

    return parser


BATCH_HELP = """
BATCH MODE (Recommended for most workflows)

Batch mode lets you execute multiple nbedit commands at once. Create a batch file
with commands starting with @>>:

    uv run nbedit notebook.ipynb --batch batch-file.txt

Use '-' for stdin:

    cat batch.txt | uv run nbedit notebook.ipynb --batch -

The notebook is automatically created if it doesn't exist, and saved after all
commands complete.

INDEXING NOTE
Cell indices use 1-based indexing (1, 2, 3...) instead of 0-based. This matches
how humans count and is more intuitive when working with line numbers in editors.

COMMENTS
Lines starting with '-- ' (double dash followed by a space) are treated as comments:

    -- This is a comment
    -- So is this

    @>> add --id my-cell
    print("hello")

BATCH COMMANDS
  add [--id ID]
      Add a code cell with optional @cell_id marker

  add --markdown
      Add a markdown cell (content follows the command)

  insert-after INDEX|ID [--id ID]
      Insert a code cell after the specified index or cell_id

  update INDEX|ID
      Update cell by index or ID (new code follows the command)

  delete INDEX|ID
      Delete cell by index or ID

  rename ID --new-id NEW
      Rename a cell ID

  add-id INDEX ID
      Add @cell_id marker to cell at index

  move ID AFTER_ID
      Move a cell after another cell

BATCH EXAMPLES

Creating a new notebook:

    @>> add --id setting-up
    from openai import OpenAI
    client = OpenAI()

    @>> add --id first-request
    messages = [{"role": "user", "content": "hello"}]
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=messages
    )
    print(response.choices[0].message.content)

Updating an existing cell by ID:

    @>> update my-cell
    def new_function():
        return "updated"

Deleting a cell by index (1-based):

    @>> delete 3

Renaming a cell ID:

    @>> rename old-id --new-id new-id

Moving a cell after another:

    @>> move cell-to-move target-cell

COMMON SCENARIOS

Create a notebook from scratch:

    @>> add --id imports
    import pandas as pd
    import numpy as np

    @>> add --id load-data
    df = pd.read_csv("data.csv")
    print(df.head())

    @>> add --id process
    df["total"] = df["quantity"] * df["price"]
    print(df.describe())

Add a cell after an existing one:

    @>> insert-after load-data --id visualize
    import matplotlib.pyplot as plt
    df.plot(x="date", y="total")
    plt.show()

COMMON MISTAKES

Wrong: Using '--' after cell_id (confusing with other CLI conventions)

    @>> update my-cell --
    code here

Correct: Code follows directly after the command line

    @>> update my-cell
    code here

The '--' separator used by some tools (like git) is NOT valid in nbedit batch mode.
Code content continues on the lines following the @>> command.
"""


def run_single_command(args: argparse.Namespace) -> None:
    """
    Execute a single command on a notebook.

    Args:
        args: Parsed arguments from argparse
    """
    # Handle batch mode
    if args.batch:
        run_batch_mode(args.notebook, args.batch)
        return

    # Load or create the notebook
    notebook_path = Path(args.notebook)
    if not notebook_path.exists():
        nb = FastNotebookEditor.create(notebook_path)
    else:
        nb = FastNotebookEditor.load(notebook_path)

    # Helper function to read code from stdin if needed
    def get_code(code_arg):
        if code_arg == "-":
            return sys.stdin.read()
        return code_arg

    if args.command == "list":
        nb.list(with_output=args.with_output, limit=args.limit, line_numbers=args.line_numbers)

    elif args.command == "get":
        nb.get(args.cell_id, with_output=args.with_output, limit=args.limit)

    elif args.command == "add":
        if args.code:
            code = get_code(args.code)
            validate_content(code)
            nb.add_code(code, args.id)
        elif args.markdown:
            nb.add_markdown(args.markdown)
        else:
            print("Error: Specify --code or --markdown", file=sys.stderr)
            sys.exit(1)
        nb.save()

    elif args.command == "insert-after":
        if args.code:
            code = get_code(args.code)
            validate_content(code)
            nb.insert_after_id(args.after_id, code, args.id)
        nb.save()

    elif args.command == "insert-after-index":
        if args.code:
            code = get_code(args.code)
            validate_content(code)
            nb.insert_after_index(args.index, code, args.id)
        nb.save()

    elif args.command == "update":
        if args.code:
            code = get_code(args.code)
            validate_content(code)
            nb.update_by_id(args.cell_id, code)
        nb.save()

    elif args.command == "update-index":
        if args.code:
            code = get_code(args.code)
            validate_content(code)
            nb.update_by_index(args.index, code)
        nb.save()

    elif args.command == "delete":
        identifier = args.identifier
        if identifier.isdigit():
            nb.delete_by_index(int(identifier))
        else:
            nb.delete_by_id(identifier)
        nb.save()

    elif args.command == "rename":
        nb.rename_id(args.cell_id, args.new_id)
        nb.save()

    elif args.command == "add-id":
        nb.add_id(args.index, args.cell_id)
        nb.save()

    elif args.command == "move":
        nb.move_id_after_id(args.cell_id, args.after_id)
        nb.save()

    elif args.command == "execute":
        from nbclient import NotebookClient
        import nbformat

        # Convert our notebook dict to nbformat node
        # Ensure source fields are strings (nbclient expects strings, not lists)
        nb_dict = dict(nb.notebook)
        for cell in nb_dict.get("cells", []):
            if isinstance(cell.get("source"), list):
                cell["source"] = "".join(cell["source"])

        nb_node = nbformat.from_dict(nb_dict)

        # Inject a cell at the beginning to add the notebook's directory to sys.path
        # This allows notebooks to import local Python modules from the same directory
        notebook_dir = notebook_path.resolve().parent
        sys_path_setup_cell = nbformat.v4.new_code_cell(
            source=f'''import sys
from pathlib import Path
notebook_dir = Path(r"{notebook_dir}").resolve()
if str(notebook_dir) not in sys.path:
    sys.path.insert(0, str(notebook_dir))
''',
            cell_type="code",
            metadata={"trusted": True},
        )
        # Insert at the beginning
        nb_node.cells.insert(0, sys_path_setup_cell)

        # Execute the notebook
        client = NotebookClient(
            nb_node,
            kernel_name=args.kernel,
            record_timing=False,
        )
        print(f"Executing notebook with kernel '{args.kernel}'...")
        client.execute()

        # Remove the injected sys.path setup cell before saving
        nb_node.cells.pop(0)

        # Update our notebook with the executed results
        nb.notebook = NotebookDict(dict(nb_node))
        nb.save()
        print(f"Executed and saved: {args.notebook}")

    elif args.command == "export-image":
        if args.quality < 1 or args.quality > 100:
            print("Error: --quality must be between 1 and 100", file=sys.stderr)
            sys.exit(1)

        nb.extract_image(
            identifier=args.identifier,
            output_path=Path(args.output),
            format=args.format,
            quality=args.quality,
        )
        print(f"Image exported to: {args.output}")

    elif args.command == "remove-ids":
        count = nb.remove_all_ids()
        nb.save()
        print(f"Removed {count} cell_id marker(s)")


def run_cli() -> None:
    """Run the notebook editor CLI."""
    # Handle --batch-help flag before argument parsing (it doesn't require a notebook)
    if "--batch-help" in sys.argv:
        print(BATCH_HELP)
        return

    parser = create_parser()
    args = parser.parse_args()

    if not args.command and not args.batch:
        parser.print_help()
        sys.exit(1)

    try:
        run_single_command(args)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
