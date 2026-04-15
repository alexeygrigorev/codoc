import { describe, it, expect } from 'vitest';
import * as path from 'path';
import { hasNobookMarkers, parseNobookBlocks, readNobook, readNobookBlocks } from '../../nobook';

const FIXTURE_PATH = path.resolve(__dirname, '..', 'fixtures', 'sample-nobook.py');

describe('nobook', () => {
  it('detects nobook markers', () => {
    expect(hasNobookMarkers('# @block=setup\nprint("x")\n')).toBe(true);
    expect(hasNobookMarkers('print("plain python")\n')).toBe(false);
  });

  it('reads nobook blocks with line information', () => {
    const blocks = readNobookBlocks(FIXTURE_PATH);

    expect(blocks.size).toBe(2);
    expect(blocks.get('setup')?.startLine).toBe(1);
    expect(blocks.get('show')?.startLine).toBe(4);
    expect(blocks.get('show')?.source).toContain('print(message)');
  });

  it('parses nobook blocks from inline content', () => {
    const blocks = parseNobookBlocks('# @block=a\nx = 1\n# @block=b\nprint(x)\n');

    expect(blocks.get('a')?.source).toBe('x = 1');
    expect(blocks.get('b')?.source).toBe('print(x)');
  });

  it('loads nobook outputs from sibling .out.py', () => {
    const cells = readNobook(FIXTURE_PATH);
    const show = cells.get('show');

    expect(show).toBeDefined();
    expect(show?.source).toContain('print(message)');
    expect(show?.output[0]?.type).toBe('stream');
    expect(show?.output[0]?.text).toContain('hello from nobook');
  });
});
