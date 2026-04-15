import { describe, it, expect } from 'vitest';
import { computeNavigationLine } from '../../navigate';
import type { BlockInfo } from '../../types';

function makeBlock(id: string, startLine: number, endLine: number): BlockInfo {
  return { id, source: '', startLine, endLine };
}

describe('computeNavigationLine', () => {
  // block-one from sample.py: startLine=1, endLine=4
  const blockOne = makeBlock('block-one', 1, 4);

  it('no param → first content line (0-based startLine)', () => {
    expect(computeNavigationLine(blockOne)).toBe(1);
  });

  it('lines=1 → first content line', () => {
    expect(computeNavigationLine(blockOne, '1')).toBe(1);
  });

  it('lines=2 → second content line', () => {
    expect(computeNavigationLine(blockOne, '2')).toBe(2);
  });

  it('lines=5-10 on a block at startLine=10 → line 14', () => {
    const block = makeBlock('big', 10, 30);
    expect(computeNavigationLine(block, '5-10')).toBe(14);
  });

  it('lines=1-1 → first content line', () => {
    expect(computeNavigationLine(blockOne, '1-1')).toBe(1);
  });

  // block-two from sample.py: startLine=6, endLine=9
  const blockTwo = makeBlock('block-two', 6, 9);

  it('different position, no param → 6', () => {
    expect(computeNavigationLine(blockTwo)).toBe(6);
  });

  it('different position, lines=2 → 7', () => {
    expect(computeNavigationLine(blockTwo, '2')).toBe(7);
  });

  it('invalid lines param falls back to content start', () => {
    expect(computeNavigationLine(blockOne, 'abc')).toBe(1);
  });

  it('lines=0 falls back to content start', () => {
    expect(computeNavigationLine(blockOne, '0')).toBe(1);
  });
});
