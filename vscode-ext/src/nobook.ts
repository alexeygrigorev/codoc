/**
 * Read nobook `.py` files and extract blocks as notebook-like cells.
 */

import * as fs from 'fs';
import * as path from 'path';
import type { BlockInfo, CellInfo, CellOutput } from './types';

const BLOCK_START = /^#\s*@block\s*=\s*(\S+)\s*$/;
const OUTPUT_PREFIX = '# >>>';
const ERROR_PREFIX = '# !!!';

export function hasNobookMarkers(content: string): boolean {
  return content.split('\n').some((line) => BLOCK_START.test(line.trim()));
}

export function readNobook(filePath: string): Map<string, CellInfo> {
  const content = fs.readFileSync(filePath, 'utf-8');
  const blocks = parseNobookBlocks(content);
  const outputs = readNobookOutputs(filePath);
  const result = new Map<string, CellInfo>();

  blocks.forEach((block, id) => {
    result.set(id, {
      id,
      source: block.source,
      output: outputs.get(id) ?? [],
      attributes: {},
    });
  });

  return result;
}

export function readNobookBlocks(filePath: string): Map<string, BlockInfo> {
  return parseNobookBlocks(fs.readFileSync(filePath, 'utf-8'));
}

export function parseNobookBlocks(content: string): Map<string, BlockInfo> {
  const lines = content.split('\n');
  const blocks = new Map<string, BlockInfo>();

  let currentId: string | null = null;
  let currentStart = 0;
  let currentLines: string[] = [];

  const flushBlock = (endLine: number) => {
    if (!currentId) return;
    if (blocks.has(currentId)) {
      throw new Error(`Duplicate block ID '${currentId}'`);
    }
    blocks.set(currentId, {
      id: currentId,
      source: currentLines.join('\n').replace(/^\n+|\n+$/g, ''),
      startLine: currentStart,
      endLine,
    });
  };

  lines.forEach((line, index) => {
    const match = BLOCK_START.exec(line.trim());
    if (match) {
      flushBlock(index);
      currentId = match[1];
      currentStart = index + 1;
      currentLines = [];
      return;
    }

    if (currentId) {
      currentLines.push(line);
    }
  });

  flushBlock(lines.length);
  return blocks;
}

function readNobookOutputs(filePath: string): Map<string, CellOutput[]> {
  const parsed = path.parse(filePath);
  const outPath = path.join(parsed.dir, `${parsed.name}.out${parsed.ext}`);
  if (!fs.existsSync(outPath)) {
    return new Map();
  }
  return parseNobookOutputs(fs.readFileSync(outPath, 'utf-8'));
}

function parseNobookOutputs(content: string): Map<string, CellOutput[]> {
  const result = new Map<string, CellOutput[]>();

  let currentId: string | null = null;
  let stdout: string[] = [];
  let stderr: string[] = [];

  const flush = () => {
    if (!currentId) {
      stdout = [];
      stderr = [];
      return;
    }

    const outputs: CellOutput[] = [];
    if (stdout.length > 0) {
      outputs.push({ type: 'stream', text: `${stdout.join('\n')}\n` });
    }
    if (stderr.length > 0) {
      outputs.push({
        type: 'error',
        ename: 'Error',
        evalue: stderr[stderr.length - 1] ?? '',
        traceback: stderr,
      });
    }
    if (outputs.length > 0) {
      result.set(currentId, outputs);
    }

    stdout = [];
    stderr = [];
  };

  for (const line of content.split('\n')) {
    const match = BLOCK_START.exec(line.trim());
    if (match) {
      flush();
      currentId = match[1];
      continue;
    }
    if (!currentId) continue;

    if (line === OUTPUT_PREFIX) continue;
    if (line.startsWith(`${OUTPUT_PREFIX} `)) {
      stdout.push(line.slice(`${OUTPUT_PREFIX} `.length));
      continue;
    }
    if (line.startsWith(`${ERROR_PREFIX} `)) {
      stderr.push(line.slice(`${ERROR_PREFIX} `.length));
    }
  }

  flush();
  return result;
}
