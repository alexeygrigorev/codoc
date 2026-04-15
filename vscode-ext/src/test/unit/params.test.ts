import { describe, it, expect } from 'vitest';
import { parseDirectiveParams, applyDirectiveParams } from '../../params';

describe('parseDirectiveParams', () => {
  it('parses key=value pairs', () => {
    expect(parseDirectiveParams('lines=5-10 strip-spaces=4')).toEqual({
      lines: '5-10',
      'strip-spaces': '4',
    });
  });

  it('returns empty for empty string', () => {
    expect(parseDirectiveParams('')).toEqual({});
  });

  it('returns empty for whitespace only', () => {
    expect(parseDirectiveParams('   ')).toEqual({});
  });

  it('handles single param', () => {
    expect(parseDirectiveParams('limit-lines=3')).toEqual({ 'limit-lines': '3' });
  });

  it('handles param with complex value', () => {
    expect(parseDirectiveParams('lines=1-17')).toEqual({ lines: '1-17' });
  });
});

describe('applyDirectiveParams - code', () => {
  const source = 'line 1\nline 2\nline 3\nline 4\nline 5';

  it('lines=5-10 extracts correct range (1-based inclusive)', () => {
    const text = 'a\nb\nc\nd\ne\nf\ng\nh\ni\nj';
    const result = applyDirectiveParams(text, { lines: '5-10' }, 'code');
    expect(result).toBe('e\nf\ng\nh\ni\nj');
  });

  it('lines=5 extracts a single line', () => {
    const result = applyDirectiveParams(source, { lines: '5' }, 'code');
    expect(result).toBe('line 5');
  });

  it('lines=2-4 extracts middle lines', () => {
    const result = applyDirectiveParams(source, { lines: '2-4' }, 'code');
    expect(result).toBe('line 2\nline 3\nline 4');
  });

  it('strip-spaces=4 removes leading spaces', () => {
    const text = '    indented\n        double\n  partial\nnone';
    const result = applyDirectiveParams(text, { 'strip-spaces': '4' }, 'code');
    expect(result).toBe('indented\n    double\npartial\nnone');
  });

  it('strip-spaces does not remove more spaces than exist', () => {
    const text = '  two\n    four';
    const result = applyDirectiveParams(text, { 'strip-spaces': '4' }, 'code');
    expect(result).toBe('two\nfour');
  });

  it('combined: lines + strip-spaces applies in order', () => {
    const text = '    a\n    b\n    c\n    d\n    e';
    const result = applyDirectiveParams(text, { lines: '2-4', 'strip-spaces': '4' }, 'code');
    expect(result).toBe('b\nc\nd');
  });

  it('returns original text with no params', () => {
    expect(applyDirectiveParams(source, {}, 'code')).toBe(source);
  });

  it('returns original text with empty params', () => {
    expect(applyDirectiveParams(source, {}, 'code')).toBe(source);
  });
});

describe('applyDirectiveParams - output', () => {
  const output = 'line 1\nline 2\nline 3\nline 4\nline 5';

  it('limit-lines=3 truncates with ...', () => {
    const result = applyDirectiveParams(output, { 'limit-lines': '3' }, 'output');
    expect(result).toBe('line 1\nline 2\nline 3\n...');
  });

  it('limit-lines does not truncate if within limit', () => {
    const result = applyDirectiveParams(output, { 'limit-lines': '10' }, 'output');
    expect(result).toBe(output);
  });

  it('limit-chars=14 truncates with ...', () => {
    // "line 1\nline 2\n" is 14 chars — truncation happens right at the newline
    const result = applyDirectiveParams(output, { 'limit-chars': '14' }, 'output');
    expect(result).toBe('line 1\nline 2\n...');
  });

  it('limit-chars does not truncate if within limit', () => {
    const result = applyDirectiveParams(output, { 'limit-chars': '1000' }, 'output');
    expect(result).toBe(output);
  });

  it('returns original text with no params', () => {
    expect(applyDirectiveParams(output, {}, 'output')).toBe(output);
  });

  it('handles empty text', () => {
    expect(applyDirectiveParams('', { 'limit-lines': '3' }, 'output')).toBe('');
  });
});
