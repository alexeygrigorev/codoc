# Codoc Template Editor — VS Code Extension

Inline code previews for `@@code` directives in `.template.md` files.

Opens templates in a Monaco-based custom editor that shows resolved cell content
below each directive, with autocomplete and generate-on-save.

## Install in VS Code

Build and package the extension:

```bash
cd vscode-ext
npm install
npm run compile
npm run package
```

Install the generated VSIX from the command line:

```bash
code --install-extension codoc-vscode-*.vsix
```

Use a local `.vsix` file path here. If the package is hosted at an `https://` URL, download it first and then install the downloaded file.

Or in VS Code:

1. Open the Extensions view
2. Click `...` in the top-right of the Extensions panel
3. Choose `Install from VSIX...`
4. Select `vscode-ext/codoc-vscode-<version>.vsix`

After installation, open any `.template.md` file to use the custom editor.

If you're using VS Code Remote - SSH, connect to the SSH host first and then install the VSIX from that remote window:

1. Run `Remote-SSH: Connect to Host...`
2. Open the remote folder or workspace
3. Open the Extensions view in that remote window
4. Click `...` and choose `Install from VSIX...`
5. Select the generated `.vsix` and reload when prompted

That installs the extension on the SSH host for that window. Installing the VSIX only in your local VS Code window does not install it remotely.

If the VSIX is hosted on a web URL, download it first and then install that file from the remote window. The documented Remote-SSH path is file-based, not URL-based.

Because the extension shells out to `codoc`, make sure `codoc` or your configured `Codoc > Python Command` is available on the SSH host. If needed, set it in Remote Settings.

If `codoc` is not available on your `PATH`, set `Codoc > Python Command` to the command you use to run it, for example `uv run codoc`.

## Development

Install dependencies and build:

```bash
cd vscode-ext
npm install
npm run compile
```

Dev build (faster, with source maps):

```bash
npm run compile:dev
```

## Tests

Run all unit tests:

```bash
npm test
```

This runs vitest against `src/test/unit/`. The test suite covers:

- `parser.test.ts` — template parsing, frontmatter extraction, directive detection
- `notebook.test.ts` — reading `.ipynb` files, cell ID extraction, output parsing
- `script.test.ts` — reading `.py` files with `@block`/`@end` markers
- `params.test.ts` — directive params (`lines=`, `strip-spaces=`, `limit-lines=`, `limit-chars=`)
- `writeBack.test.ts` — replacing cell source in notebooks and block source in scripts

Watch mode (re-runs on file changes):

```bash
npm run test:watch
```

Type checking without emitting:

```bash
npm run lint
```

## Running the Extension

From the repository root:

1. Open the Run & Debug panel (Ctrl+Shift+D)
2. Select "Run Codoc Extension" from the dropdown
3. Press F5

This launches an Extension Development Host with the extension loaded.
Open any `.template.md` file in the new window to see the custom editor.

The launch configuration lives in `.vscode/launch.json` at the workspace root.

## Using the Editor

Each `@@code` directive shows an inline preview of the resolved cell content. The
preview header shows the directive type (CODE/OUTPUT/FIGURE) and source type (IPYNB/PY).

Ctrl+Click on any code preview widget to navigate to the source:
- Notebooks open in VS Code's Jupyter notebook editor, scrolled to the target cell
- Python scripts open in the text editor, scrolled to the target block


## Debugging the Webview

The webview runs inside a sandboxed iframe, so its logs don't appear in VS Code's
Debug Console. To see them:

1. In the **Extension Development Host** window (the second VS Code that opened on F5),
   open the Command Palette (`Ctrl+Shift+P`)
2. Run "Developer: Open Webview Developer Tools"
3. A Chrome DevTools window opens — go to the **Console** tab
4. Look for `[codegen-vs]` prefixed messages

The webview logs its build timestamp on startup, so you can verify you're running
the latest build. Example output:

```
[codegen-vs] Webview loaded, built: 2026-02-15 11:13:39
[codegen-vs] Font: Consolas, size: 14
[codegen-vs] Monaco editor created, language: markdown
[codegen-vs] loadContent: cells=["nb"], blocks=["sc"]
[codegen-vs] colorize: lang=python, text length=42
```

Extension host logs (file reading, navigation) appear in the Debug Console of the
**original** VS Code window where you pressed F5.

## Rebuilding After Changes

After editing source files:

```bash
cd vscode-ext
npm run compile:dev
```

Then in VS Code: Shift+F5 (stop) then F5 (restart) to reload the extension.
