/**
 * Shell out to `uv run codoc` to generate markdown from templates.
 */

import * as vscode from 'vscode';
import * as path from 'path';
import { exec } from 'child_process';

let outputChannel: vscode.OutputChannel | undefined;

function getOutputChannel(): vscode.OutputChannel {
  if (!outputChannel) {
    outputChannel = vscode.window.createOutputChannel('Codoc');
  }
  return outputChannel;
}

/**
 * Run codoc for a single template file.
 *
 * @param templatePath - Absolute path to the .template.md file.
 * @param workspaceRoot - Absolute path to the workspace root where `uv run codoc` should execute.
 */
export async function generate(templatePath: string, workspaceRoot: string): Promise<void> {
  const command = vscode.workspace.getConfiguration('codoc').get<string>('pythonCommand', 'uv run codoc');
  const relativePath = path.relative(workspaceRoot, templatePath).replace(/\\/g, '/');

  const channel = getOutputChannel();
  channel.appendLine(`[codoc] Running: ${command} ${relativePath}`);
  channel.appendLine(`[codoc] Working directory: ${workspaceRoot}`);

  return new Promise<void>((resolve, reject) => {
    const child = exec(`${command} ${relativePath}`, { cwd: workspaceRoot }, (error, stdout, stderr) => {
      if (stdout) channel.appendLine(stdout);
      if (stderr) channel.appendLine(stderr);

      if (error) {
        channel.appendLine(`[codoc] ERROR: ${error.message}`);
        reject(error);
      } else {
        channel.appendLine('[codoc] Done.');
        resolve();
      }
    });

    // Safety: kill the process if it hangs
    setTimeout(() => {
      child.kill();
    }, 30_000);
  });
}

/**
 * Run codoc for all .template.md files found by scanning the workspace.
 */
export async function generateAll(workspaceRoot: string): Promise<void> {
  const command = vscode.workspace.getConfiguration('codoc').get<string>('pythonCommand', 'uv run codoc');

  const channel = getOutputChannel();
  channel.appendLine(`[codoc] Running: ${command} (all templates)`);

  return new Promise<void>((resolve, reject) => {
    const child = exec(command, { cwd: workspaceRoot }, (error, stdout, stderr) => {
      if (stdout) channel.appendLine(stdout);
      if (stderr) channel.appendLine(stderr);

      if (error) {
        channel.appendLine(`[codoc] ERROR: ${error.message}`);
        reject(error);
      } else {
        channel.appendLine('[codoc] Done (all).');
        resolve();
      }
    });

    setTimeout(() => {
      child.kill();
    }, 120_000);
  });
}

export function disposeOutputChannel(): void {
  outputChannel?.dispose();
  outputChannel = undefined;
}
