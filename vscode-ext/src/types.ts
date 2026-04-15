/** Shared interfaces for the codegen VS Code extension. */

/** Reference to a Jupyter notebook from template frontmatter. */
export interface NotebookRef {
  id: string;
  path: string;
  execute?: boolean;
  image_folder?: string;
}

/** Reference to a script file from template frontmatter. */
export interface ScriptRef {
  id: string;
  path: string;
}

/** Parsed frontmatter from a template file. */
export interface Frontmatter {
  notebooks: NotebookRef[];
  scripts: ScriptRef[];
}

/** A directive found in a template body. */
export interface Directive {
  type: 'code' | 'code-output' | 'code-figure';
  sourceId: string;   // notebook or script ID
  cellId: string;     // cell or block ID
  lineNumber: number; // 0-based line number in the full document
  rawLine: string;    // the original line text
  params: Record<string, string>;
}

/** Result of parsing a template file. */
export interface ParsedTemplate {
  content: string;
  frontmatter: Frontmatter;
  body: string;
  bodyStartLine: number;
  directives: Directive[];
}

/** Info about a single notebook cell. */
export interface CellInfo {
  id: string;
  source: string;
  output: CellOutput[];
  attributes: Record<string, string>;
}

/** A single output from a notebook cell. */
export interface CellOutput {
  type: 'stream' | 'execute_result' | 'error' | 'image';
  text?: string;
  ename?: string;
  evalue?: string;
  traceback?: string[];
  mimeType?: string;
}

/** Info about a script block. */
export interface BlockInfo {
  id: string;
  source: string;
  startLine: number;
  endLine: number;
}

/** Nearby files for path autocompletion in frontmatter. */
export interface NearbyFiles {
  notebooks: string[];  // relative paths to .ipynb files
  scripts: string[];    // relative paths to .py files
}

/** Messages from extension host to webview. */
export type ExtensionToWebviewMessage =
  | { type: 'loadContent'; content: string; cells: Record<string, Record<string, CellInfo>>; blocks: Record<string, Record<string, BlockInfo>>; nearbyFiles: NearbyFiles }
  | { type: 'updateCells'; sourceId: string; cells: Record<string, CellInfo> }
  | { type: 'updateBlocks'; sourceId: string; blocks: Record<string, BlockInfo> };

/** Messages from webview to extension host. */
export type WebviewToExtensionMessage =
  | { type: 'edit'; content: string }
  | { type: 'save' }
  | { type: 'ready' }
  | { type: 'navigate'; sourceId: string; cellId: string; params?: Record<string, string> }
  | { type: 'editCell'; sourceId: string; cellId: string; newSource: string }
  | { type: 'openFile'; relativePath: string };
