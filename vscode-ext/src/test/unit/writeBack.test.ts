import { describe, it, expect } from 'vitest';
import * as fs from 'fs';
import * as path from 'path';
import { replaceBlockSource, replaceCellSource, replaceNobookBlockSource } from '../../writeBack';

const FIXTURE_NB = path.resolve(__dirname, '..', 'fixtures', 'sample.ipynb');
const FIXTURE_PY = path.resolve(__dirname, '..', 'fixtures', 'sample.py');
const FIXTURE_NOBOOK = path.resolve(__dirname, '..', 'fixtures', 'sample-nobook.py');

describe('replaceCellSource', () => {
  it('replaces source in a cell while preserving @cell_id marker', () => {
    const nbContent = fs.readFileSync(FIXTURE_NB, 'utf-8');
    const result = replaceCellSource(nbContent, 'hello', 'print("replaced")');
    const nb = JSON.parse(result);

    const cell = nb.cells[0];
    const source = cell.source.join('');
    expect(source).toContain('# @cell_id=hello');
    expect(source).toContain('print("replaced")');
    expect(source).not.toContain('greet');
  });

  it('preserves attribute lines after @cell_id', () => {
    const nbContent = fs.readFileSync(FIXTURE_NB, 'utf-8');
    const result = replaceCellSource(nbContent, 'setup', 'new_code = True');
    const nb = JSON.parse(result);

    const cell = nb.cells[1];
    const source = cell.source.join('');
    expect(source).toContain('# @cell_id=setup');
    expect(source).toContain('# @language=python');
    expect(source).toContain('new_code = True');
    expect(source).not.toContain('import os');
  });

  it('does not modify other cells', () => {
    const nbContent = fs.readFileSync(FIXTURE_NB, 'utf-8');
    const result = replaceCellSource(nbContent, 'hello', 'changed');
    const nb = JSON.parse(result);

    // setup cell should be untouched
    const setupSource = nb.cells[1].source.join('');
    expect(setupSource).toContain('import os');
  });

  it('throws on non-existent cell ID', () => {
    const nbContent = fs.readFileSync(FIXTURE_NB, 'utf-8');
    expect(() => replaceCellSource(nbContent, 'nonexistent', 'x')).toThrow(/not found/);
  });

  it('produces valid JSON output', () => {
    const nbContent = fs.readFileSync(FIXTURE_NB, 'utf-8');
    const result = replaceCellSource(nbContent, 'hello', 'x = 1');
    expect(() => JSON.parse(result)).not.toThrow();
  });

  it('handles multi-line replacement', () => {
    const nbContent = fs.readFileSync(FIXTURE_NB, 'utf-8');
    const newSource = 'line1\nline2\nline3';
    const result = replaceCellSource(nbContent, 'hello', newSource);
    const nb = JSON.parse(result);

    const source = nb.cells[0].source.join('');
    expect(source).toContain('line1\nline2\nline3');
  });

  it('handles empty replacement', () => {
    const nbContent = fs.readFileSync(FIXTURE_NB, 'utf-8');
    const result = replaceCellSource(nbContent, 'hello', '');
    const nb = JSON.parse(result);

    const source = nb.cells[0].source.join('');
    expect(source).toContain('# @cell_id=hello');
    // Only the marker line and the empty string
    expect(source).not.toContain('greet');
  });

  it('works with inline notebook JSON (string source)', () => {
    const nb = {
      cells: [
        {
          cell_type: 'code',
          source: '# @cell_id=test\nold code',
          outputs: [],
        },
      ],
    };
    const result = replaceCellSource(JSON.stringify(nb), 'test', 'new code');
    const parsed = JSON.parse(result);
    const source = parsed.cells[0].source.join('');
    expect(source).toContain('# @cell_id=test');
    expect(source).toContain('new code');
    expect(source).not.toContain('old code');
  });

  it('throws when notebook has no cells array', () => {
    expect(() => replaceCellSource('{}', 'test', 'x')).toThrow(/no cells/);
  });
});

describe('replaceBlockSource', () => {
  it('replaces block content between markers', () => {
    const content = fs.readFileSync(FIXTURE_PY, 'utf-8');
    const result = replaceBlockSource(content, 'block-one', 'print("new")');

    expect(result).toContain('# @block=block-one');
    expect(result).toContain('print("new")');
    expect(result).toContain('# @end');
    expect(result).not.toContain('def hello');
  });

  it('preserves other blocks', () => {
    const content = fs.readFileSync(FIXTURE_PY, 'utf-8');
    const result = replaceBlockSource(content, 'block-one', 'changed');

    // block-two should be untouched
    expect(result).toContain('x = 42');
    expect(result).toContain('y = x * 2');
  });

  it('throws on non-existent block ID', () => {
    const content = fs.readFileSync(FIXTURE_PY, 'utf-8');
    expect(() => replaceBlockSource(content, 'nonexistent', 'x')).toThrow(/not found/);
  });

  it('handles multi-line replacement', () => {
    const content = fs.readFileSync(FIXTURE_PY, 'utf-8');
    const newSource = 'a = 1\nb = 2\nc = 3';
    const result = replaceBlockSource(content, 'block-two', newSource);

    expect(result).toContain('# @block=block-two');
    expect(result).toContain('a = 1\nb = 2\nc = 3');
    expect(result).toContain('# @end');
    expect(result).not.toContain('x = 42');
  });

  it('handles empty replacement', () => {
    const content = `# @block=block-one\nold code\n# @end\n`;
    const result = replaceBlockSource(content, 'block-one', '');

    expect(result).toContain('# @block=block-one\n\n# @end');
  });

  it('works with inline script content', () => {
    const content = `# @block=a
old line
# @end
`;
    const result = replaceBlockSource(content, 'a', 'new line');
    expect(result).toContain('# @block=a');
    expect(result).toContain('new line');
    expect(result).toContain('# @end');
    expect(result).not.toContain('old line');
  });

  it('handles block at end of file', () => {
    const content = `some code
# @block=last
original
# @end`;
    const result = replaceBlockSource(content, 'last', 'replaced');
    expect(result).toBe(`some code\n# @block=last\nreplaced\n# @end`);
  });

  it('preserves lines before and after blocks', () => {
    const content = `import os

# @block=middle
old_code()
# @end

print("done")
`;
    const result = replaceBlockSource(content, 'middle', 'new_code()');
    expect(result).toContain('import os');
    expect(result).toContain('print("done")');
    expect(result).toContain('new_code()');
    expect(result).not.toContain('old_code()');
  });
});

describe('replaceNobookBlockSource', () => {
  it('replaces block content up to the next block marker', () => {
    const content = fs.readFileSync(FIXTURE_NOBOOK, 'utf-8');
    const result = replaceNobookBlockSource(content, 'setup', 'message = "changed"');

    expect(result).toContain('# @block=setup');
    expect(result).toContain('message = "changed"');
    expect(result).toContain('# @block=show');
    expect(result).not.toContain('message = "hello from nobook"');
  });

  it('replaces the last nobook block through EOF', () => {
    const content = fs.readFileSync(FIXTURE_NOBOOK, 'utf-8');
    const result = replaceNobookBlockSource(content, 'show', 'print("done")');

    expect(result.trimEnd().endsWith('# @block=show\nprint("done")')).toBe(true);
  });
});
