"""Parse template files for frontmatter and code generation directives."""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

import frontmatter

from codoc.errors import ParseError


@dataclass
class NotebookRef:
    """Reference to a notebook from frontmatter."""

    id: str
    path: str
    execute: bool = True  # Whether to execute this notebook during validation
    image_folder: str | None = None  # Folder to save extracted images (relative to output)


@dataclass
class ScriptRef:
    """Reference to a script file from frontmatter."""

    id: str
    path: str


class Directive(ABC):
    """Abstract base class for code generation directives found in templates."""

    notebook_id: str
    cell_id: str
    line_number: int
    raw_line: str
    type: str  # Set by subclasses

    def __init__(
        self,
        notebook_id: str,
        cell_id: str,
        line_number: int,
        raw_line: str,
    ):
        self.notebook_id = notebook_id
        self.cell_id = cell_id
        self.line_number = line_number
        self.raw_line = raw_line

    @abstractmethod
    def accept(self, visitor) -> str:
        """Accept a visitor and return the result."""
        pass


class CodeDirective(Directive):
    """Directive for @@code - inserts code from a notebook cell.

    Args:
        notebook_id: The notebook identifier
        cell_id: The cell identifier
        line_number: Line number in the template
        raw_line: The original raw line
        lines: Optional (from, to) 1-based inclusive line range to extract
        strip_spaces: Optional number of leading spaces to remove from each line
    """

    def __init__(
        self,
        notebook_id: str,
        cell_id: str,
        line_number: int,
        raw_line: str,
        lines: tuple[int, int] | None = None,
        strip_spaces: int | None = None,
    ):
        super().__init__(notebook_id, cell_id, line_number, raw_line)
        self.type = "code"
        self.lines = lines
        self.strip_spaces = strip_spaces

    def accept(self, visitor) -> str:
        return visitor.visit_code(self)


class CodeOutputDirective(Directive):
    """Directive for @@code-output - inserts output from a notebook cell.

    Args:
        notebook_id: The notebook identifier
        cell_id: The cell identifier
        line_number: Line number in the template
        raw_line: The original raw line
        limit_lines: Optional max lines to include from output
        limit_chars: Optional max characters to include from output
    """

    def __init__(
        self,
        notebook_id: str,
        cell_id: str,
        line_number: int,
        raw_line: str,
        limit_lines: int | None = None,
        limit_chars: int | None = None,
    ):
        super().__init__(notebook_id, cell_id, line_number, raw_line)
        self.type = "code-output"
        self.limit_lines = limit_lines
        self.limit_chars = limit_chars

    def accept(self, visitor) -> str:
        return visitor.visit_code_output(self)


class CodeFigureDirective(Directive):
    """Directive for @@code-figure - extracts and embeds an image from cell output.

    Args:
        notebook_id: The notebook identifier
        cell_id: The cell identifier
        line_number: Line number in the template
        raw_line: The original raw line
        format: Image format - "jpg" or "png" (default: "jpg")
        quality: JPEG quality 1-100 (default: 85, only used for jpg)
    """

    def __init__(
        self,
        notebook_id: str,
        cell_id: str,
        line_number: int,
        raw_line: str,
        format: str = "jpg",
        quality: int = 85,
    ):
        super().__init__(notebook_id, cell_id, line_number, raw_line)
        self.type = "code-figure"
        self.format = format
        self.quality = quality

    def accept(self, visitor) -> str:
        return visitor.visit_code_figure(self)


@dataclass
class ParsedTemplate:
    """Result of parsing a template file."""

    content: str  # Full content including frontmatter
    frontmatter: dict
    body: str  # Content after frontmatter is removed
    body_start_line: int  # Line number where body starts (1-indexed)
    directives: list[Directive]
    notebook_refs: dict[str, NotebookRef]  # id -> NotebookRef
    script_refs: dict[str, ScriptRef] = None  # id -> ScriptRef

    def __post_init__(self):
        if self.script_refs is None:
            self.script_refs = {}


# Pattern to match @@code, @@code-output, or @@code-figure directives
# Optional parameters:
#   - code-output: limit-lines=N, limit-chars=N
#   - code-figure: format=jpg|png, quality=N (1-100)
DIRECTIVE_PATTERN = re.compile(
    r"^@@(code|code-output|code-figure)\s+(\S+):(\S+)"
    r"(?:\s+(limit-lines|limit-chars|format|quality|lines|strip-spaces)=([^\s]+))?"
    r"(?:\s+(limit-lines|limit-chars|format|quality|lines|strip-spaces)=([^\s]+))?"
    r"(?:\s+(limit-lines|limit-chars|format|quality|lines|strip-spaces)=([^\s]+))?"
    r"(?:\s+(limit-lines|limit-chars|format|quality|lines|strip-spaces)=([^\s]+))?\s*$"
)


def parse_template(template_path: Path) -> ParsedTemplate:
    """
    Parse a template file to extract frontmatter and directives.

    Args:
        template_path: Path to the template file

    Returns:
        ParsedTemplate with all extracted information

    Raises:
        ParseError: If the file cannot be parsed
    """
    try:
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        raise ParseError(str(template_path), "File not found")
    except OSError as e:
        raise ParseError(str(template_path), f"Failed to read file: {e}")

    # Parse frontmatter
    try:
        post = frontmatter.loads(content)
    except Exception as e:
        raise ParseError(str(template_path), f"Invalid frontmatter: {e}")

    frontmatter_data = post.metadata
    body = post.content

    # Find where body starts (after frontmatter)
    frontmatter_lines = len(content) - len(content.lstrip())
    if frontmatter_lines == 0 and content.startswith("---"):
        # Count lines until the second ---
        lines = content.split("\n")
        body_start_line = 0
        found_end = False
        for i, line in enumerate(lines):
            if i > 0 and line.strip() == "---":
                body_start_line = i + 1
                found_end = True
                break
        if not found_end:
            body_start_line = 0
    else:
        body_start_line = frontmatter_data.get("body_start", 0)

    # Parse notebook references from frontmatter
    notebook_refs = _parse_notebook_refs(frontmatter_data, template_path)

    # Parse script references from frontmatter
    script_refs = _parse_script_refs(frontmatter_data, template_path)

    # Validate no ID collision between notebooks and scripts
    collisions = set(notebook_refs.keys()) & set(script_refs.keys())
    if collisions:
        raise ParseError(
            str(template_path),
            f"ID collision between notebooks and scripts: {', '.join(sorted(collisions))}",
        )

    # Find all directives in the body
    directives = _find_directives(body, start_line=body_start_line)

    return ParsedTemplate(
        content=content,
        frontmatter=frontmatter_data,
        body=body,
        body_start_line=body_start_line,
        directives=directives,
        notebook_refs=notebook_refs,
        script_refs=script_refs,
    )


def _parse_notebook_refs(
    frontmatter_data: dict, template_path: Path
) -> dict[str, NotebookRef]:
    """Parse notebook references from frontmatter."""
    refs = {}

    notebooks_list = frontmatter_data.get("notebooks", [])
    if not isinstance(notebooks_list, list):
        raise ParseError(
            str(template_path), "'notebooks' in frontmatter must be a list"
        )

    for item in notebooks_list:
        if not isinstance(item, dict):
            raise ParseError(
                str(template_path), "Each notebook entry must be a dictionary"
            )

        notebook_id = item.get("id")
        path = item.get("path")
        execute = item.get("execute", True)  # Default to True
        image_folder = item.get("image_folder")  # Optional image folder

        if not isinstance(execute, bool):
            raise ParseError(
                str(template_path), f"Notebook '{notebook_id}' 'execute' must be a boolean"
            )

        if image_folder is not None and not isinstance(image_folder, str):
            raise ParseError(
                str(template_path), f"Notebook '{notebook_id}' 'image_folder' must be a string"
            )

        if not notebook_id:
            raise ParseError(str(template_path), "Notebook missing 'id' field")
        if not path:
            raise ParseError(str(template_path), f"Notebook '{notebook_id}' missing 'path'")

        refs[notebook_id] = NotebookRef(
            id=notebook_id, path=path, execute=execute, image_folder=image_folder
        )

    return refs


def _parse_script_refs(
    frontmatter_data: dict, template_path: Path
) -> dict[str, ScriptRef]:
    """Parse script references from frontmatter."""
    refs = {}

    scripts_list = frontmatter_data.get("scripts", [])
    if not isinstance(scripts_list, list):
        raise ParseError(
            str(template_path), "'scripts' in frontmatter must be a list"
        )

    for item in scripts_list:
        if not isinstance(item, dict):
            raise ParseError(
                str(template_path), "Each script entry must be a dictionary"
            )

        script_id = item.get("id")
        path = item.get("path")

        if not script_id:
            raise ParseError(str(template_path), "Script missing 'id' field")
        if not path:
            raise ParseError(str(template_path), f"Script '{script_id}' missing 'path'")

        refs[script_id] = ScriptRef(id=script_id, path=path)

    return refs


def _find_directives(body: str, start_line: int) -> list[Directive]:
    """Find all @@code, @@code-output, and @@code-figure directives in the body."""
    directives = []

    for line_number, line in enumerate(body.split("\n"), start=start_line):
        # Normalize whitespace: strip and collapse multiple spaces
        normalized = " ".join(line.strip().split())
        match = DIRECTIVE_PATTERN.match(normalized)
        if match:
            groups = match.groups()
            dir_type, notebook_id, cell_id = groups[0], groups[1], groups[2]

            # Parse optional parameters
            limit_lines = None
            limit_chars = None
            format = "jpg"  # default for code-figure
            quality = 85  # default for code-figure
            lines = None
            strip_spaces = None

            # Process up to 4 parameter pairs (groups[3]-groups[10])
            for i in range(4):
                param_idx = 3 + i * 2
                value_idx = 4 + i * 2
                if param_idx >= len(groups) or groups[param_idx] is None:
                    break

                param_name = groups[param_idx]
                param_value = groups[value_idx]

                if param_name == "limit-lines":
                    limit_lines = int(param_value)
                elif param_name == "limit-chars":
                    limit_chars = int(param_value)
                elif param_name == "format":
                    format = param_value
                elif param_name == "quality":
                    quality = int(param_value)
                elif param_name == "lines":
                    if "-" in param_value:
                        from_line, to_line = param_value.split("-", 1)
                        lines = (max(1, int(from_line)), int(to_line))
                    else:
                        line_val = max(1, int(param_value))
                        lines = (line_val, line_val)
                elif param_name == "strip-spaces":
                    strip_spaces = int(param_value)

            # Create the appropriate directive subclass
            if dir_type == "code-output":
                directive = CodeOutputDirective(
                    notebook_id=notebook_id,
                    cell_id=cell_id,
                    line_number=line_number,
                    raw_line=line,
                    limit_lines=limit_lines,
                    limit_chars=limit_chars,
                )
            elif dir_type == "code-figure":
                directive = CodeFigureDirective(
                    notebook_id=notebook_id,
                    cell_id=cell_id,
                    line_number=line_number,
                    raw_line=line,
                    format=format,
                    quality=quality,
                )
            else:  # "code"
                directive = CodeDirective(
                    notebook_id=notebook_id,
                    cell_id=cell_id,
                    line_number=line_number,
                    raw_line=line,
                    lines=lines,
                    strip_spaces=strip_spaces,
                )

            directives.append(directive)

    return directives
