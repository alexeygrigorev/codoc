"""Generate markdown documents from notebook-backed templates."""

from codoc.__version__ import __version__
from codoc.generator import Generator, generate_directory, generate_template
from codoc.parser import Directive, NotebookRef, ParsedTemplate, ScriptRef, parse_template

__all__ = [
    "__version__",
    "Generator",
    "generate_directory",
    "generate_template",
    "parse_template",
    "ParsedTemplate",
    "Directive",
    "NotebookRef",
    "ScriptRef",
]


def main():
    """Entry point for the codoc CLI."""
    from codoc.cli import run

    run()
