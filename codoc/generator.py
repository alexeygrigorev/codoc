"""Generate markdown files from templates by pulling code from Jupyter notebooks and scripts."""

from pathlib import Path

from codoc.executor import validate_notebook_for_cells
from codoc.nobook import execute_nobook, load_nobook
from codoc.parser import (
    CodeDirective,
    CodeFigureDirective,
    CodeOutputDirective,
    NotebookRef,
    ScriptRef,
    parse_template,
)
from codoc.utils import resolve_notebook_path


def _strip_frontmatter(content: str) -> str:
    """Strip YAML frontmatter from generated markdown, returning just the body.

    The frontmatter contains the generated_at timestamp which changes every run.
    Stripping it allows comparing the actual content between runs.
    """
    if not content.startswith("---"):
        return content
    # Find the closing ---
    end = content.find("\n---\n", 1)
    if end == -1:
        return content
    # Skip the closing --- and any leading newlines after it
    body = content[end + 4:]  # skip \n---\n
    # Strip leading newlines that are part of the frontmatter separator
    body = body.lstrip("\n")
    return body


class DirectiveVisitor:
    """Visitor for processing directives during code generation."""

    def __init__(
        self,
        loaded_notebooks: dict,
        notebook_refs: dict,
        output_path: Path,
        loaded_scripts: dict | None = None,
        script_refs: dict | None = None,
        notebook_kinds: dict[str, str] | None = None,
    ):
        self.loaded_notebooks = loaded_notebooks
        self.notebook_refs = notebook_refs
        self.output_path = output_path
        self.loaded_scripts = loaded_scripts or {}
        self.script_refs = script_refs or {}
        self.notebook_kinds = notebook_kinds or {}

    def _apply_line_params(self, source: str, directive: CodeDirective) -> str:
        """Apply lines= and strip-spaces= parameters to source code."""
        if directive.lines is not None:
            source_lines = source.split("\n")
            from_line, to_line = directive.lines
            source = "\n".join(source_lines[from_line - 1 : to_line])

        if directive.strip_spaces is not None:
            n = directive.strip_spaces
            stripped_lines = []
            for line in source.split("\n"):
                leading = len(line) - len(line.lstrip(" "))
                remove = min(n, leading)
                stripped_lines.append(line[remove:])
            source = "\n".join(stripped_lines)

        return source

    def visit_code(self, directive: CodeDirective) -> str:
        """Process a @@code directive."""
        # Check if source is a script first
        if directive.notebook_id in self.loaded_scripts:
            blocks, language = self.loaded_scripts[directive.notebook_id]
            from codoc.errors import BlockNotFoundError

            if directive.cell_id not in blocks:
                script_ref = self.script_refs[directive.notebook_id]
                raise BlockNotFoundError(script_ref.path, directive.cell_id)

            source = blocks[directive.cell_id].source
            source = self._apply_line_params(source, directive)
            return f"```{language}\n{source}\n```"

        # Fall through to notebook logic
        from codoc.nb_edit.editor import get_cell_by_id
        from codoc.utils import strip_try_except

        notebook, notebook_path = self.loaded_notebooks[directive.notebook_id]
        cell_info = get_cell_by_id(notebook, directive.cell_id, str(notebook_path))

        source = cell_info.source.strip()

        # If failing=true, strip try/except wrapper and de-indent
        if cell_info.attributes.get("failing") == "true":
            source = strip_try_except(source)

        source = self._apply_line_params(source, directive)

        return f"```python\n{source}\n```"

    def visit_code_output(self, directive: CodeOutputDirective) -> str:
        """Process a @@code-output directive."""
        # Scripts don't support @@code-output
        if directive.notebook_id in self.loaded_scripts:
            from codoc.errors import InvalidDirectiveError
            raise InvalidDirectiveError(
                directive.raw_line,
                "@@code-output is not supported for scripts (scripts have no execution output)",
            )

        from codoc.nb_edit.editor import get_cell_by_id, get_cell_output
        from codoc.errors import EmptyOutputError

        notebook, notebook_path = self.loaded_notebooks[directive.notebook_id]
        cell_info = get_cell_by_id(notebook, directive.cell_id, str(notebook_path))
        cell = notebook.cells[cell_info.cell_index]
        output = get_cell_output(cell)

        if not output.has_output:
            raise EmptyOutputError(str(notebook_path), directive.cell_id)

        output_text = output.text

        # Apply limit-lines if specified
        if directive.limit_lines is not None:
            lines = output_text.split("\n")
            if len(lines) > directive.limit_lines:
                output_text = "\n".join(lines[:directive.limit_lines]) + "\n..."

        # Apply limit-chars if specified (after limit-lines for consistency)
        if directive.limit_chars is not None:
            if len(output_text) > directive.limit_chars:
                output_text = output_text[:directive.limit_chars] + "..."

        return f"```python\n{output_text}\n```"

    def visit_code_figure(self, directive: CodeFigureDirective) -> str:
        """Process a @@code-figure directive."""
        # Scripts don't support @@code-figure
        if directive.notebook_id in self.loaded_scripts:
            from codoc.errors import InvalidDirectiveError
            raise InvalidDirectiveError(
                directive.raw_line,
                "@@code-figure is not supported for scripts (scripts have no execution output)",
            )
        if self.notebook_kinds.get(directive.notebook_id) == "nobook":
            from codoc.errors import InvalidDirectiveError
            raise InvalidDirectiveError(
                directive.raw_line,
                "@@code-figure is not supported for nobook sources",
            )

        from codoc.nb_edit.editor import FastNotebookEditor

        notebook, notebook_path = self.loaded_notebooks[directive.notebook_id]

        # Get the notebook ref to find image folder
        ref = self.notebook_refs.get(directive.notebook_id)
        image_folder = ref.image_folder if ref else None

        # Determine image filename: use cell_id
        image_filename = f"{directive.cell_id}.{directive.format}"
        if image_folder:
            image_rel_path = f"{image_folder}/{image_filename}"
        else:
            image_rel_path = f"images/{image_filename}"

        # Full path for the image file
        image_full_path = self.output_path.parent / image_rel_path

        # Create editor and extract image
        editor = FastNotebookEditor(notebook, None)
        editor.extract_image(
            identifier=directive.cell_id,
            output_path=image_full_path,
            format=directive.format,
            quality=directive.quality,
        )

        # Return markdown image reference
        return f"![{directive.cell_id}]({image_rel_path})"


class Generator:
    """Generate markdown files from templates."""

    def __init__(self, timeout: int = 30, kernel_name: str = "python3"):
        """
        Initialize the generator.

        Args:
            timeout: Timeout for notebook execution in seconds
            kernel_name: Jupyter kernel name to use for execution
        """
        self.timeout = timeout
        self.kernel_name = kernel_name

    def generate(self, template_path: Path, output_path: Path | None = None) -> str:
        """
        Generate a markdown file from a template.

        Args:
            template_path: Path to the .template.md file
            output_path: Where to write the output. If None, derives from template_path
                        (e.g., "file.template.md" -> "file.md")

        Returns:
            The generated markdown content

        Raises:
            CodocError: If generation fails
        """

        # Parse the template
        parsed = parse_template(template_path)

        # Determine output path
        if output_path is None:
            output_path = self._derive_output_path(template_path)

        # Collect all source references and required cells/blocks
        notebook_cells: dict[str, list[str]] = {}  # notebook_id -> [cell_ids]
        script_blocks: dict[str, list[str]] = {}  # script_id -> [block_ids]

        for directive in parsed.directives:
            source_id = directive.notebook_id
            target_id = directive.cell_id

            if source_id in parsed.script_refs:
                if source_id not in script_blocks:
                    script_blocks[source_id] = []
                if target_id not in script_blocks[source_id]:
                    script_blocks[source_id].append(target_id)
            else:
                if source_id not in notebook_cells:
                    notebook_cells[source_id] = []
                if target_id not in notebook_cells[source_id]:
                    notebook_cells[source_id].append(target_id)

        # Load and validate notebooks
        loaded_notebooks: dict[str, tuple] = {}  # notebook_id -> (notebook, notebook_path)
        notebook_kinds: dict[str, str] = {}

        for notebook_id, cell_ids in notebook_cells.items():
            if notebook_id not in parsed.notebook_refs:
                from codoc.errors import ParseError
                raise ParseError(
                    str(template_path),
                    f"Unknown source reference '{notebook_id}' in directive"
                )

            ref: NotebookRef = parsed.notebook_refs[notebook_id]
            notebook_path = resolve_notebook_path(template_path, ref.path)
            notebook_kinds[notebook_id] = "nobook" if notebook_path.suffix == ".py" else "ipynb"

            if notebook_path.suffix == ".py":
                if ref.execute:
                    loaded_notebooks[notebook_id] = (execute_nobook(notebook_path, cell_ids), notebook_path)
                else:
                    loaded_notebooks[notebook_id] = (load_nobook(notebook_path), notebook_path)
            else:
                # Execute if notebook has execute=True
                if ref.execute:
                    executed_notebook = validate_notebook_for_cells(
                        notebook_path,
                        cell_ids=cell_ids,
                        timeout=self.timeout,
                        kernel_name=self.kernel_name,
                    )
                    loaded_notebooks[notebook_id] = (executed_notebook, notebook_path)
                else:
                    from codoc.nb_edit.editor import load_notebook
                    notebook = load_notebook(notebook_path)
                    loaded_notebooks[notebook_id] = (notebook, notebook_path)

        # Load scripts
        loaded_scripts: dict[str, tuple] = {}  # script_id -> (blocks_dict, language)

        for script_id in script_blocks:
            ref: ScriptRef = parsed.script_refs[script_id]
            script_path = template_path.parent / ref.path

            from codoc.script_reader import parse_script_blocks, detect_language
            blocks = parse_script_blocks(script_path)
            language = detect_language(script_path)
            loaded_scripts[script_id] = (blocks, language)

        # Create visitor for directive processing
        visitor = DirectiveVisitor(
            loaded_notebooks=loaded_notebooks,
            notebook_refs=parsed.notebook_refs,
            output_path=output_path,
            loaded_scripts=loaded_scripts,
            script_refs=parsed.script_refs,
            notebook_kinds=notebook_kinds,
        )

        # Generate output by replacing directives
        output_lines = []
        directives_by_line = {d.line_number: d for d in parsed.directives}

        for line_number, line in enumerate(parsed.body.split("\n"), start=parsed.body_start_line):
            if line_number in directives_by_line:
                directive = directives_by_line[line_number]
                replacement = directive.accept(visitor)
                output_lines.append(replacement)
            else:
                output_lines.append(line)

        output_content = "\n".join(output_lines)

        # Determine output path
        output_path = Path(output_path)

        # Skip writing if the body content hasn't changed
        if output_path.exists():
            existing = output_path.read_text(encoding="utf-8")
            existing_body = _strip_frontmatter(existing)
            if existing_body == output_content:
                return existing

        # Add frontmatter with source note and generation time
        # Try to make the path relative to cwd for nicer output, but fall back to absolute path
        try:
            if template_path.is_absolute():
                relative_template = template_path.relative_to(Path.cwd())
            else:
                relative_template = template_path
        except ValueError:
            # Path is not relative to cwd (e.g., in temp directory), use as-is
            relative_template = template_path

        from datetime import datetime
        generated_at = datetime.now().isoformat()

        frontmatter = f"""---
note: This file is generated from {relative_template}. Don't change this file.
generated_at: {generated_at}
---

"""
        output_content = frontmatter + output_content

        # Write to output file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(output_content, encoding="utf-8")

        return output_content

    def _derive_output_path(self, template_path: Path) -> Path:
        """Derive output path from template path."""
        stem = template_path.stem  # e.g., "file.template" from "file.template.md"
        # Remove .template suffix if present
        if stem.endswith(".template"):
            stem = stem[:-9]  # Remove ".template"
        return template_path.parent / f"{stem}.md"


def generate_template(
    template_path: Path,
    output_path: Path | None = None,
    timeout: int = 30,
    kernel_name: str = "python3",
) -> str:
    """
    Convenience function to generate a single template.

    Args:
        template_path: Path to the .template.md file
        output_path: Optional output path
        timeout: Timeout for notebook execution
        kernel_name: Jupyter kernel to use

    Returns:
        The generated markdown content
    """
    generator = Generator(timeout=timeout, kernel_name=kernel_name)
    return generator.generate(template_path, output_path)


def generate_directory(
    directory: Path,
    timeout: int = 30,
    kernel_name: str = "python3",
) -> list[Path]:
    """
    Generate all template files in a directory.

    Args:
        directory: Root directory to search for templates
        timeout: Timeout for notebook execution
        kernel_name: Jupyter kernel to use

    Returns:
        List of generated file paths
    """
    from codoc.utils import find_template_files

    generator = Generator(timeout=timeout, kernel_name=kernel_name)

    template_files = find_template_files(directory)
    generated_paths = []

    for template_path in template_files:
        output_path = generator._derive_output_path(template_path)
        generator.generate(template_path, output_path)
        generated_paths.append(output_path)

    return generated_paths
