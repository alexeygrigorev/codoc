/**
 * Extension entry point.
 *
 * Registers the custom editor provider and commands.
 */

import * as vscode from 'vscode';
import { CodocEditorProvider } from './editorProvider';
import { generate, generateAll, disposeOutputChannel } from './generate';

export function activate(context: vscode.ExtensionContext): void {
  // Register the custom editor provider for .template.md files
  context.subscriptions.push(CodocEditorProvider.register(context));

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('codoc.generate', async () => {
      const editor = vscode.window.activeTextEditor;
      if (!editor) {
        vscode.window.showWarningMessage('No active editor');
        return;
      }

      const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!workspaceRoot) {
        vscode.window.showWarningMessage('No workspace folder open');
        return;
      }

      const filePath = editor.document.uri.fsPath;
      if (!filePath.endsWith('.template.md')) {
        vscode.window.showWarningMessage('Current file is not a .template.md file');
        return;
      }

      try {
        vscode.window.setStatusBarMessage('Codoc: generating...', 10_000);
        await generate(filePath, workspaceRoot);
        vscode.window.setStatusBarMessage('Codoc: done', 3000);
      } catch (err) {
        vscode.window.showErrorMessage(`Codoc generation failed: ${err}`);
      }
    })
  );

  context.subscriptions.push(
    vscode.commands.registerCommand('codoc.generateAll', async () => {
      const workspaceRoot = vscode.workspace.workspaceFolders?.[0]?.uri.fsPath;
      if (!workspaceRoot) {
        vscode.window.showWarningMessage('No workspace folder open');
        return;
      }

      try {
        vscode.window.setStatusBarMessage('Codoc: generating all...', 30_000);
        await generateAll(workspaceRoot);
        vscode.window.setStatusBarMessage('Codoc: all done', 3000);
      } catch (err) {
        vscode.window.showErrorMessage(`Codoc generation failed: ${err}`);
      }
    })
  );
}

export function deactivate(): void {
  disposeOutputChannel();
}
