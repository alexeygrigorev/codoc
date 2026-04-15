/**
 * CustomTextEditorProvider for .template.md files.
 *
 * Uses VS Code's document model for undo/redo, dirty state, and save.
 * Webview hosts a Monaco editor with inline code previews.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import * as fs from 'fs';
import { parseTemplate } from './parser';
import { readNotebook } from './notebook';
import { hasNobookMarkers, readNobook, readNobookBlocks } from './nobook';
import { readScriptBlocks } from './script';
import { generate } from './generate';
import { replaceBlockSource, replaceCellSource, replaceNobookBlockSource } from './writeBack';
import { computeNavigationLine } from './navigate';
import type { CellInfo, BlockInfo, NearbyFiles, WebviewToExtensionMessage } from './types';

export class CodocEditorProvider implements vscode.CustomTextEditorProvider {
  public static readonly viewType = 'codoc.templateEditor';

  private static readonly webviewOptions: vscode.WebviewOptions = {
    enableScripts: true,
    localResourceRoots: [],
  };

  constructor(private readonly context: vscode.ExtensionContext) {}

  public static register(context: vscode.ExtensionContext): vscode.Disposable {
    const provider = new CodocEditorProvider(context);
    return vscode.window.registerCustomEditorProvider(
      CodocEditorProvider.viewType,
      provider,
      {
        webviewOptions: { retainContextWhenHidden: true },
      }
    );
  }

  public async resolveCustomTextEditor(
    document: vscode.TextDocument,
    webviewPanel: vscode.WebviewPanel,
    _token: vscode.CancellationToken
  ): Promise<void> {
    // Configure webview
    webviewPanel.webview.options = {
      enableScripts: true,
      localResourceRoots: [
        vscode.Uri.joinPath(this.context.extensionUri, 'dist'),
      ],
    };

    // Build webview HTML
    webviewPanel.webview.html = this.getWebviewHtml(webviewPanel.webview);

    // Track whether we're in the middle of pushing edits from the webview
    let isUpdatingFromWebview = false;

    // Load cell data from referenced notebooks and scripts
    const loadSourceData = () => {
      const content = document.getText();
      const parsed = parseTemplate(content);
      const templateDir = path.dirname(document.uri.fsPath);
      const cells: Record<string, Record<string, CellInfo>> = {};
      const blocks: Record<string, Record<string, BlockInfo>> = {};

      // Load notebooks
      for (const nbRef of parsed.frontmatter.notebooks) {
        const nbPath = path.resolve(templateDir, nbRef.path);
        try {
          const cellMap = nbPath.endsWith('.py') ? readNobook(nbPath) : readNotebook(nbPath);
          const cellRecord: Record<string, CellInfo> = {};
          cellMap.forEach((cell, id) => { cellRecord[id] = cell; });
          cells[nbRef.id] = cellRecord;
        } catch (err) {
          console.warn(`[codoc] Failed to read notebook source ${nbPath}: ${err}`);
          cells[nbRef.id] = {};
        }
      }

      // Load scripts
      for (const scRef of parsed.frontmatter.scripts) {
        const scPath = path.resolve(templateDir, scRef.path);
        console.log(`[codoc] Loading script: id=${scRef.id}, path=${scRef.path}, resolved=${scPath}, exists=${fs.existsSync(scPath)}`);
        try {
          const blockMap = readScriptBlocks(scPath);
          console.log(`[codoc] Script ${scRef.id}: found ${blockMap.size} blocks: ${[...blockMap.keys()].join(', ')}`);
          const blockRecord: Record<string, BlockInfo> = {};
          blockMap.forEach((block, id) => { blockRecord[id] = block; });
          blocks[scRef.id] = blockRecord;
        } catch (err) {
          console.warn(`[codoc] Failed to read script ${scPath}: ${err}`);
          blocks[scRef.id] = {};
        }
      }

      return { cells, blocks };
    };

    // Scan for .ipynb and .py files near the template (up 2 levels, down 2 levels)
    const scanNearbyFiles = (): NearbyFiles => {
      const templateDir = path.dirname(document.uri.fsPath);
      const notebooks: string[] = [];
      const scripts: string[] = [];

      const scanDir = (dir: string, depth: number) => {
        if (depth > 2) return;
        try {
          const entries = fs.readdirSync(dir, { withFileTypes: true });
          for (const entry of entries) {
            if (entry.name.startsWith('.') || entry.name === 'node_modules' || entry.name === '__pycache__') continue;
            const fullPath = path.join(dir, entry.name);
            if (entry.isDirectory()) {
              scanDir(fullPath, depth + 1);
            } else if (entry.name.endsWith('.ipynb')) {
              notebooks.push(path.relative(templateDir, fullPath).replace(/\\/g, '/'));
            } else if (entry.name.endsWith('.py')) {
              scripts.push(path.relative(templateDir, fullPath).replace(/\\/g, '/'));
              try {
                if (hasNobookMarkers(fs.readFileSync(fullPath, 'utf-8'))) {
                  notebooks.push(path.relative(templateDir, fullPath).replace(/\\/g, '/'));
                }
              } catch {
                // Ignore unreadable files
              }
            }
          }
        } catch { /* ignore permission errors */ }
      };

      // Scan from parent dir (so we get sibling folders too)
      const parentDir = path.dirname(templateDir);
      scanDir(parentDir, 0);

      return { notebooks, scripts };
    };

    // Send full content + cell data to webview
    const pushContentToWebview = () => {
      const { cells, blocks } = loadSourceData();
      const nearbyFiles = scanNearbyFiles();
      webviewPanel.webview.postMessage({
        type: 'loadContent',
        content: document.getText(),
        cells,
        blocks,
        nearbyFiles,
      });
    };

    // Listen for webview ready
    const messageDisposable = webviewPanel.webview.onDidReceiveMessage(
      async (msg: WebviewToExtensionMessage) => {
        switch (msg.type) {
          case 'ready':
            pushContentToWebview();
            break;

          case 'edit': {
            if (msg.content === document.getText()) return;
            isUpdatingFromWebview = true;
            const edit = new vscode.WorkspaceEdit();
            edit.replace(
              document.uri,
              new vscode.Range(0, 0, document.lineCount, 0),
              msg.content
            );
            await vscode.workspace.applyEdit(edit);
            isUpdatingFromWebview = false;
            break;
          }

          case 'save': {
            await document.save();
            break;
          }

          case 'navigate': {
            const templateDir = path.dirname(document.uri.fsPath);
            const content = document.getText();
            const parsed = parseTemplate(content);

            // Find the source file path (notebook or script)
            const nbRef = parsed.frontmatter.notebooks.find(n => n.id === msg.sourceId);
            const scRef = parsed.frontmatter.scripts.find(s => s.id === msg.sourceId);

            if (nbRef) {
              const nbPath = path.resolve(templateDir, nbRef.path);
              try {
                if (nbPath.endsWith('.py')) {
                  const blockMap = readNobookBlocks(nbPath);
                  const block = blockMap.get(msg.cellId);
                  const targetLine = block ? computeNavigationLine(block, msg.params?.['lines']) : 0;

                  const uri = vscode.Uri.file(nbPath);
                  const doc = await vscode.workspace.openTextDocument(uri);
                  const editor = await vscode.window.showTextDocument(doc, {
                    viewColumn: vscode.ViewColumn.Active,
                    preview: true,
                  });
                  const pos = new vscode.Position(targetLine, 0);
                  editor.selection = new vscode.Selection(pos, pos);
                  editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
                  break;
                }

                const uri = vscode.Uri.file(nbPath);
                // Open as Jupyter notebook (not raw JSON), reuse tab in same group
                await vscode.commands.executeCommand('vscode.openWith', uri, 'jupyter-notebook');

                // Find the REAL cell index by scanning all cells in the notebook
                const raw = JSON.parse(fs.readFileSync(nbPath, 'utf-8'));
                const allNbCells = Array.isArray(raw.cells) ? raw.cells : [];
                const cellIdPattern = `@cell_id=${msg.cellId}`;
                let realCellIndex = -1;
                for (let i = 0; i < allNbCells.length; i++) {
                  const src = allNbCells[i].source;
                  const firstLine = Array.isArray(src) ? (src[0] ?? '') : String(src).split('\n')[0];
                  if (firstLine.includes(cellIdPattern)) {
                    realCellIndex = i;
                    break;
                  }
                }

                if (realCellIndex >= 0) {
                  // Wait for notebook editor to be ready after openWith
                  const revealCell = () => {
                    const nbEditor = vscode.window.activeNotebookEditor;
                    if (nbEditor && nbEditor.notebook.uri.toString() === uri.toString()) {
                      const cellRange = new vscode.NotebookRange(realCellIndex, realCellIndex + 1);
                      nbEditor.revealRange(cellRange, vscode.NotebookEditorRevealType.InCenter);
                      nbEditor.selections = [cellRange];
                      return true;
                    }
                    return false;
                  };
                  // Try immediately, then retry after a short delay
                  if (!revealCell()) {
                    setTimeout(() => revealCell(), 500);
                  }
                }
              } catch (err) {
                vscode.window.showWarningMessage(`Could not open notebook source: ${err}`);
              }
            } else if (scRef) {
              const scPath = path.resolve(templateDir, scRef.path);
              try {
                const blockMap = readScriptBlocks(scPath);
                const block = blockMap.get(msg.cellId);
                const targetLine = block ? computeNavigationLine(block, msg.params?.['lines']) : 0;

                const uri = vscode.Uri.file(scPath);
                const doc = await vscode.workspace.openTextDocument(uri);
                // Open in same group, reuse preview tab
                const editor = await vscode.window.showTextDocument(doc, {
                  viewColumn: vscode.ViewColumn.Active,
                  preview: true,
                });
                const pos = new vscode.Position(targetLine, 0);
                editor.selection = new vscode.Selection(pos, pos);
                editor.revealRange(new vscode.Range(pos, pos), vscode.TextEditorRevealType.InCenter);
              } catch (err) {
                vscode.window.showWarningMessage(`Could not open script: ${err}`);
              }
            }
            break;
          }

          case 'editCell': {
            const templateDir = path.dirname(document.uri.fsPath);
            const content = document.getText();
            const parsed = parseTemplate(content);

            const nbRef = parsed.frontmatter.notebooks.find(n => n.id === msg.sourceId);
            const scRef = parsed.frontmatter.scripts.find(s => s.id === msg.sourceId);

            try {
              if (nbRef) {
                const nbPath = path.resolve(templateDir, nbRef.path);
                const nbContent = fs.readFileSync(nbPath, 'utf-8');
                const updated = nbPath.endsWith('.py')
                  ? replaceNobookBlockSource(nbContent, msg.cellId, msg.newSource)
                  : replaceCellSource(nbContent, msg.cellId, msg.newSource);
                isWritingCell = true;
                fs.writeFileSync(nbPath, updated, 'utf-8');
                setTimeout(() => { isWritingCell = false; }, 300);

                // Reload and push updated cells
                const cellMap = nbPath.endsWith('.py') ? readNobook(nbPath) : readNotebook(nbPath);
                const cellRecord: Record<string, CellInfo> = {};
                cellMap.forEach((cell, id) => { cellRecord[id] = cell; });
                webviewPanel.webview.postMessage({
                  type: 'updateCells',
                  sourceId: msg.sourceId,
                  cells: cellRecord,
                });
              } else if (scRef) {
                const scPath = path.resolve(templateDir, scRef.path);
                const scContent = fs.readFileSync(scPath, 'utf-8');
                const updated = replaceBlockSource(scContent, msg.cellId, msg.newSource);
                isWritingCell = true;
                fs.writeFileSync(scPath, updated, 'utf-8');
                setTimeout(() => { isWritingCell = false; }, 300);

                // Reload and push updated blocks
                const blockMap = readScriptBlocks(scPath);
                const blockRecord: Record<string, BlockInfo> = {};
                blockMap.forEach((block, id) => { blockRecord[id] = block; });
                webviewPanel.webview.postMessage({
                  type: 'updateBlocks',
                  sourceId: msg.sourceId,
                  blocks: blockRecord,
                });
              } else {
                console.warn(`[codoc] editCell: source '${msg.sourceId}' not found`);
              }
            } catch (err) {
              console.error(`[codoc] editCell failed:`, err);
              vscode.window.showErrorMessage(`Failed to write cell: ${err}`);
            }
            break;
          }

          case 'openFile': {
            const templateDir = path.dirname(document.uri.fsPath);
            const filePath = path.resolve(templateDir, msg.relativePath);
            try {
              const uri = vscode.Uri.file(filePath);
              if (filePath.endsWith('.ipynb')) {
                await vscode.commands.executeCommand('vscode.openWith', uri, 'jupyter-notebook');
              } else {
                const doc = await vscode.workspace.openTextDocument(uri);
                await vscode.window.showTextDocument(doc, { preview: true });
              }
            } catch (err) {
              vscode.window.showWarningMessage(`Could not open file: ${filePath}`);
            }
            break;
          }
        }
      }
    );

    // Flag to suppress file watcher during our own writes
    let isWritingCell = false;

    // Sync document changes -> webview (when document changes externally)
    const docChangeDisposable = vscode.workspace.onDidChangeTextDocument((e) => {
      if (e.document.uri.toString() === document.uri.toString() && !isUpdatingFromWebview) {
        webviewPanel.webview.postMessage({
          type: 'loadContent',
          content: document.getText(),
          ...loadSourceData(),
          nearbyFiles: scanNearbyFiles(),
        });
      }
    });

    // Watch referenced .ipynb and .py files for changes
    const fileWatchers: vscode.FileSystemWatcher[] = [];
    const setupFileWatchers = () => {
      // Dispose old watchers
      fileWatchers.forEach((w) => w.dispose());
      fileWatchers.length = 0;

      const content = document.getText();
      const parsed = parseTemplate(content);
      const templateDir = path.dirname(document.uri.fsPath);

      for (const nbRef of parsed.frontmatter.notebooks) {
        const nbPath = path.resolve(templateDir, nbRef.path);
        const pattern = new vscode.RelativePattern(path.dirname(nbPath), path.basename(nbPath));
        const watcher = vscode.workspace.createFileSystemWatcher(pattern);
        watcher.onDidChange(() => {
          if (isWritingCell) return; // Ignore our own writes
          try {
            const cellMap = nbPath.endsWith('.py') ? readNobook(nbPath) : readNotebook(nbPath);
            const cellRecord: Record<string, CellInfo> = {};
            cellMap.forEach((cell, id) => { cellRecord[id] = cell; });
            webviewPanel.webview.postMessage({
              type: 'updateCells',
              sourceId: nbRef.id,
              cells: cellRecord,
            });
          } catch (err) {
            console.warn(`[codoc] Failed to reload notebook source ${nbPath}: ${err}`);
          }
        });
        fileWatchers.push(watcher);
      }

      for (const scRef of parsed.frontmatter.scripts) {
        const scPath = path.resolve(templateDir, scRef.path);
        const pattern = new vscode.RelativePattern(path.dirname(scPath), path.basename(scPath));
        const watcher = vscode.workspace.createFileSystemWatcher(pattern);
        watcher.onDidChange(() => {
          if (isWritingCell) return; // Ignore our own writes
          try {
            const blockMap = readScriptBlocks(scPath);
            const blockRecord: Record<string, BlockInfo> = {};
            blockMap.forEach((block, id) => { blockRecord[id] = block; });
            webviewPanel.webview.postMessage({
              type: 'updateBlocks',
              sourceId: scRef.id,
              blocks: blockRecord,
            });
          } catch (err) {
            console.warn(`[codoc] Failed to reload script ${scPath}: ${err}`);
          }
        });
        fileWatchers.push(watcher);
      }
    };

    setupFileWatchers();

    // Also watch for saves within VS Code (more reliable than file system watchers)
    const templateDir = path.dirname(document.uri.fsPath);

    // Watch notebook saves (Jupyter editor uses NotebookDocument, not TextDocument)
    const nbSaveDisposable = vscode.workspace.onDidSaveNotebookDocument((nbDoc) => {
      const content = document.getText();
      const parsed = parseTemplate(content);
      for (const nbRef of parsed.frontmatter.notebooks) {
        const nbPath = path.resolve(templateDir, nbRef.path);
        if (nbPath.endsWith('.py')) {
          continue;
        }
        const nbUri = vscode.Uri.file(nbPath).toString();
        if (nbDoc.uri.toString() === nbUri) {
          console.log(`[codoc] Notebook saved, refreshing: ${nbRef.id}`);
          try {
            const cellMap = readNotebook(nbPath);
            const cellRecord: Record<string, CellInfo> = {};
            cellMap.forEach((cell, id) => { cellRecord[id] = cell; });
            webviewPanel.webview.postMessage({
              type: 'updateCells',
              sourceId: nbRef.id,
              cells: cellRecord,
            });
          } catch (err) {
            console.warn(`[codoc] Failed to reload notebook ${nbPath}: ${err}`);
          }
        }
      }
    });

    // Watch script saves
    const scriptSaveDisposable = vscode.workspace.onDidSaveTextDocument((savedDoc) => {
      const content = document.getText();
      const parsed = parseTemplate(content);
      for (const nbRef of parsed.frontmatter.notebooks) {
        const nbPath = path.resolve(templateDir, nbRef.path);
        if (!nbPath.endsWith('.py')) {
          continue;
        }
        const nbUri = vscode.Uri.file(nbPath).toString();
        if (savedDoc.uri.toString() === nbUri) {
          console.log(`[codoc] Nobook saved, refreshing: ${nbRef.id}`);
          try {
            const cellMap = readNobook(nbPath);
            const cellRecord: Record<string, CellInfo> = {};
            cellMap.forEach((cell, id) => { cellRecord[id] = cell; });
            webviewPanel.webview.postMessage({
              type: 'updateCells',
              sourceId: nbRef.id,
              cells: cellRecord,
            });
          } catch (err) {
            console.warn(`[codoc] Failed to reload nobook ${nbPath}: ${err}`);
          }
        }
      }
      for (const scRef of parsed.frontmatter.scripts) {
        const scPath = path.resolve(templateDir, scRef.path);
        const scUri = vscode.Uri.file(scPath).toString();
        if (savedDoc.uri.toString() === scUri) {
          console.log(`[codoc] Script saved, refreshing: ${scRef.id}`);
          try {
            const blockMap = readScriptBlocks(scPath);
            const blockRecord: Record<string, BlockInfo> = {};
            blockMap.forEach((block, id) => { blockRecord[id] = block; });
            webviewPanel.webview.postMessage({
              type: 'updateBlocks',
              sourceId: scRef.id,
              blocks: blockRecord,
            });
          } catch (err) {
            console.warn(`[codoc] Failed to reload script ${scPath}: ${err}`);
          }
        }
      }
    });

    // Clean up on dispose
    webviewPanel.onDidDispose(() => {
      messageDisposable.dispose();
      docChangeDisposable.dispose();
      nbSaveDisposable.dispose();
      scriptSaveDisposable.dispose();
      fileWatchers.forEach((w) => w.dispose());
    });
  }

  /**
   * Build the HTML for the webview.
   * Loads the bundled Monaco-based editor.
   */
  private getWebviewHtml(webview: vscode.Webview): string {
    const scriptUri = webview.asWebviewUri(
      vscode.Uri.joinPath(this.context.extensionUri, 'dist', 'webview.js')
    ) + `?v=${Date.now()}`;

    const nonce = getNonce();

    // Read VS Code editor font settings
    const editorConfig = vscode.workspace.getConfiguration('editor');
    const fontSize = editorConfig.get<number>('fontSize', 14);
    const fontFamily = editorConfig.get<string>('fontFamily', "Consolas, 'Courier New', monospace");

    return /* html */ `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta http-equiv="Content-Security-Policy"
        content="default-src 'none';
                 style-src ${webview.cspSource} 'unsafe-inline';
                 script-src 'nonce-${nonce}' ${webview.cspSource};
                 worker-src ${webview.cspSource} blob:;
                 font-src ${webview.cspSource} data:;
                 img-src ${webview.cspSource} data:;">
  <title>Codoc Template Editor</title>
  <style>
    html, body {
      margin: 0;
      padding: 0;
      width: 100%;
      height: 100%;
      overflow: hidden;
      background: var(--vscode-editor-background, #1e1e1e);
    }
    #editor-container {
      width: 100%;
      height: 100%;
    }
  </style>
</head>
<body data-font-size="${fontSize}" data-font-family="${fontFamily}">
  <div id="editor-container"></div>
  <script nonce="${nonce}" src="${scriptUri}"></script>
</body>
</html>`;
  }
}

function getNonce(): string {
  let text = '';
  const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
  for (let i = 0; i < 32; i++) {
    text += chars.charAt(Math.floor(Math.random() * chars.length));
  }
  return text;
}
