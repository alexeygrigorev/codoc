"""Batch command parsing and execution for the notebook editor."""

import sys
from dataclasses import dataclass
from pathlib import Path

from codoc.nb_edit.editor import FastNotebookEditor


BATCH_MARKER = "@>>"


def validate_content(content: str) -> None:
    """
    Validate content doesn't have excessive doubled line breaks.

    If content has 3 or more non-blank lines and contains doubled
    line breaks (more than 2 consecutive newlines), raise an error.

    Args:
        content: The content to validate

    Raises:
        ValueError: If doubled line breaks are detected
    """
    # Count non-blank lines
    non_blank_lines = [line for line in content.split("\n") if line.strip()]

    # Only check if we have substantial content (3 or more non-blank lines)
    if len(non_blank_lines) >= 3:
        # Check for doubled line breaks (more than 2 consecutive newlines)
        if "\n\n\n" in content:
            raise ValueError(
                "Doubled line breaks detected (more than 2 consecutive newlines). "
                "This may indicate a formatting issue with your batch file. "
                "Check that you haven't accidentally doubled the line breaks."
            )


@dataclass
class BatchCommand:
    """A single batch command."""

    name: str
    args: list[str]
    content: str

    def has_arg(self, arg: str) -> bool:
        """Check if the command has a specific argument."""
        return arg in self.args

    def get_arg_value(self, arg: str) -> str | None:
        """Get the value after a specific argument flag."""
        try:
            idx = self.args.index(arg)
            if idx + 1 < len(self.args):
                return self.args[idx + 1]
        except ValueError:
            pass
        return None


def parse_batch_commands(lines: list[str]) -> list[BatchCommand]:
    """
    Parse batch commands from lines.

    Each command starts with @>> followed by the command.
    Content for commands like --code continues until next @>> or EOF.
    Lines starting with -- (followed by a space) are treated as comments and ignored.

    Args:
        lines: List of lines from the batch file

    Returns:
        List of BatchCommand objects
    """
    commands = []
    current_command = None
    content_lines = []

    for line in lines:
        line = line.rstrip("\n")
        # Skip comment lines (-- must be at line start with a space, to avoid flag conflicts)
        if line.startswith("-- "):
            continue


        if line.startswith(BATCH_MARKER):
            # Save previous command if exists
            if current_command:
                current_command.content = "".join(content_lines).strip("\n")
                commands.append(current_command)

            # Start new command
            cmd_line = line[len(BATCH_MARKER):].strip()
            parts = cmd_line.split()
            current_command = BatchCommand(
                name=parts[0] if parts else "",
                args=parts[1:],
                content=""
            )
            content_lines = []
        elif current_command:
            content_lines.append(line + "\n")

    # Don't forget the last command
    if current_command:
        current_command.content = "".join(content_lines).strip("\n")
        commands.append(current_command)

    return commands


class BatchExecutor:
    """Executes batch commands on a notebook."""

    def __init__(self, notebook_path: str, commands: list[BatchCommand], auto_save: bool = True):
        """
        Initialize the executor.

        Args:
            notebook_path: Path to the notebook file
            commands: List of BatchCommand objects to execute
            auto_save: Automatically save after all commands (default: True)
        """
        self.notebook_path = notebook_path
        self.commands = commands
        self.auto_save = auto_save
        self.nb: FastNotebookEditor | None = None

    def execute(self) -> None:
        """Execute all batch commands."""
        self._load_notebook()
        self._run_commands()
        self._save()

    def _load_notebook(self) -> None:
        """Load or create the notebook."""
        path = Path(self.notebook_path)
        if not path.exists():
            # Auto-create if notebook doesn't exist
            self.nb = FastNotebookEditor.create(self.notebook_path)
        else:
            self.nb = FastNotebookEditor.load(path)

    def _run_commands(self) -> None:
        """Run all commands on the notebook."""
        for cmd in self.commands:
            try:
                self._execute_command(cmd)
            except Exception as e:
                print(f"Error executing command '{cmd.name}': {e}", file=sys.stderr)
                raise

    def _save(self) -> None:
        """Always save the notebook."""
        if self.nb:
            self.nb.save()
            print(f"Saved: {self.nb.path}")

    def _execute_command(self, cmd: BatchCommand) -> None:
        """Execute a single batch command."""
        if not self.nb:
            return

        name = cmd.name

        if name == "add":
            self._cmd_add(cmd)

        elif name == "insert-after-index":
            self._cmd_insert_after_index(cmd)

        elif name == "insert-after":
            self._cmd_insert_after(cmd)

        elif name == "update":
            self._cmd_update(cmd)

        elif name == "update-index":
            self._cmd_update_index(cmd)

        elif name == "delete":
            self._cmd_delete(cmd)

        elif name == "rename":
            self._cmd_rename(cmd)

        elif name == "add-id":
            self._cmd_add_id(cmd)

        elif name == "move":
            self._cmd_move(cmd)

        else:
            print(f"Warning: Unknown command '{name}'", file=sys.stderr)

    def _cmd_add(self, cmd: BatchCommand) -> None:
        """Handle the add command."""
        id_arg = cmd.get_arg_value("--id")

        validate_content(cmd.content)

        if cmd.has_arg("--markdown"):
            self.nb.add_markdown(cmd.content)
        elif cmd.has_arg("--code"):
            self.nb.add_code(cmd.content, id_arg)
        else:
            # If no flag was specified, treat as code
            self.nb.add_code(cmd.content, id_arg)

    def _cmd_insert_after_index(self, cmd: BatchCommand) -> None:
        """Handle the insert-after-index command."""
        id_arg = cmd.get_arg_value("--id")
        index_arg = None

        for arg in cmd.args:
            if arg.isdigit():
                index_arg = int(arg)
                break

        validate_content(cmd.content)

        if index_arg is not None:
            self.nb.insert_after_index(index_arg, cmd.content, id_arg)

    def _cmd_insert_after(self, cmd: BatchCommand) -> None:
        """Handle the insert-after command."""
        id_arg = cmd.get_arg_value("--id")
        after_id_arg = None

        for arg in cmd.args:
            if arg != "--id" and arg != "--code":
                after_id_arg = arg
                break

        validate_content(cmd.content)

        if after_id_arg:
            self.nb.insert_after_id(after_id_arg, cmd.content, id_arg)

    def _cmd_update(self, cmd: BatchCommand) -> None:
        """Handle the update command."""
        cell_id = None

        for arg in cmd.args:
            if arg != "--code":
                cell_id = arg
                break

        validate_content(cmd.content)

        if cell_id:
            self.nb.update_by_id(cell_id, cmd.content)

    def _cmd_update_index(self, cmd: BatchCommand) -> None:
        """Handle the update-index command."""
        index_arg = None

        for arg in cmd.args:
            if arg.isdigit():
                index_arg = int(arg)
                break

        validate_content(cmd.content)

        if index_arg is not None:
            self.nb.update_by_index(index_arg, cmd.content)

    def _cmd_delete(self, cmd: BatchCommand) -> None:
        """Handle the delete command (works with both index and ID)."""
        if cmd.args and cmd.args[0].isdigit():
            self.nb.delete_by_index(int(cmd.args[0]))
        elif cmd.args:
            self.nb.delete_by_id(cmd.args[0])

    def _cmd_rename(self, cmd: BatchCommand) -> None:
        """Handle the rename command."""
        cell_id = None
        new_id = cmd.get_arg_value("--new-id")

        for arg in cmd.args:
            if arg != "--new-id":
                cell_id = arg
                break

        if cell_id and new_id:
            self.nb.rename_id(cell_id, new_id)

    def _cmd_add_id(self, cmd: BatchCommand) -> None:
        """Handle the add-id command."""
        index_arg = None
        cell_id = None

        for arg in cmd.args:
            if arg.isdigit() and index_arg is None:
                index_arg = int(arg)
            elif cell_id is None:
                cell_id = arg

        if index_arg is not None and cell_id:
            self.nb.add_id(index_arg, cell_id)

    def _cmd_move(self, cmd: BatchCommand) -> None:
        """Handle the move command (move cell after another)."""
        if len(cmd.args) >= 2:
            cell_id = cmd.args[0]
            after_id = cmd.args[1]
            self.nb.move_id_after_id(cell_id, after_id)
