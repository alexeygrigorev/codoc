/**
 * Parse template files: extract YAML frontmatter and @@code directives.
 *
 * Ported from codegen/codegen/parser.py.
 */

import { parse as parseYaml } from 'yaml';
import type { Directive, Frontmatter, NotebookRef, ParsedTemplate, ScriptRef } from './types';

/**
 * Regex to match @@code, @@code-output, and @@code-figure directives.
 * Captures: type, sourceId, cellId, then up to 4 key=value params.
 */
const DIRECTIVE_PATTERN =
  /^@@(code|code-output|code-figure)\s+(\S+):(\S+)((?:\s+\S+=\S+)*)\s*$/;

/**
 * Parse a template string (including frontmatter).
 * Does NOT read from disk — the caller provides the content.
 */
export function parseTemplate(content: string): ParsedTemplate {
  const { frontmatter, body, bodyStartLine } = parseFrontmatter(content);
  const directives = findDirectives(body, bodyStartLine);

  return { content, frontmatter, body, bodyStartLine, directives };
}

/**
 * Extract YAML frontmatter delimited by `---` markers.
 */
export function parseFrontmatter(content: string): {
  frontmatter: Frontmatter;
  body: string;
  bodyStartLine: number;
} {
  // Normalize CRLF → LF before parsing (Windows line endings)
  const lines = content.replace(/\r\n/g, '\n').split('\n');

  // No frontmatter if the file doesn't start with ---
  if (lines[0]?.trim() !== '---') {
    return {
      frontmatter: { notebooks: [], scripts: [] },
      body: content,
      bodyStartLine: 0,
    };
  }

  // Find the closing ---
  let endIndex = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === '---') {
      endIndex = i;
      break;
    }
  }

  if (endIndex === -1) {
    // No closing --- found, treat entire content as body
    return {
      frontmatter: { notebooks: [], scripts: [] },
      body: content,
      bodyStartLine: 0,
    };
  }

  const yamlContent = lines.slice(1, endIndex).join('\n');
  const bodyStartLine = endIndex + 1;
  const body = lines.slice(bodyStartLine).join('\n');

  let raw: Record<string, unknown> = {};
  try {
    raw = (parseYaml(yamlContent) as Record<string, unknown>) ?? {};
  } catch {
    // Invalid YAML — treat as empty frontmatter
  }

  const notebooks = parseNotebookRefs(raw);
  const scripts = parseScriptRefs(raw);

  return { frontmatter: { notebooks, scripts }, body, bodyStartLine };
}

function parseNotebookRefs(raw: Record<string, unknown>): NotebookRef[] {
  const list = raw['notebooks'];
  if (!Array.isArray(list)) return [];

  return list
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      id: String(item['id'] ?? ''),
      path: String(item['path'] ?? ''),
      execute: item['execute'] !== false,
      ...(item['image_folder'] ? { image_folder: String(item['image_folder']) } : {}),
    }))
    .filter((ref) => ref.id && ref.path);
}

function parseScriptRefs(raw: Record<string, unknown>): ScriptRef[] {
  const list = raw['scripts'];
  if (!Array.isArray(list)) return [];

  return list
    .filter((item): item is Record<string, unknown> => typeof item === 'object' && item !== null)
    .map((item) => ({
      id: String(item['id'] ?? ''),
      path: String(item['path'] ?? ''),
    }))
    .filter((ref) => ref.id && ref.path);
}

/**
 * Find all directives in the template body.
 *
 * @param body - The template content after frontmatter.
 * @param startLine - The line offset for the body (0-based) in the full document.
 */
export function findDirectives(body: string, startLine: number): Directive[] {
  const directives: Directive[] = [];

  body.split('\n').forEach((rawLine, index) => {
    const normalized = rawLine.trim().replace(/\s+/g, ' ');
    const match = DIRECTIVE_PATTERN.exec(normalized);
    if (!match) return;

    const type = match[1] as Directive['type'];
    const sourceId = match[2];
    const cellId = match[3];
    const paramString = match[4] ?? '';
    const params = parseDirectiveParamString(paramString);

    directives.push({
      type,
      sourceId,
      cellId,
      lineNumber: startLine + index,
      rawLine,
      params,
    });
  });

  return directives;
}

/**
 * Parse a trailing param string like " lines=1-17 strip-spaces=4"
 * into { lines: "1-17", "strip-spaces": "4" }.
 */
export function parseDirectiveParamString(paramString: string): Record<string, string> {
  const params: Record<string, string> = {};
  if (!paramString) return params;

  const pairs = paramString.trim().match(/(\S+=\S+)/g);
  if (!pairs) return params;

  for (const pair of pairs) {
    const eq = pair.indexOf('=');
    params[pair.slice(0, eq)] = pair.slice(eq + 1);
  }

  return params;
}
