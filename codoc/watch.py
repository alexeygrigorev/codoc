"""Watch *.template.md files and referenced notebooks, trigger codoc on changes."""

import argparse
import sys
import threading
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from codoc.generator import generate_template
from codoc.parser import parse_template
from codoc.utils import resolve_notebook_path, set_terminal_title


ORIGINAL_TITLE = None


def get_original_title() -> str | None:
    """Get the current terminal title before we change it."""
    # This is platform-dependent and not always possible
    # We'll just return None and use a default restore
    return None


def set_title(title: str) -> None:
    """Set terminal title."""
    set_terminal_title(title)


def build_notebook_to_templates_map(root: Path) -> dict[Path, list[Path]]:
    """
    Build a mapping of source file paths (notebooks and scripts) to templates that reference them.

    Returns:
        dict mapping source_path -> list of template_paths that reference it
    """
    notebook_to_templates: dict[Path, list[Path]] = {}

    for template_path in root.rglob("*.template.md"):
        try:
            parsed = parse_template(template_path)
            for notebook_ref in parsed.notebook_refs.values():
                notebook_path = resolve_notebook_path(template_path, notebook_ref.path)
                # Resolve to absolute path for consistent matching
                notebook_path = notebook_path.resolve()
                if notebook_path not in notebook_to_templates:
                    notebook_to_templates[notebook_path] = []
                notebook_to_templates[notebook_path].append(template_path)

            for script_ref in parsed.script_refs.values():
                script_path = (template_path.parent / script_ref.path).resolve()
                if script_path not in notebook_to_templates:
                    notebook_to_templates[script_path] = []
                notebook_to_templates[script_path].append(template_path)
        except Exception:
            # Skip templates that can't be parsed
            continue

    return notebook_to_templates


class TemplateChangeHandler(FileSystemEventHandler):
    """Handle file change events for template and notebook files with debouncing."""

    def __init__(
        self,
        grace_period: float = 1.5,
        verbose: bool = False,
        timeout: int = 30,
        kernel_name: str = "python3",
        notebook_to_templates: dict[Path, list[Path]] | None = None,
    ):
        """
        Initialize the handler.

        Args:
            grace_period: Seconds to wait after last change before triggering (default: 1.5)
            verbose: Print verbose output
            timeout: Timeout for notebook execution during generation
            kernel_name: Jupyter kernel name to use for execution
            notebook_to_templates: Mapping of notebook paths to templates that reference them
        """
        self.grace_period = grace_period
        self.verbose = verbose
        self.timeout = timeout
        self.kernel_name = kernel_name
        self.pending_files: dict[Path, float] = {}
        self.timers: dict[Path, threading.Timer] = {}
        self.lock = threading.Lock()
        self.cwd = Path.cwd()
        self.notebook_to_templates = notebook_to_templates or {}
        self._seen_files: set[Path] = set()  # Track files we've seen to avoid spam

    def on_any_event(self, event):
        """Catch all events for debugging when verbose is enabled."""
        if event.is_directory:
            return

        if self.verbose:
            path = Path(event.src_path)
            print(f"[DEBUG] Event: {event.event_type}, path: {path}", flush=True)

    def on_modified(self, event):
        """Handle file modification events for templates and notebooks."""
        if event.is_directory:
            return

        path = Path(event.src_path).resolve()

        if self.verbose:
            print(f"[DEBUG] File modified: {path}", flush=True)
            print(f"[DEBUG]   suffix: {path.suffix!r}", flush=True)

        # Handle template files
        if path.suffix == ".md" and ".template." in path.name:
            # Update notebook-to-templates mapping in case dependencies changed
            self._update_notebook_mapping(path)
            self._schedule_codegen(path)
            return

        # Handle notebook files
        if path.suffix == ".ipynb":
            self._schedule_notebook_regenerate(path)
            return

        # Handle Python script files
        if path.suffix == ".py":
            self._schedule_notebook_regenerate(path)
            return

    def on_created(self, event):
        """Handle file created events (for new templates and notebooks)."""
        if event.is_directory:
            return

        path = Path(event.src_path).resolve()

        if self.verbose:
            print(f"[DEBUG] File created: {path}", flush=True)

        # Handle new template files
        if path.suffix == ".md" and ".template." in path.name:
            try:
                rel_path = path.relative_to(self.cwd)
            except ValueError:
                rel_path = path
            print(f"New template detected: {rel_path}", flush=True)
            self._schedule_codegen(path)
            # Update the notebook-to-templates mapping
            self._update_notebook_mapping(path)
            return

        # Handle new notebook files
        if path.suffix == ".ipynb":
            # Rebuild the mapping to catch any templates that reference this new notebook
            self._rebuild_notebook_mapping()
            self._schedule_notebook_regenerate(path)
            return

    def _rebuild_notebook_mapping(self):
        """Rebuild the notebook-to-templates mapping to handle new files."""
        try:
            old_mapping = self.notebook_to_templates.copy()
            self.notebook_to_templates.clear()
            self.notebook_to_templates.update(build_notebook_to_templates_map(self.cwd))
            if self.verbose:
                new_count = len(self.notebook_to_templates)
                old_count = len(old_mapping)
                if new_count != old_count:
                    print(f"[DEBUG] Rebuilt mapping: {old_count} -> {new_count} notebooks", flush=True)
        except Exception as e:
            if self.verbose:
                print(f"[DEBUG] Failed to rebuild mapping: {e}", flush=True)

    def _update_notebook_mapping(self, template_path: Path):
        """
        Update the notebook-to-templates mapping for a new or modified template.

        For a modified template, this removes old references and adds new ones,
        correctly handling the case where the template's notebook dependencies changed.
        """
        # First, remove this template from all notebook references
        for nb_path in list(self.notebook_to_templates.keys()):
            if template_path in self.notebook_to_templates[nb_path]:
                self.notebook_to_templates[nb_path].remove(template_path)
                # Clean up empty lists
                if not self.notebook_to_templates[nb_path]:
                    del self.notebook_to_templates[nb_path]

        # Then add the current template's notebook and script references
        try:
            parsed = parse_template(template_path)
            for notebook_ref in parsed.notebook_refs.values():
                notebook_path = resolve_notebook_path(template_path, notebook_ref.path)
                notebook_path = notebook_path.resolve()
                if notebook_path not in self.notebook_to_templates:
                    self.notebook_to_templates[notebook_path] = []
                if template_path not in self.notebook_to_templates[notebook_path]:
                    self.notebook_to_templates[notebook_path].append(template_path)

            for script_ref in parsed.script_refs.values():
                script_path = (template_path.parent / script_ref.path).resolve()
                if script_path not in self.notebook_to_templates:
                    self.notebook_to_templates[script_path] = []
                if template_path not in self.notebook_to_templates[script_path]:
                    self.notebook_to_templates[script_path].append(template_path)
        except Exception:
            pass

    def _schedule_notebook_regenerate(self, notebook_path: Path):
        """Schedule regeneration of all templates that reference this notebook."""
        # Look up the resolved path in our mapping
        notebook_path = notebook_path.resolve()

        if notebook_path not in self.notebook_to_templates:
            if self.verbose:
                print(f"[DEBUG] Notebook not referenced by any templates: {notebook_path}", flush=True)
            return

        templates = self.notebook_to_templates[notebook_path]

        try:
            rel_nb = notebook_path.relative_to(self.cwd)
        except ValueError:
            rel_nb = notebook_path

        print(f"Change detected in notebook: {rel_nb}, updating {len(templates)} template(s)...", flush=True)

        # Schedule regeneration for each template
        for template_path in templates:
            self._schedule_codegen(template_path)

    def _schedule_codegen(self, path: Path):
        """Schedule codoc for a file after the grace period."""
        with self.lock:
            # Cancel existing timer if file is already pending
            if path in self.timers:
                self.timers[path].cancel()

            # Schedule new timer
            timer = threading.Timer(
                self.grace_period,
                self._run_codegen,
                args=[path]
            )
            self.timers[path] = timer
            timer.start()

        try:
            rel_path = path.relative_to(self.cwd)
        except ValueError:
            rel_path = path

        print(f"Change detected: {rel_path} (waiting {self.grace_period}s for more changes...)", flush=True)

    def _run_codegen(self, path: Path):
        """Run codoc for the given file."""
        with self.lock:
            # Clean up timer
            if path in self.timers:
                del self.timers[path]
            if path in self.pending_files:
                del self.pending_files[path]

        self._generate_now(path)

    def _generate_now(self, path: Path):
        """Generate a template file immediately (no debouncing)."""
        try:
            output_path = path.parent / path.name.replace(".template.md", ".md")

            try:
                rel_path = path.relative_to(self.cwd)
            except ValueError:
                rel_path = path
            try:
                rel_output = output_path.relative_to(self.cwd)
            except ValueError:
                rel_output = output_path

            # Update terminal title with current file
            set_title(f"codoc: {path.name}")

            if self.verbose:
                print(f"Generating: {rel_path}", flush=True)

            # Check mtime before to detect if file was actually written
            old_mtime = output_path.stat().st_mtime if output_path.exists() else None

            generate_template(
                template_path=path,
                timeout=self.timeout,
                kernel_name=self.kernel_name,
            )

            new_mtime = output_path.stat().st_mtime if output_path.exists() else None
            if old_mtime is not None and old_mtime == new_mtime:
                if self.verbose:
                    print(f"Skipped (unchanged): {rel_output}", flush=True)
            else:
                print(f"Generated: {rel_output}", flush=True)

            # Reset to watching state
            set_title("codoc: watching")

        except Exception as e:
            print(f"Error generating {path.name}: {e}", file=sys.stderr, flush=True)
            # Reset to watching state even on error
            set_title("codoc: watching")
            if self.verbose:
                import traceback
                traceback.print_exc()

    def wait(self):
        """Wait for all pending tasks to complete."""
        with self.lock:
            while self.timers:
                timer = next(iter(self.timers.values()))
                timer.join()
                if timer in self.timers:
                    del self.timers[timer]


def find_template_files(root: Path) -> list[Path]:
    """Find all *.template.md files in the given directory."""
    return list(root.rglob("*.template.md"))


def find_stale_templates(root: Path, handler: 'TemplateChangeHandler') -> list[Path]:
    """Find templates that don't have a corresponding output file or are newer than the output."""
    stale = []
    for template_path in find_template_files(root):
        output_path = template_path.parent / template_path.name.replace(".template.md", ".md")
        if not output_path.exists():
            stale.append(template_path)
        elif template_path.stat().st_mtime > output_path.stat().st_mtime:
            stale.append(template_path)
    return stale


def main():
    """Main entry point for codoc-watch."""
    parser = argparse.ArgumentParser(
        description="Watch *.template.md files and referenced notebooks, trigger codoc on changes",
        prog="codoc-watch",
    )

    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=Path("."),
        help="Path to watch (default: current directory)",
    )

    parser.add_argument(
        "-g",
        "--grace-period",
        type=float,
        default=1.5,
        help="Seconds to wait after last change before triggering (default: 1.5)",
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
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    args = parser.parse_args()

    watch_path = args.path.resolve()

    if not watch_path.exists():
        print(f"Error: Path not found: {watch_path}", file=sys.stderr, flush=True)
        sys.exit(1)

    # List existing template files
    templates = find_template_files(watch_path)
    print(f"Watching {len(templates)} template file(s) in: {watch_path}", flush=True)
    for t in templates:
        try:
            print(f"  {t.relative_to(watch_path)}", flush=True)
        except ValueError:
            print(f"  {t}", flush=True)
    print(flush=True)

    # Build notebook-to-templates mapping
    notebook_to_templates = build_notebook_to_templates_map(watch_path)
    print(f"Watching {len(notebook_to_templates)} notebook(s) referenced by templates:", flush=True)
    for notebook_path in sorted(notebook_to_templates.keys()):
        try:
            rel_nb = notebook_path.relative_to(watch_path)
        except ValueError:
            rel_nb = notebook_path
        try:
            templates_for_nb = [t.relative_to(watch_path) for t in notebook_to_templates[notebook_path]]
        except ValueError:
            templates_for_nb = notebook_to_templates[notebook_path]
        print(f"  {rel_nb} -> {len(templates_for_nb)} template(s)", flush=True)
        for t in templates_for_nb:
            print(f"    - {t}", flush=True)
    print(flush=True)

    # Create handler with notebook mapping
    event_handler = TemplateChangeHandler(
        grace_period=args.grace_period,
        verbose=args.verbose,
        timeout=args.timeout,
        kernel_name=args.kernel,
        notebook_to_templates=notebook_to_templates,
    )

    # Generate templates that don't have an output file yet or are newer than the output
    stale_templates = find_stale_templates(watch_path, event_handler)
    if stale_templates:
        print(f"Generating {len(stale_templates)} out-of-date template file(s):", flush=True)
        for template_path in stale_templates:
            event_handler._generate_now(template_path)
        print(flush=True)

    # Start observer

    observer = Observer()
    observer.schedule(event_handler, str(watch_path), recursive=True)
    observer.start()

    # Set terminal title
    set_title("codoc: watching")

    try:
        print("Press Ctrl+C to stop", flush=True)
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...", flush=True)
        observer.stop()
        event_handler.wait()
        # Restore terminal title
        set_title("codoc: stopped")
    finally:
        # Always restore title on exit
        set_title("Terminal")


if __name__ == "__main__":
    main()
