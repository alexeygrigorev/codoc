/**
 * Read script files and extract blocks by @block / @end markers.
 *
 * Ported from codegen/codegen/script_reader.py.
 */

import * as fs from 'fs';
import type { BlockInfo } from './types';

/** Regex matching # @block=block-id */
const BLOCK_START = /^#\s*@block\s*=\s*(\S+)\s*$/;

/** Regex matching # @end */
const BLOCK_END = /^#\s*@end\s*$/;

/**
 * Read a script file and return a map of block_id -> BlockInfo.
 *
 * Throws on unclosed blocks, duplicate IDs, or nested blocks.
 */
export function readScriptBlocks(filePath: string): Map<string, BlockInfo> {
  const content = fs.readFileSync(filePath, 'utf-8').replace(/\r\n/g, '\n');
  return parseScriptBlocks(content, filePath);
}

/**
 * Parse script content for block markers. Operates on the text directly.
 *
 * @param content - The full script file content.
 * @param fileName - Used in error messages.
 */
export function parseScriptBlocks(content: string, fileName = '<unknown>'): Map<string, BlockInfo> {
  const lines = content.split('\n');
  const blocks = new Map<string, BlockInfo>();

  let currentId: string | null = null;
  let currentStart = 0;
  let currentLines: string[] = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const trimmed = line.trim();
    const lineNum = i + 1; // 1-based

    const startMatch = BLOCK_START.exec(trimmed);
    const endMatch = BLOCK_END.exec(trimmed);

    if (startMatch) {
      if (currentId !== null) {
        throw new Error(
          `${fileName}: Nested block '${startMatch[1]}' found inside block '${currentId}' at line ${lineNum}`
        );
      }

      const blockId = startMatch[1];
      if (blocks.has(blockId)) {
        throw new Error(`${fileName}: Duplicate block ID '${blockId}' at line ${lineNum}`);
      }

      currentId = blockId;
      currentStart = lineNum;
      currentLines = [];
    } else if (endMatch) {
      if (currentId === null) {
        throw new Error(`${fileName}: Found # @end without matching # @block at line ${lineNum}`);
      }

      const source = currentLines.join('\n').trim();
      blocks.set(currentId, {
        id: currentId,
        source,
        startLine: currentStart,
        endLine: lineNum,
      });

      currentId = null;
      currentLines = [];
    } else if (currentId !== null) {
      currentLines.push(line);
    }
  }

  if (currentId !== null) {
    throw new Error(
      `${fileName}: Unclosed block '${currentId}' starting at line ${currentStart}`
    );
  }

  return blocks;
}
