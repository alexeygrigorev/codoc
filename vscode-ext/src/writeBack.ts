/**
 * Write-back functions for updating cell/block source in notebooks and scripts.
 *
 * These operate on file content strings (not filesystem) so they're testable.
 */

/** Regex matching the first line of a cell: # @cell_id=some-id */
const CELL_ID_PATTERN = /^#\s*@cell_id\s*=\s*(\S+)\s*$/;

/** Regex matching additional attribute lines: # @key=value */
const ATTR_PATTERN = /^#\s*@(\w[\w-]*)\s*=\s*(.+?)\s*$/;

/**
 * Replace the source of a specific cell in a notebook JSON string.
 * Preserves the @cell_id marker line and any @attribute lines.
 * Returns the modified JSON string.
 */
export function replaceCellSource(nbContent: string, cellId: string, newSource: string): string {
  const nb = JSON.parse(nbContent);
  const cells = nb.cells;
  if (!Array.isArray(cells)) {
    throw new Error('Notebook has no cells array');
  }

  let found = false;

  for (const cell of cells) {
    if (cell.cell_type !== 'code') continue;

    const sourceLines = normalizeSource(cell.source);
    if (sourceLines.length === 0) continue;

    const idMatch = CELL_ID_PATTERN.exec(sourceLines[0]);
    if (!idMatch || idMatch[1] !== cellId) continue;

    found = true;

    // Collect marker + attribute lines to preserve
    const preserved: string[] = [sourceLines[0]];
    for (let i = 1; i < sourceLines.length; i++) {
      if (ATTR_PATTERN.test(sourceLines[i]) && !CELL_ID_PATTERN.test(sourceLines[i])) {
        preserved.push(sourceLines[i]);
      } else {
        break;
      }
    }

    // Build new source: preserved marker lines + new content
    const newLines = [...preserved, ...newSource.split('\n')];

    // Jupyter stores source as array of lines, each ending with \n (except last)
    cell.source = newLines.map((line: string, i: number) =>
      i < newLines.length - 1 ? line + '\n' : line
    );

    break;
  }

  if (!found) {
    throw new Error(`Cell '${cellId}' not found in notebook`);
  }

  return JSON.stringify(nb, null, 1);
}

/**
 * Replace the source of a specific block in a script file.
 * Content between # @block=id and # @end is replaced.
 * Returns the modified file content.
 */
export function replaceBlockSource(scriptContent: string, blockId: string, newSource: string): string {
  const lines = scriptContent.split('\n');
  const BLOCK_START = /^#\s*@block\s*=\s*(\S+)\s*$/;
  const BLOCK_END = /^#\s*@end\s*$/;

  const result: string[] = [];
  let inTargetBlock = false;
  let found = false;

  for (const line of lines) {
    const trimmed = line.trim();

    if (!inTargetBlock) {
      const startMatch = BLOCK_START.exec(trimmed);
      if (startMatch && startMatch[1] === blockId) {
        inTargetBlock = true;
        found = true;
        result.push(line); // Keep the @block= line
        // Insert the new source
        result.push(...newSource.split('\n'));
        continue;
      }
      result.push(line);
    } else {
      // Inside target block — skip old content until @end
      if (BLOCK_END.test(trimmed)) {
        inTargetBlock = false;
        result.push(line); // Keep the @end line
      }
      // Skip old content lines
    }
  }

  if (!found) {
    throw new Error(`Block '${blockId}' not found in script`);
  }

  return result.join('\n');
}

/**
 * Replace the source of a specific nobook block in a `.py` file.
 * Content between `# @block=id` and the next `# @block=` (or EOF) is replaced.
 */
export function replaceNobookBlockSource(fileContent: string, blockId: string, newSource: string): string {
  const lines = fileContent.split('\n');
  const BLOCK_START = /^#\s*@block\s*=\s*(\S+)\s*$/;

  const result: string[] = [];
  let found = false;
  let insideTarget = false;

  for (const line of lines) {
    const match = BLOCK_START.exec(line.trim());

    if (match) {
      if (insideTarget) {
        insideTarget = false;
      }

      if (match[1] === blockId) {
        found = true;
        insideTarget = true;
        result.push(line);
        result.push(...newSource.split('\n'));
        continue;
      }

      result.push(line);
      continue;
    }

    if (!insideTarget) {
      result.push(line);
    }
  }

  if (!found) {
    throw new Error(`Block '${blockId}' not found in nobook`);
  }

  return result.join('\n');
}

/** Normalize Jupyter source field (string | string[]) to string[]. */
function normalizeSource(source: unknown): string[] {
  if (typeof source === 'string') return source.split('\n');
  if (Array.isArray(source)) return source.join('').split('\n');
  return [];
}
