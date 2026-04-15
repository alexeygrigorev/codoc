# Editable Cells — Future Feature Plan

## Goal

Make `@@code` directives without params (`lines=`, `strip-spaces=`) editable inline.
Changes write back to the source `.ipynb` or `.py` file.
Directives with params show a "VIEW" badge and stay read-only.
`@@code-output` and `@@code-figure` are always read-only.

## Editability Detection

```typescript
function isEditableDirective(d: DirectiveMatch): boolean {
  return d.type === 'code' && Object.keys(d.params).length === 0;
}
```

## Architecture

### New file: `src/writeBack.ts`

Two write-back functions:

**Notebook write-back** (`replaceCellSource`):
- Read .ipynb JSON, find cell with `@cell_id=X` marker
- Preserve marker + attribute lines (`# @cell_id=...`, `# @key=value`)
- Replace remaining source lines with new content
- Write JSON back (Jupyter uses array-of-strings format, each line ending with `\n` except last)
- Use `JSON.stringify(nb, null, 1)` for standard Jupyter indentation

**Script write-back** (`replaceBlockSource`):
- Read .py file, find `# @block=X` line
- Replace lines between it and `# @end` with new content
- Preserve the marker lines themselves

### New message type

Add to `WebviewToExtensionMessage` in `types.ts`:
```typescript
| { type: 'editCell'; sourceId: string; cellId: string; newSource: string }
```

### Webview changes (`editor.ts`)

1. Track active edit state:
```typescript
let activeEdit: {
  sourceId: string;
  cellId: string;
  textarea: HTMLTextAreaElement;
  originalContent: string;
} | null = null;
```

2. In `refreshViewZones()`: bail out early when `activeEdit` is non-null (prevents textarea destruction during editing)

3. In `createViewZoneWidget()`: for editable directives, render a `<textarea>` instead of colorized HTML

4. Textarea features:
   - `stopPropagation()` on keydown to prevent Monaco from capturing keypresses
   - Tab key inserts 4 spaces
   - Escape blurs textarea and returns focus to main editor
   - Auto-resize height on input
   - Debounced (500ms) `editCell` message on input
   - Flush pending edit on blur, then `refreshViewZones()`

5. For view directives (has params): add "VIEW" badge, keep colorized HTML

### Extension host changes (`editorProvider.ts`)

1. Handle `editCell` message:
   - Find source file (notebook or script) from frontmatter
   - Call `replaceCellSource` or `replaceBlockSource`
   - Write file
   - Re-read cells/blocks and send `updateCells`/`updateBlocks` to webview

2. Add `isWritingCell` flag to prevent file watcher from triggering redundant re-reads after our own writes

### CSS additions (`style.css`)

```css
.codegen-viewzone-textarea {
  width: 100%;
  min-height: 1.5em;
  margin: 0; padding: 0;
  border: none; outline: none; resize: none;
  background: transparent; color: #d4d4d4;
  white-space: pre; overflow: hidden;
  line-height: inherit; font-family: inherit; font-size: inherit;
  tab-size: 4; box-sizing: border-box;
}

.codegen-viewzone-textarea:focus {
  background: rgba(74, 158, 255, 0.04);
  outline: 1px solid rgba(74, 158, 255, 0.3);
}

.codegen-viewzone-badge.view-badge {
  background: #5a5a5a44; color: #888;
}

.codegen-viewzone-edit-hint {
  display: inline-block; padding: 0 4px;
  border-radius: 3px; font-size: 9px; font-weight: 600;
  letter-spacing: 0.5px;
  background: #4a9eff22; color: #4a9eff88;
}
```

### ViewZone height for editable zones

Set generous height: `Math.min(contentLines + 2, 25)` with textarea scrolling if needed.
On blur, full zone refresh recalculates correct height.

## Edge Cases

- **File watcher race**: Our write triggers file watcher. `isWritingCell` flag prevents redundant re-reads.
- **External modification during edit**: `activeEdit` suppresses refresh. On blur, latest data is picked up.
- **Notebook JSON formatting**: `JSON.stringify(nb, null, 1)` may differ from original. Content is correct even if whitespace differs.
- **Ctrl+Z in textarea**: Browser textarea has own undo stack, separate from Monaco. This is fine.
- **Write failure**: Show `vscode.window.showErrorMessage()`. Textarea still has user's edits (no data loss).

## Implementation Order

1. `src/types.ts` — Add editCell message type
2. `src/writeBack.ts` — Create write-back functions
3. `src/test/unit/writeBack.test.ts` — Test write-back functions
4. `webview/style.css` — Add new CSS classes
5. `webview/editor.ts` — Add editability detection, textarea, active edit state, refresh guard
6. `src/editorProvider.ts` — Add editCell handler with write-back

## Tests

Unit tests for `replaceCellSource` and `replaceBlockSource`:
- Replace cell source preserving markers and attributes
- Replace block content preserving @block/@end markers
- Throw for missing cell/block
- Handle both string and array source formats in notebooks
