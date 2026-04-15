"""Command-line interface for the codoc tool."""

import argparse
import sys
from pathlib import Path

from codoc.errors import CodocError
from codoc.generator import generate_directory, generate_template


def run():
    """Run the codoc CLI."""
    parser = argparse.ArgumentParser(
        description="Generate markdown files from templates using Jupyter notebooks. "
        "Use 'codoc-watch' for automatic regeneration on file changes.",
        prog="codoc",
        epilog="Related commands: codoc-watch - watch for template changes and auto-regenerate",
    )

    parser.add_argument(
        "path",
        type=Path,
        help="Path to a template file or directory containing templates",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=30,
        help="Timeout in seconds for each cell during validation (default: 30)",
    )

    parser.add_argument(
        "--kernel",
        type=str,
        default="python3",
        help="Jupyter kernel name to use for validation (default: python3)",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output file path (only valid when processing a single template)",
    )

    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    try:
        if args.path.is_file():
            if args.path.suffix != ".md" or ".template." not in args.path.name:
                print(
                    f"Warning: {args.path.name} does not match expected pattern '*.template.md'",
                    file=sys.stderr,
                )

            if args.verbose:
                print(f"Generating: {args.path} -> {args.output or 'auto'}")

            result = generate_template(
                template_path=args.path,
                output_path=args.output,
                timeout=args.timeout,
                kernel_name=args.kernel,
            )

            if args.verbose:
                output_path = args.output or args.path.parent / args.path.name.replace(".template.md", ".md")
                print(f"Generated: {output_path}")

        elif args.path.is_dir():
            if args.output:
                print(
                    "Warning: --output is ignored when processing a directory",
                    file=sys.stderr,
                )

            generated = generate_directory(
                directory=args.path,
                timeout=args.timeout,
                kernel_name=args.kernel,
            )

            if args.verbose:
                print(f"Generated {len(generated)} file(s):")
                for path in generated:
                    print(f"  {path}")
        else:
            print(f"Error: Path not found: {args.path}", file=sys.stderr)
            sys.exit(1)

    except CodocError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    run()
