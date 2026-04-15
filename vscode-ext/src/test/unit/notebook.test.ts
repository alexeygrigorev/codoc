import { describe, it, expect } from 'vitest';
import * as path from 'path';
import { readNotebook, parseCells } from '../../notebook';

const FIXTURE_PATH = path.resolve(__dirname, '..', 'fixtures', 'sample.ipynb');

describe('readNotebook', () => {
  it('reads cells with @cell_id markers', () => {
    const cells = readNotebook(FIXTURE_PATH);

    expect(cells.size).toBe(3); // hello, setup, error-cell
    expect(cells.has('hello')).toBe(true);
    expect(cells.has('setup')).toBe(true);
    expect(cells.has('error-cell')).toBe(true);
  });

  it('strips @cell_id marker from source', () => {
    const cells = readNotebook(FIXTURE_PATH);
    const hello = cells.get('hello')!;

    expect(hello.source).not.toContain('@cell_id');
    expect(hello.source).toContain('def greet(name):');
  });

  it('extracts cell attributes', () => {
    const cells = readNotebook(FIXTURE_PATH);
    const setup = cells.get('setup')!;

    expect(setup.attributes).toEqual({ language: 'python' });
    expect(setup.source).not.toContain('@language');
    expect(setup.source).toContain('import os');
  });

  it('extracts stream output', () => {
    const cells = readNotebook(FIXTURE_PATH);
    const hello = cells.get('hello')!;

    const stream = hello.output.find(o => o.type === 'stream');
    expect(stream).toBeDefined();
    expect(stream!.text).toContain('Hello, World!');
  });

  it('extracts execute_result output', () => {
    const cells = readNotebook(FIXTURE_PATH);
    const hello = cells.get('hello')!;

    const result = hello.output.find(o => o.type === 'execute_result');
    expect(result).toBeDefined();
    expect(result!.text).toContain("'World'");
  });

  it('extracts error output', () => {
    const cells = readNotebook(FIXTURE_PATH);
    const errorCell = cells.get('error-cell')!;

    const error = errorCell.output.find(o => o.type === 'error');
    expect(error).toBeDefined();
    expect(error!.ename).toBe('ZeroDivisionError');
    expect(error!.evalue).toBe('division by zero');
    expect(error!.traceback).toHaveLength(3);
  });

  it('skips cells without @cell_id', () => {
    const cells = readNotebook(FIXTURE_PATH);

    // The third cell has no @cell_id — it should not appear
    const ids = Array.from(cells.keys());
    expect(ids).not.toContain(undefined);
    expect(ids).toEqual(expect.arrayContaining(['hello', 'setup', 'error-cell']));
    expect(cells.size).toBe(3);
  });

  it('throws on missing file', () => {
    expect(() => readNotebook('/nonexistent/path.ipynb')).toThrow();
  });
});

describe('parseCells', () => {
  it('handles notebook with no cells', () => {
    const cells = parseCells({ cells: [] });
    expect(cells.size).toBe(0);
  });

  it('handles notebook with missing cells key', () => {
    const cells = parseCells({});
    expect(cells.size).toBe(0);
  });

  it('handles source as string instead of array', () => {
    const nb = {
      cells: [
        {
          cell_type: 'code',
          source: '# @cell_id=test\nprint("hello")',
          outputs: [],
        },
      ],
    };
    const cells = parseCells(nb);
    expect(cells.has('test')).toBe(true);
    expect(cells.get('test')!.source).toBe('print("hello")');
  });
});
