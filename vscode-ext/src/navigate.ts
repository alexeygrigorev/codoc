import type { BlockInfo } from './types';

/**
 * Compute the 0-based line number to navigate to in a script file.
 *
 * - block.startLine is the 1-based line of `# @block=`. Content starts on the
 *   next line, so the first content line is startLine (0-based).
 * - With `lines=N-M`: offset by N-1 from content start → startLine + (N - 1).
 * - With `lines=N`: same as `lines=N-N`.
 * - No param or `lines=1`: no offset → startLine (0-based).
 */
export function computeNavigationLine(block: BlockInfo, linesParam?: string): number {
  // Content starts at startLine (0-based) = block.startLine + 1 - 1
  const contentStart = block.startLine; // 0-based first content line

  if (!linesParam) {
    return contentStart;
  }

  const parts = linesParam.split('-');
  const from = parseInt(parts[0], 10);

  if (isNaN(from) || from < 1) {
    return contentStart;
  }

  return contentStart + (from - 1);
}
