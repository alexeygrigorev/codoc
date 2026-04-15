/**
 * Read Jupyter .ipynb files and extract cells by @cell_id markers.
 *
 * Ported from codegen/codegen/nb_edit/editor.py (find_cells_by_id, _extract_outputs).
 */

import * as fs from 'fs';
import type { CellInfo, CellOutput } from './types';

/** Regex matching the first line of a cell: # @cell_id=some-id */
const CELL_ID_PATTERN = /^#\s*@cell_id\s*=\s*(\S+)\s*$/;

/** Regex matching additional attribute lines: # @key=value */
const ATTR_PATTERN = /^#\s*@(\w[\w-]*)\s*=\s*(.+?)\s*$/;

/**
 * Read a .ipynb file and return a map of cell_id -> CellInfo.
 * Cells without a @cell_id marker are skipped.
 */
export function readNotebook(filePath: string): Map<string, CellInfo> {
  const raw = fs.readFileSync(filePath, 'utf-8');
  const nb = JSON.parse(raw);
  return parseCells(nb);
}

/**
 * Parse cells from an already-loaded notebook object.
 */
export function parseCells(nb: Record<string, unknown>): Map<string, CellInfo> {
  const cells = nb['cells'];
  if (!Array.isArray(cells)) return new Map();

  const result = new Map<string, CellInfo>();

  for (const cell of cells) {
    if (cell['cell_type'] !== 'code') continue;

    const sourceLines = normalizeSource(cell['source']);
    if (sourceLines.length === 0) continue;

    // Check if the first line has a @cell_id marker
    const idMatch = CELL_ID_PATTERN.exec(sourceLines[0]);
    if (!idMatch) continue;

    const cellId = idMatch[1];

    // Extract additional attributes from subsequent comment lines
    const attributes: Record<string, string> = {};
    let contentStart = 1;

    for (let i = 1; i < sourceLines.length; i++) {
      const attrMatch = ATTR_PATTERN.exec(sourceLines[i]);
      if (attrMatch && attrMatch[1] !== 'cell_id') {
        attributes[attrMatch[1]] = attrMatch[2];
        contentStart = i + 1;
      } else {
        break;
      }
    }

    // Build source: strip the marker lines, trim leading/trailing blank lines
    const source = sourceLines.slice(contentStart).join('\n').replace(/^\n+|\n+$/g, '');

    // Extract outputs
    const output = extractOutputs(cell['outputs']);

    result.set(cellId, { id: cellId, source, output, attributes });
  }

  return result;
}

/**
 * Normalize the `source` field of a cell.
 * Jupyter stores source as either a string or an array of strings.
 */
function normalizeSource(source: unknown): string[] {
  if (typeof source === 'string') {
    return source.split('\n');
  }
  if (Array.isArray(source)) {
    // Each element may end with \n — join then re-split to normalize
    return source.join('').split('\n');
  }
  return [];
}

/**
 * Extract text outputs from a cell's output array.
 * Mirrors _extract_outputs from the Python backend.
 */
function extractOutputs(outputs: unknown): CellOutput[] {
  if (!Array.isArray(outputs)) return [];

  const result: CellOutput[] = [];

  for (const output of outputs) {
    if (typeof output !== 'object' || output === null) continue;
    const o = output as Record<string, unknown>;
    const outputType = String(o['output_type'] ?? '');

    if (outputType === 'stream') {
      const text = joinText(o['text']);
      result.push({ type: 'stream', text });
    } else if (outputType === 'execute_result') {
      const data = o['data'] as Record<string, unknown> | undefined;
      if (data && data['text/plain']) {
        result.push({ type: 'execute_result', text: joinText(data['text/plain']) });
      }
    } else if (outputType === 'error') {
      result.push({
        type: 'error',
        ename: String(o['ename'] ?? ''),
        evalue: String(o['evalue'] ?? ''),
        traceback: Array.isArray(o['traceback']) ? o['traceback'].map(String) : [],
      });
    } else if (o['data']) {
      const data = o['data'] as Record<string, unknown>;
      for (const mimeType of Object.keys(data)) {
        if (mimeType.startsWith('image/')) {
          result.push({ type: 'image', mimeType });
        }
      }
    }
  }

  return result;
}

/**
 * Join a Jupyter text field (string | string[]) into a single string.
 */
function joinText(text: unknown): string {
  if (typeof text === 'string') return text;
  if (Array.isArray(text)) return text.join('');
  return '';
}
