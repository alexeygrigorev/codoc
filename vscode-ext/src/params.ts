/**
 * Parse and apply directive parameters (lines=, strip-spaces=, limit-lines=, limit-chars=).
 *
 * Ported from the frontend main.js (parseDirectiveParams / applyDirectiveParams).
 */

/**
 * Parse a parameter string like "lines=1-17 strip-spaces=4"
 * into { lines: "1-17", "strip-spaces": "4" }.
 */
export function parseDirectiveParams(paramString: string): Record<string, string> {
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

/**
 * Apply directive params to source text.
 *
 * For code directives: lines=M-N (1-based inclusive), strip-spaces=N
 * For output directives: limit-lines=N, limit-chars=N
 *
 * @param text - The source or output text.
 * @param params - Parsed parameters.
 * @param type - "code" or "output".
 */
export function applyDirectiveParams(
  text: string,
  params: Record<string, string>,
  type: 'code' | 'output'
): string {
  if (!text || !params || Object.keys(params).length === 0) return text;

  if (type === 'code') {
    // lines=M-N — 1-based inclusive range
    if (params['lines']) {
      const parts = params['lines'].split('-');
      const from = parseInt(parts[0], 10);
      const to = parts.length > 1 ? parseInt(parts[1], 10) : from;
      const lines = text.split('\n');
      text = lines.slice(from - 1, to).join('\n');
    }

    // strip-spaces=N — remove up to N leading spaces per line
    if (params['strip-spaces']) {
      const n = parseInt(params['strip-spaces'], 10);
      text = text
        .split('\n')
        .map((line) => {
          const leading = line.length - line.trimStart().length;
          return line.slice(Math.min(n, leading));
        })
        .join('\n');
    }
  } else {
    // limit-lines=N
    if (params['limit-lines']) {
      const n = parseInt(params['limit-lines'], 10);
      const lines = text.split('\n');
      if (lines.length > n) {
        text = lines.slice(0, n).join('\n') + '\n...';
      }
    }

    // limit-chars=N
    if (params['limit-chars']) {
      const n = parseInt(params['limit-chars'], 10);
      if (text.length > n) {
        text = text.slice(0, n) + '...';
      }
    }
  }

  return text;
}
