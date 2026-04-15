import { describe, it, expect } from 'vitest';
import * as path from 'path';
import * as fs from 'fs';
import { readScriptBlocks, parseScriptBlocks } from '../../script';
import { parseTemplate } from '../../parser';

const FIXTURE_PATH = path.resolve(__dirname, '..', 'fixtures', 'sample.py');

describe('readScriptBlocks', () => {
  it('reads blocks from the fixture file', () => {
    const blocks = readScriptBlocks(FIXTURE_PATH);

    expect(blocks.size).toBe(2);
    expect(blocks.has('block-one')).toBe(true);
    expect(blocks.has('block-two')).toBe(true);
  });

  it('extracts source without markers', () => {
    const blocks = readScriptBlocks(FIXTURE_PATH);
    const one = blocks.get('block-one')!;

    expect(one.source).toBe('def hello():\n    print("world")');
    expect(one.source).not.toContain('@block');
    expect(one.source).not.toContain('@end');
  });

  it('records line numbers', () => {
    const blocks = readScriptBlocks(FIXTURE_PATH);
    const one = blocks.get('block-one')!;

    expect(one.startLine).toBe(1);
    expect(one.endLine).toBe(4);

    const two = blocks.get('block-two')!;
    expect(two.startLine).toBe(6);
    expect(two.endLine).toBe(9);
  });

  it('throws on missing file', () => {
    expect(() => readScriptBlocks('/nonexistent/path.py')).toThrow();
  });
});

describe('parseScriptBlocks', () => {
  it('handles multiple blocks', () => {
    const content = `# @block=a
line1
# @end

# @block=b
line2
# @end
`;
    const blocks = parseScriptBlocks(content);
    expect(blocks.size).toBe(2);
    expect(blocks.get('a')!.source).toBe('line1');
    expect(blocks.get('b')!.source).toBe('line2');
  });

  it('throws on unclosed block', () => {
    const content = '# @block=oops\nsome code\n';
    expect(() => parseScriptBlocks(content)).toThrow(/Unclosed block/);
  });

  it('throws on duplicate block IDs', () => {
    const content = `# @block=dup
a
# @end
# @block=dup
b
# @end
`;
    expect(() => parseScriptBlocks(content)).toThrow(/Duplicate block ID/);
  });

  it('throws on nested blocks', () => {
    const content = `# @block=outer
# @block=inner
code
# @end
# @end
`;
    expect(() => parseScriptBlocks(content)).toThrow(/Nested block/);
  });

  it('throws on @end without @block', () => {
    const content = '# @end\n';
    expect(() => parseScriptBlocks(content)).toThrow(/without matching/);
  });

  it('handles empty blocks', () => {
    const content = '# @block=empty\n# @end\n';
    const blocks = parseScriptBlocks(content);
    expect(blocks.get('empty')!.source).toBe('');
  });

  it('trims leading/trailing whitespace from source', () => {
    const content = `# @block=trimmed

  indented code

# @end
`;
    const blocks = parseScriptBlocks(content);
    // .trim() strips leading \n and leading spaces, matching Python's .strip()
    expect(blocks.get('trimmed')!.source).toBe('indented code');
  });
});

describe('real template: 02-converting-to-project', () => {
  const templatePath = path.resolve(__dirname, '..', '..', '..', '..', 'v2', '04-testing', '02-testing', '02-converting-to-project.template.md');
  const templateDir = path.dirname(templatePath);

  // Skip if the template doesn't exist (CI environments)
  const skip = !fs.existsSync(templatePath);

  it.skipIf(skip)('parses frontmatter with 3 script refs', () => {
    const content = fs.readFileSync(templatePath, 'utf-8');
    const parsed = parseTemplate(content);
    expect(parsed.frontmatter.scripts).toHaveLength(3);
    expect(parsed.frontmatter.scripts.map(s => s.id)).toEqual(['tools', 'agent', 'main']);
  });

  it.skipIf(skip)('all script files exist', () => {
    const content = fs.readFileSync(templatePath, 'utf-8');
    const parsed = parseTemplate(content);
    for (const scRef of parsed.frontmatter.scripts) {
      const scPath = path.resolve(templateDir, scRef.path);
      expect(fs.existsSync(scPath), `${scRef.id}: ${scPath} should exist`).toBe(true);
    }
  });

  it.skipIf(skip)('reads all script blocks successfully', () => {
    const content = fs.readFileSync(templatePath, 'utf-8');
    const parsed = parseTemplate(content);
    const blocks: Record<string, Record<string, any>> = {};

    for (const scRef of parsed.frontmatter.scripts) {
      const scPath = path.resolve(templateDir, scRef.path);
      const blockMap = readScriptBlocks(scPath);
      const blockRecord: Record<string, any> = {};
      blockMap.forEach((block, id) => { blockRecord[id] = block; });
      blocks[scRef.id] = blockRecord;
    }

    // tools.py blocks
    expect(Object.keys(blocks['tools'])).toContain('download-docs');
    expect(Object.keys(blocks['tools'])).toContain('create-tools');

    // doc_agent.py blocks
    expect(Object.keys(blocks['agent'])).toContain('imports');
    expect(Object.keys(blocks['agent'])).toContain('create-agent');

    // main.py blocks — this is the one that was failing
    expect(Object.keys(blocks['main'])).toContain('run-agent-question');
    expect(Object.keys(blocks['main'])).toContain('entry-point');
  });

  it.skipIf(skip)('every directive resolves to a found block', () => {
    const content = fs.readFileSync(templatePath, 'utf-8');
    const parsed = parseTemplate(content);
    const blocks: Record<string, Record<string, any>> = {};

    for (const scRef of parsed.frontmatter.scripts) {
      const scPath = path.resolve(templateDir, scRef.path);
      const blockMap = readScriptBlocks(scPath);
      const blockRecord: Record<string, any> = {};
      blockMap.forEach((block, id) => { blockRecord[id] = block; });
      blocks[scRef.id] = blockRecord;
    }

    for (const d of parsed.directives) {
      const blockSource = blocks[d.sourceId];
      expect(blockSource, `blocks for source '${d.sourceId}' should exist`).toBeDefined();
      expect(blockSource[d.cellId], `${d.sourceId}:${d.cellId} should be found`).toBeDefined();
    }
  });
});
