"""CLI entry point for the notebook editor."""

import warnings

# Suppress warning when module is run as script after being imported
warnings.simplefilter("ignore", RuntimeWarning)

from codoc.nb_edit.cli import run_cli  # noqa: E402


if __name__ == "__main__":
    run_cli()


def main():
    """Entry point for nbedit command."""
    run_cli()
