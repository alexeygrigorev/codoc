/**
 * Webview editor — Monaco instance with ViewZones for inline code previews,
 * directive completions, and document sync with the extension host.
 */

import * as monaco from 'monaco-editor';
import './style.css';

// ============================================================================
// Types (duplicated here because webview can't import from src/)
// ============================================================================

interface CellInfo {
  id: string;
  source: string;
  output: CellOutput[];
  attributes: Record<string, string>;
}

interface CellOutput {
  type: 'stream' | 'execute_result' | 'error' | 'image';
  text?: string;
  ename?: string;
  evalue?: string;
  traceback?: string[];
  mimeType?: string;
}

interface BlockInfo {
  id: string;
  source: string;
  startLine: number;
  endLine: number;
}

interface NearbyFiles {
  notebooks: string[];
  scripts: string[];
}

type ExtensionMessage =
  | { type: 'loadContent'; content: string; cells: Record<string, Record<string, CellInfo>>; blocks: Record<string, Record<string, BlockInfo>>; nearbyFiles: NearbyFiles }
  | { type: 'updateCells'; sourceId: string; cells: Record<string, CellInfo> }
  | { type: 'updateBlocks'; sourceId: string; blocks: Record<string, BlockInfo> };

// ============================================================================
// VS Code API
// ============================================================================

// @ts-ignore — provided by VS Code webview runtime
const vscode = acquireVsCodeApi();

// ============================================================================
// State
// ============================================================================

/** All cells by source ID → cell ID → CellInfo */
let allCells: Record<string, Record<string, CellInfo>> = {};

/** All blocks by source ID → block ID → BlockInfo */
let allBlocks: Record<string, Record<string, BlockInfo>> = {};

/** Nearby .ipynb and .py files for frontmatter path completion */
let nearbyFiles: NearbyFiles = { notebooks: [], scripts: [] };

/** Active ViewZone IDs so we can remove them on refresh */
let activeZoneIds: string[] = [];

/** Map from ViewZone ID to directive info for click-to-navigate */
let zoneToDirective: Map<string, { sourceId: string; cellId: string; params: Record<string, string> }> = new Map();

/** Whether we're programmatically setting editor content (avoid feedback loop) */
let isSettingContent = false;

/** Timestamp of last user edit — used to ignore stale loadContent messages */
let lastUserEditTime = 0;

/** Debounce timer for sending edits */
let editDebounceTimer: ReturnType<typeof setTimeout> | undefined;

/** Debounce timer for ViewZone refresh */
let zoneRefreshTimer: ReturnType<typeof setTimeout> | undefined;

/** Debounce timer for writing cell edits back to source files */
let cellEditDebounceTimer: ReturnType<typeof setTimeout> | undefined;

/** Cached directive fingerprint to skip no-op refreshes */
let lastDirectiveFingerprint = '';

/** Currently active editing state — if set, refreshViewZones() is suppressed */
let activeEdit: {
  sourceId: string;
  cellId: string;
  textarea: HTMLTextAreaElement;
  originalContent: string;
} | null = null;

// ============================================================================
// Directive regex (matches in editor content)
// ============================================================================

const DIRECTIVE_RE = /^@@(code|code-output|code-figure)\s+(\S+):(\S+)((?:\s+\S+=\S+)*)\s*$/;

// ============================================================================
// Param logic (same as params.ts — duplicated for webview isolation)
// ============================================================================

function parseDirectiveParams(paramString: string): Record<string, string> {
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

function applyDirectiveParams(text: string, params: Record<string, string>, type: 'code' | 'output'): string {
  if (!text || !params || Object.keys(params).length === 0) return text;
  if (type === 'code') {
    if (params['lines']) {
      const parts = params['lines'].split('-');
      const from = parseInt(parts[0], 10);
      const to = parts.length > 1 ? parseInt(parts[1], 10) : from;
      const lines = text.split('\n');
      text = lines.slice(from - 1, to).join('\n');
    }
    if (params['strip-spaces']) {
      const n = parseInt(params['strip-spaces'], 10);
      text = text.split('\n').map(line => {
        const leading = line.length - line.trimStart().length;
        return line.slice(Math.min(n, leading));
      }).join('\n');
    }
  } else {
    if (params['limit-lines']) {
      const n = parseInt(params['limit-lines'], 10);
      const lines = text.split('\n');
      if (lines.length > n) {
        text = lines.slice(0, n).join('\n') + '\n...';
      }
    }
    if (params['limit-chars']) {
      const n = parseInt(params['limit-chars'], 10);
      if (text.length > n) {
        text = text.slice(0, n) + '...';
      }
    }
  }
  return text;
}

// ============================================================================
// Monaco Setup
// ============================================================================

declare const __BUILD_TIMESTAMP__: string;
console.log(`[codegen-vs] Webview loaded, built: ${new Date(__BUILD_TIMESTAMP__).toLocaleString()}, opened: ${new Date().toLocaleString()}`);

const container = document.getElementById('editor-container')!;

// Read font settings from data attributes (injected by extension host from VS Code config)
const vscFontSize = parseInt(document.body.dataset.fontSize || '14', 10);
const vscFontFamily = document.body.dataset.fontFamily || "Consolas, 'Courier New', monospace";

console.log(`[codegen-vs] Font: ${vscFontFamily}, size: ${vscFontSize}`);

// Define a dark theme matching VS Code with bold headings
monaco.editor.defineTheme('codegen-dark', {
  base: 'vs-dark',
  inherit: true,
  rules: [
    // Markdown headings — bold and colored
    { token: 'markup.heading', fontStyle: 'bold', foreground: '569cd6' },
    // YAML keys (used when we set frontmatter language)
    { token: 'type.yaml', foreground: '9cdcfe' },
    { token: 'string.yaml', foreground: 'ce9178' },
    { token: 'number.yaml', foreground: 'b5cea8' },
    { token: 'keyword.yaml', foreground: '569cd6' },
  ],
  colors: {
    'editor.background': '#1e1e1e',
  },
});

const editor = monaco.editor.create(container, {
  value: '',
  language: 'markdown',
  theme: 'codegen-dark',
  automaticLayout: true,
  minimap: { enabled: false },
  lineNumbers: 'on',
  wordWrap: 'on',
  fontSize: vscFontSize,
  fontFamily: vscFontFamily,
  fontLigatures: false,
  scrollBeyondLastLine: false,
  renderWhitespace: 'none',
  tabSize: 2,
});

console.log(`[codegen-vs] Monaco editor created, language: ${editor.getModel()?.getLanguageId()}`);

// ============================================================================
// Click-to-navigate — detect clicks on ViewZone widgets
// ============================================================================

editor.onMouseDown((e) => {
  // Only navigate on Ctrl+Click (Cmd+Click on Mac)
  if (!e.event.ctrlKey && !e.event.metaKey) return;

  // Check if the click target is inside a ViewZone
  if (e.target.type === monaco.editor.MouseTargetType.CONTENT_VIEW_ZONE
      || e.target.type === monaco.editor.MouseTargetType.OVERLAY_WIDGET) {
    const detail = e.target.detail as { viewZoneId?: string } | undefined;
    if (detail?.viewZoneId) {
      const directive = zoneToDirective.get(detail.viewZoneId);
      if (directive) {
        console.log(`[codegen-vs] Ctrl+Click navigate: ${directive.sourceId}:${directive.cellId}`);
        vscode.postMessage({ type: 'navigate', sourceId: directive.sourceId, cellId: directive.cellId, params: directive.params });
        return;
      }
    }
  }

  // Fallback: check if the click target element is inside a .codegen-viewzone
  const targetEl = e.target.element;
  if (targetEl) {
    const widget = targetEl.closest('.codegen-viewzone') as HTMLElement | null;
    if (widget) {
      const sourceId = widget.dataset.sourceId;
      const cellId = widget.dataset.cellId;
      if (sourceId && cellId) {
        let params: Record<string, string> = {};
        try { params = JSON.parse(widget.dataset.params || '{}'); } catch {}
        console.log(`[codegen-vs] Ctrl+Click navigate (DOM fallback): ${sourceId}:${cellId}`);
        vscode.postMessage({ type: 'navigate', sourceId, cellId, params });
      }
    }
  }
});

// ============================================================================
// ViewZones — inline code previews
// ============================================================================

interface DirectiveMatch {
  lineNumber: number; // 1-based
  type: 'code' | 'code-output' | 'code-figure';
  sourceId: string;
  cellId: string;
  params: Record<string, string>;
  rawLine: string;
}

function findDirectivesInEditor(): DirectiveMatch[] {
  const model = editor.getModel();
  if (!model) return [];

  const matches: DirectiveMatch[] = [];
  const lineCount = model.getLineCount();

  for (let i = 1; i <= lineCount; i++) {
    const line = model.getLineContent(i).trim();
    const m = DIRECTIVE_RE.exec(line);
    if (!m) continue;
    matches.push({
      lineNumber: i,
      type: m[1] as DirectiveMatch['type'],
      sourceId: m[2],
      cellId: m[3],
      params: parseDirectiveParams(m[4] ?? ''),
      rawLine: model.getLineContent(i),
    });
  }

  return matches;
}

/**
 * Resolve directive content: look up cell or block from loaded data.
 */
function resolveDirectiveContent(d: DirectiveMatch): { text: string; found: boolean } {
  // Check cells first, then blocks
  const cellSource = allCells[d.sourceId];
  if (cellSource) {
    const cell = cellSource[d.cellId];
    if (cell) {
      if (d.type === 'code') {
        return { text: applyDirectiveParams(cell.source, d.params, 'code').trimEnd(), found: true };
      } else if (d.type === 'code-output') {
        const outputText = cell.output
          .map(out => {
            if (out.type === 'stream' || out.type === 'execute_result') return out.text ?? '';
            if (out.type === 'error') return `${out.ename}: ${out.evalue}`;
            return '';
          })
          .filter(Boolean)
          .join('\n');
        if (!outputText) return { text: '(no output)', found: true };
        return { text: applyDirectiveParams(outputText, d.params, 'output').trimEnd(), found: true };
      } else if (d.type === 'code-figure') {
        return { text: '[figure — preview not available]', found: true };
      }
    }
  }

  const blockSource = allBlocks[d.sourceId];
  if (blockSource) {
    const block = blockSource[d.cellId];
    if (block) {
      return { text: applyDirectiveParams(block.source, d.params, 'code').trimEnd(), found: true };
    }
  }

  return { text: `(not found: ${d.sourceId}:${d.cellId})`, found: false };
}

/**
 * Check if a directive is editable (full cell, no filtering params).
 */
function isEditableDirective(d: DirectiveMatch): boolean {
  return d.type === 'code' && Object.keys(d.params).length === 0;
}

/**
 * Create a DOM node for the ViewZone widget.
 * Always shows colorized HTML. Editable cells swap to textarea on click.
 */
function createViewZoneWidget(d: DirectiveMatch, resolved: { text: string; found: boolean }): HTMLElement {
  const editable = isEditableDirective(d) && resolved.found;

  const widget = document.createElement('div');
  widget.className = `codegen-viewzone ${d.type === 'code-output' ? 'output' : 'code'} ${resolved.found ? '' : 'not-found'} ${editable ? 'editable' : ''}`;

  // Set font and line-height — smaller than editor for visual separation
  const lineHeight = editor.getOption(monaco.editor.EditorOption.lineHeight);
  const widgetFontSize = Math.max(vscFontSize - 2, 10);
  widget.style.fontFamily = vscFontFamily;
  widget.style.fontSize = `${widgetFontSize}px`;
  widget.style.lineHeight = `${lineHeight}px`;

  // Header
  const header = document.createElement('div');
  header.className = 'codegen-viewzone-header';

  // Type badge (CODE / OUTPUT / FIGURE)
  const badge = document.createElement('span');
  badge.className = 'codegen-viewzone-badge';
  badge.textContent = d.type === 'code' ? 'CODE' : d.type === 'code-output' ? 'OUTPUT' : 'FIGURE';

  // Source type indicator: IPYNB or PY
  const isScript = d.sourceId in allBlocks;
  const typeBadge = document.createElement('span');
  typeBadge.className = 'codegen-viewzone-type';
  typeBadge.textContent = isScript ? 'PY' : 'IPYNB';

  const label = document.createElement('span');
  label.className = 'codegen-viewzone-label';
  const paramStr = Object.entries(d.params).map(([k, v]) => `${k}=${v}`).join(' ');
  label.textContent = `${d.sourceId}:${d.cellId}${paramStr ? ' ' + paramStr : ''}`;

  header.appendChild(badge);

  // VIEW badge (non-clickable) for filtered directives
  const hasParams = Object.keys(d.params).length > 0;
  if (d.type === 'code' && hasParams) {
    const viewBadge = document.createElement('span');
    viewBadge.className = 'codegen-viewzone-badge view-badge';
    viewBadge.textContent = 'VIEW';
    header.appendChild(viewBadge);
  }

  header.appendChild(typeBadge);
  header.appendChild(label);

  // Copy icon button — always available
  const copyBtn = document.createElement('span');
  copyBtn.className = 'codegen-viewzone-icon-btn';
  copyBtn.title = 'Copy code';
  copyBtn.innerHTML = '<svg viewBox="0 0 16 16"><path d="M4 4l1-1h5.414L14 6.586V14l-1 1H5l-1-1V4zm9 3l-3-3H5v10h8V7zM3 1L2 2v10l1 1V2h6.414l-1-1H3z"/></svg>';
  header.appendChild(copyBtn);

  // Edit icon button — only for editable directives
  let editBtn: HTMLElement | null = null;
  if (editable) {
    editBtn = document.createElement('span');
    editBtn.className = 'codegen-viewzone-icon-btn';
    editBtn.title = 'Edit cell';
    editBtn.innerHTML = '<svg viewBox="0 0 16 16"><path d="M13.23 1h-1.46L3.52 9.25l-.16.22L1 13.59 2.41 15l4.12-2.36.22-.16L15 4.23V2.77L13.23 1zM2.41 13.59l1.51-3 1.45 1.45-2.96 1.55zm3.83-2.06L4.47 9.76l8-8 1.77 1.77-8 8z"/></svg>';
    header.appendChild(editBtn);
  }

  widget.appendChild(header);

  // Store directive info on DOM for fallback click detection
  widget.dataset.sourceId = d.sourceId;
  widget.dataset.cellId = d.cellId;
  widget.dataset.params = JSON.stringify(d.params);

  // Cursor hint that the widget is clickable (actual click handled by editor.onMouseDown)
  widget.style.cursor = 'pointer';
  widget.style.pointerEvents = 'auto';

  // Content: always start with colorized HTML
  const content = document.createElement('div');
  content.className = 'codegen-viewzone-content';

  if (resolved.found && (d.type === 'code' || d.type === 'code-output')) {
    const cellSource = allCells[d.sourceId];
    const cell = cellSource?.[d.cellId];
    const lang = d.type === 'code'
      ? (cell?.attributes?.['language'] ?? 'python')
      : 'plaintext';

    content.textContent = resolved.text;
    monaco.editor.colorize(resolved.text, lang, { tabSize: 4 }).then(html => {
      content.innerHTML = html.replace(/(<br\s*\/?>)+\s*$/, '');
    }).catch(err => {
      console.error(`[codegen-vs] colorize failed:`, err);
    });
  } else {
    content.textContent = resolved.text;
  }

  widget.appendChild(content);

  // Copy button — copy resolved text to clipboard
  copyBtn.addEventListener('mousedown', (e) => {
    e.stopPropagation();
    e.preventDefault();
    navigator.clipboard.writeText(resolved.text).then(() => {
      // Brief visual feedback — show checkmark
      const svg = copyBtn.innerHTML;
      copyBtn.innerHTML = '<svg viewBox="0 0 16 16"><path d="M6.27 10.87h.71l4.56-4.56-.71-.71-4.2 4.21-1.92-1.92-.71.71 2.27 2.27z"/><path d="M14 1H5l-1 1v10l1 1h9l1-1V2l-1-1zm0 11H5V2h9v10zM3 4H2v10l1 1h8v-1H3V4z"/></svg>';
      setTimeout(() => { copyBtn.innerHTML = svg; }, 1500);
    });
  });

  // Edit button — swap colorized HTML → textarea
  // Use mousedown (not click) because Monaco intercepts click events on ViewZones
  if (editable && editBtn) {
    editBtn.addEventListener('mousedown', (e) => {
      e.stopPropagation();
      e.preventDefault();
      if (activeEdit) return;

      const textarea = createEditableTextarea(d, resolved.text);
      widget.replaceChild(textarea, content);
      textarea.focus();
    });
  }

  return widget;
}

/**
 * Create an editable textarea for a cell directive.
 */
function createEditableTextarea(d: DirectiveMatch, text: string): HTMLTextAreaElement {
  const textarea = document.createElement('textarea');
  textarea.className = 'codegen-viewzone-textarea';
  textarea.value = text;
  textarea.spellcheck = false;
  textarea.setAttribute('wrap', 'off');
  textarea.rows = text.split('\n').length;

  // Focus handler — set active edit state to suppress zone refresh
  textarea.addEventListener('focus', () => {
    activeEdit = {
      sourceId: d.sourceId,
      cellId: d.cellId,
      textarea,
      originalContent: text,
    };
  });

  // Input handler — auto-resize + debounced write-back
  textarea.addEventListener('input', () => {
    // Auto-resize textarea to fit content
    textarea.rows = textarea.value.split('\n').length;

    clearTimeout(cellEditDebounceTimer);
    cellEditDebounceTimer = setTimeout(() => {
      if (activeEdit && textarea.value !== activeEdit.originalContent) {
        vscode.postMessage({
          type: 'editCell',
          sourceId: d.sourceId,
          cellId: d.cellId,
          newSource: textarea.value,
        });
      }
    }, 500);
  });

  // Blur handler — flush pending edit, clear active state, refresh zones
  textarea.addEventListener('blur', () => {
    clearTimeout(cellEditDebounceTimer);
    if (activeEdit && textarea.value !== activeEdit.originalContent) {
      vscode.postMessage({
        type: 'editCell',
        sourceId: d.sourceId,
        cellId: d.cellId,
        newSource: textarea.value,
      });
    }
    activeEdit = null;
    // Refresh all zones after editing is done
    setTimeout(() => refreshViewZones(true), 50);
  });

  // Prevent Monaco from stealing focus when clicking inside the textarea
  textarea.addEventListener('mousedown', (e) => {
    e.stopPropagation();
  });

  // Prevent Monaco from capturing keystrokes meant for the textarea
  textarea.addEventListener('keydown', (e) => {
    e.stopPropagation();

    // Tab key inserts 4 spaces
    if (e.key === 'Tab') {
      e.preventDefault();
      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;
      textarea.value = textarea.value.substring(0, start) + '    ' + textarea.value.substring(end);
      textarea.selectionStart = textarea.selectionEnd = start + 4;
      textarea.dispatchEvent(new Event('input'));
    }

    // Escape returns focus to main editor
    if (e.key === 'Escape') {
      textarea.blur();
      editor.focus();
    }
  });

  return textarea;
}

/**
 * Build a fingerprint of current directives to detect if they changed.
 * Line numbers are excluded — Monaco repositions ViewZones automatically when
 * lines are added/removed, so we only rebuild when directive content changes.
 */
function directiveFingerprint(directives: DirectiveMatch[]): string {
  return directives.map(d =>
    `${d.type}:${d.sourceId}:${d.cellId}:${JSON.stringify(d.params)}`
  ).join('|');
}

/**
 * Refresh all ViewZones based on current editor content and loaded cells/blocks.
 * @param force - If true, skip the fingerprint check and always refresh.
 */
function refreshViewZones(force = false): void {
  // If a textarea is focused (user is editing a cell), don't destroy zones
  if (activeEdit) return;

  const directives = findDirectivesInEditor();

  // Skip refresh if directives haven't changed (avoids scroll jumps during typing)
  if (!force) {
    const fp = directiveFingerprint(directives);
    if (fp === lastDirectiveFingerprint) return;
    lastDirectiveFingerprint = fp;
  } else {
    lastDirectiveFingerprint = directiveFingerprint(directives);
  }

  // Save scroll position to restore after zone rebuild
  const scrollTop = editor.getScrollTop();

  editor.changeViewZones(accessor => {
    // Remove existing zones
    for (const id of activeZoneIds) {
      accessor.removeZone(id);
    }
    activeZoneIds = [];
    zoneToDirective = new Map();

    // Add new zones
    const lineHeight = editor.getOption(monaco.editor.EditorOption.lineHeight);
    for (const d of directives) {
      const resolved = resolveDirectiveContent(d);
      const domNode = createViewZoneWidget(d, resolved);
      const editable = isEditableDirective(d) && resolved.found;

      // Height in pixels: header (1 line) + content lines
      const contentLines = resolved.text.split('\n').length;
      const heightInPx = (contentLines + 1) * lineHeight;

      const zoneId = accessor.addZone({
        afterLineNumber: d.lineNumber,
        heightInPx,
        domNode,
        suppressMouseDown: false,
      });
      activeZoneIds.push(zoneId);
      zoneToDirective.set(zoneId, { sourceId: d.sourceId, cellId: d.cellId, params: d.params });
    }
  });

  // Restore scroll position after zone rebuild
  editor.setScrollTop(scrollTop);

  // Add line decorations for directive lines
  refreshDecorations(directives);
}

// ============================================================================
// Line Decorations — highlight directive lines
// ============================================================================

let decorationIds: string[] = [];

function refreshDecorations(directives: DirectiveMatch[]): void {
  const model = editor.getModel();
  if (!model) return;

  const newDecorations: monaco.editor.IModelDeltaDecoration[] = [];

  // Directive line decorations
  for (const d of directives) {
    const resolved = resolveDirectiveContent(d);
    newDecorations.push({
      range: new monaco.Range(d.lineNumber, 1, d.lineNumber, 1),
      options: {
        isWholeLine: true,
        className: resolved.found ? 'codegen-directive-found' : 'codegen-directive-not-found',
        glyphMarginClassName: resolved.found ? 'codegen-glyph-found' : 'codegen-glyph-not-found',
      },
    });
  }

  // Markdown heading decorations — make # lines bold
  const lineCount = model.getLineCount();
  for (let i = 1; i <= lineCount; i++) {
    const line = model.getLineContent(i);
    const headingMatch = line.match(/^(#{1,6})\s/);
    if (headingMatch) {
      newDecorations.push({
        range: new monaco.Range(i, 1, i, line.length + 1),
        options: {
          inlineClassName: 'codegen-heading',
        },
      });
    }
  }

  // YAML frontmatter decorations
  const firstLine = model.getLineContent(1);
  if (firstLine.trim() === '---') {
    // Find closing ---
    let fmEndLine = -1;
    for (let i = 2; i <= lineCount; i++) {
      if (model.getLineContent(i).trim() === '---') {
        fmEndLine = i;
        break;
      }
    }
    if (fmEndLine > 0) {
      // --- delimiters
      newDecorations.push({
        range: new monaco.Range(1, 1, 1, 4),
        options: { inlineClassName: 'codegen-yaml-delimiter' },
      });
      newDecorations.push({
        range: new monaco.Range(fmEndLine, 1, fmEndLine, 4),
        options: { inlineClassName: 'codegen-yaml-delimiter' },
      });

      // YAML content between delimiters
      for (let i = 2; i < fmEndLine; i++) {
        const line = model.getLineContent(i);

        // Key: value pattern
        const kvMatch = line.match(/^(\s*-?\s*)(\w[\w-]*)(:)(.*)$/);
        if (kvMatch) {
          const keyStart = kvMatch[1].length + 1;
          const keyEnd = keyStart + kvMatch[2].length;
          const colonEnd = keyEnd + 1;

          // Highlight the key
          newDecorations.push({
            range: new monaco.Range(i, keyStart, i, keyEnd),
            options: { inlineClassName: 'codegen-yaml-key' },
          });
          // Highlight the colon
          newDecorations.push({
            range: new monaco.Range(i, keyEnd, i, colonEnd),
            options: { inlineClassName: 'codegen-yaml-colon' },
          });
          // Highlight the value
          const value = kvMatch[4].trim();
          if (value) {
            const valueStart = line.indexOf(value, colonEnd - 1) + 1;
            const valueEnd = valueStart + value.length;
            // Boolean values
            if (value === 'true' || value === 'false') {
              newDecorations.push({
                range: new monaco.Range(i, valueStart, i, valueEnd),
                options: { inlineClassName: 'codegen-yaml-bool' },
              });
            } else {
              newDecorations.push({
                range: new monaco.Range(i, valueStart, i, valueEnd),
                options: { inlineClassName: 'codegen-yaml-value' },
              });
            }
          }
        }
      }
    }
  }

  decorationIds = editor.deltaDecorations(decorationIds, newDecorations);
}

// ============================================================================
// Links — Ctrl+Click on frontmatter path: values to open files
// ============================================================================

monaco.languages.registerLinkProvider('markdown', {
  provideLinks(model) {
    const links: monaco.languages.ILink[] = [];
    const lineCount = model.getLineCount();

    // Find frontmatter boundaries
    if (model.getLineContent(1).trim() !== '---') return { links };
    let fmEnd = -1;
    for (let i = 2; i <= lineCount; i++) {
      if (model.getLineContent(i).trim() === '---') { fmEnd = i; break; }
    }
    if (fmEnd < 0) return { links };

    // Scan frontmatter for path: values
    for (let i = 2; i < fmEnd; i++) {
      const line = model.getLineContent(i);
      const pathMatch = line.match(/^(\s*path:\s*)(\S+)\s*$/);
      if (!pathMatch) continue;

      const pathValue = pathMatch[2];
      const startCol = pathMatch[1].length + 1;
      const endCol = startCol + pathValue.length;

      links.push({
        range: new monaco.Range(i, startCol, i, endCol),
        // Use a custom URI scheme — we intercept this in the link opener
        url: `codegen-open:${pathValue}`,
      });
    }

    return { links };
  },
});

// Intercept link clicks — send openFile message to extension host
monaco.editor.registerEditorOpener({
  openCodeEditor(_source, resource, _selectionOrPosition) {
    if (resource.scheme === 'codegen-open') {
      const relativePath = resource.path || resource.authority;
      vscode.postMessage({ type: 'openFile', relativePath });
      return true;
    }
    return false;
  },
});

// ============================================================================
// Completions — autocomplete for @@code directives
// ============================================================================

monaco.languages.registerCompletionItemProvider('markdown', {
  triggerCharacters: ['@', ':', ' '],

  provideCompletionItems(model, position) {
    const lineContent = model.getLineContent(position.lineNumber);
    const textUntilPosition = lineContent.substring(0, position.column - 1);

    const items: monaco.languages.CompletionItem[] = [];
    const range = {
      startLineNumber: position.lineNumber,
      startColumn: position.column,
      endLineNumber: position.lineNumber,
      endColumn: position.column,
    };

    // Suggest directive types after @@
    if (textUntilPosition.match(/^@@$/)) {
      for (const kind of ['code', 'code-output', 'code-figure']) {
        items.push({
          label: kind,
          kind: monaco.languages.CompletionItemKind.Keyword,
          insertText: kind + ' ',
          range,
        });
      }
      return { suggestions: items };
    }

    // Suggest source IDs after @@code / @@code-output / @@code-figure + space
    const afterDirective = textUntilPosition.match(/^@@(?:code|code-output|code-figure)\s+$/);
    if (afterDirective) {
      const sourceIds = new Set([...Object.keys(allCells), ...Object.keys(allBlocks)]);
      for (const id of sourceIds) {
        items.push({
          label: id,
          kind: monaco.languages.CompletionItemKind.Module,
          insertText: id + ':',
          range,
        });
      }
      return { suggestions: items };
    }

    // Suggest cell/block IDs after sourceId:
    const afterColon = textUntilPosition.match(/^@@(?:code|code-output|code-figure)\s+(\S+):$/);
    if (afterColon) {
      const sourceId = afterColon[1];
      const cellIds = allCells[sourceId] ? Object.keys(allCells[sourceId]) : [];
      const blockIds = allBlocks[sourceId] ? Object.keys(allBlocks[sourceId]) : [];
      for (const id of [...cellIds, ...blockIds]) {
        items.push({
          label: id,
          kind: monaco.languages.CompletionItemKind.Value,
          insertText: id,
          range,
        });
      }
      return { suggestions: items };
    }

    // Suggest params after cellId + space
    const afterCellId = textUntilPosition.match(/^@@(code|code-output|code-figure)\s+\S+:\S+\s+$/);
    if (afterCellId) {
      const dirType = afterCellId[1];
      const paramSuggestions = dirType === 'code'
        ? ['lines=', 'strip-spaces=']
        : dirType === 'code-output'
          ? ['limit-lines=', 'limit-chars=']
          : ['format=', 'quality='];
      for (const param of paramSuggestions) {
        items.push({
          label: param,
          kind: monaco.languages.CompletionItemKind.Property,
          insertText: param,
          range,
        });
      }
      return { suggestions: items };
    }

    // Frontmatter completions — check if cursor is between --- markers
    const fullText = model.getValue();
    const firstDash = fullText.indexOf('---');
    const secondDash = fullText.indexOf('---', firstDash + 3);
    if (firstDash >= 0 && secondDash > firstDash) {
      const fmStart = model.getPositionAt(firstDash);
      const fmEnd = model.getPositionAt(secondDash + 3);
      const inFrontmatter = position.lineNumber > fmStart.lineNumber && position.lineNumber < fmEnd.lineNumber;

      if (inFrontmatter) {
        const trimmed = textUntilPosition.trim();

        // After "path:" suggest nearby .ipynb and .py files
        if (trimmed.match(/path:\s*$/)) {
          // Check context: are we in notebooks or scripts section?
          const linesAbove = model.getValue().split('\n').slice(0, position.lineNumber);
          const inNotebooks = linesAbove.some(l => l.trim() === 'notebooks:');
          const inScripts = linesAbove.some(l => l.trim() === 'scripts:');

          const files = inScripts ? nearbyFiles.scripts : nearbyFiles.notebooks;
          for (const filePath of files) {
            items.push({
              label: filePath,
              kind: monaco.languages.CompletionItemKind.File,
              insertText: filePath,
              range,
            });
          }
          // Also suggest from the other type
          const otherFiles = inScripts ? nearbyFiles.notebooks : nearbyFiles.scripts;
          for (const filePath of otherFiles) {
            items.push({
              label: filePath,
              kind: monaco.languages.CompletionItemKind.File,
              insertText: filePath,
              detail: inScripts ? 'notebook' : 'script',
              range,
            });
          }
          return { suggestions: items };
        }

        // After "- id:" suggest a name derived from nearby files
        if (trimmed.match(/^-\s+id:\s*$/)) {
          const usedIds = new Set([...Object.keys(allCells), ...Object.keys(allBlocks)]);
          for (const id of usedIds) {
            items.push({
              label: id,
              kind: monaco.languages.CompletionItemKind.Reference,
              insertText: id,
              detail: 'Existing source ID',
              range,
            });
          }
          // Suggest short names from nearby notebook files
          for (const nb of nearbyFiles.notebooks) {
            const name = nb.replace(/.*\//, '').replace('.ipynb', '');
            if (!usedIds.has(name)) {
              items.push({
                label: name,
                kind: monaco.languages.CompletionItemKind.Value,
                insertText: name,
                detail: nb,
                range,
              });
            }
          }
          return { suggestions: items };
        }

        // After "- " suggest entry structure
        if (trimmed === '-' || trimmed === '') {
          items.push({
            label: 'notebook entry',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: '- id: ${1:name}\n    path: ${2:../notebook.ipynb}',
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            detail: 'Add a notebook reference',
            range,
          });
          items.push({
            label: 'script entry',
            kind: monaco.languages.CompletionItemKind.Snippet,
            insertText: '- id: ${1:name}\n    path: ${2:../script.py}',
            insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet,
            detail: 'Add a script reference',
            range,
          });
        }

        // Suggest frontmatter keys at root level
        if (trimmed === '') {
          items.push(
            { label: 'notebooks:', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'notebooks:\n  ', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range },
            { label: 'scripts:', kind: monaco.languages.CompletionItemKind.Keyword, insertText: 'scripts:\n  ', insertTextRules: monaco.languages.CompletionItemInsertTextRule.InsertAsSnippet, range },
          );
        }

        return { suggestions: items };
      }
    }

    return { suggestions: items };
  },
});

// ============================================================================
// Document sync — editor ↔ extension host
// ============================================================================

editor.onDidChangeModelContent(() => {
  if (isSettingContent) return;

  // Track when user last edited — used to ignore stale loadContent echo
  lastUserEditTime = Date.now();

  // Debounce: send edit after 300ms of inactivity
  clearTimeout(editDebounceTimer);
  editDebounceTimer = setTimeout(() => {
    vscode.postMessage({ type: 'edit', content: editor.getValue() });
  }, 300);

  // Debounce ViewZone refresh — only runs if directives actually changed
  // (fingerprint check inside refreshViewZones prevents no-op rebuilds)
  clearTimeout(zoneRefreshTimer);
  zoneRefreshTimer = setTimeout(() => refreshViewZones(), 500);
});

// Ctrl+S → save
editor.addCommand(monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyS, () => {
  // Flush any pending edit
  clearTimeout(editDebounceTimer);
  vscode.postMessage({ type: 'edit', content: editor.getValue() });
  vscode.postMessage({ type: 'save' });
});

// ============================================================================
// Message handling from extension host
// ============================================================================

window.addEventListener('message', (event) => {
  const msg = event.data as ExtensionMessage;

  switch (msg.type) {
    case 'loadContent': {
      console.log(`[codegen-vs] loadContent: cells=${JSON.stringify(Object.keys(msg.cells))}, blocks=${JSON.stringify(Object.keys(msg.blocks))}, notebooks=${msg.nearbyFiles?.notebooks?.length ?? 0}, scripts=${msg.nearbyFiles?.scripts?.length ?? 0}`);
      allCells = msg.cells;
      allBlocks = msg.blocks;
      if (msg.nearbyFiles) nearbyFiles = msg.nearbyFiles;

      // Ignore stale content echoes during active editing.
      // If the user edited < 2s ago, the extension host is likely echoing back
      // our own edit with stale content. Only update cells/blocks data, not text.
      const timeSinceEdit = Date.now() - lastUserEditTime;
      if (timeSinceEdit < 2000 && editor.getValue().length > 0) {
        console.log(`[codegen-vs] Skipping setValue — user edited ${timeSinceEdit}ms ago`);
        refreshViewZones(true);
        break;
      }

      // Update editor content, preserving scroll position and cursor
      if (editor.getValue() !== msg.content) {
        const scrollTop = editor.getScrollTop();
        const position = editor.getPosition();
        isSettingContent = true;
        editor.setValue(msg.content);
        isSettingContent = false;
        if (position) editor.setPosition(position);
        editor.setScrollTop(scrollTop);
      }

      refreshViewZones(true);
      break;
    }

    case 'updateCells': {
      allCells[msg.sourceId] = msg.cells;
      refreshViewZones(true);
      break;
    }

    case 'updateBlocks': {
      allBlocks[msg.sourceId] = msg.blocks;
      refreshViewZones(true);
      break;
    }
  }
});

// ============================================================================
// Tell extension host we're ready
// ============================================================================

vscode.postMessage({ type: 'ready' });
