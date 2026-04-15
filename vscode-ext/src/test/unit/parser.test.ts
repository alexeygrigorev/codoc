import { describe, it, expect } from 'vitest';
import { parseTemplate, parseFrontmatter, findDirectives, parseDirectiveParamString } from '../../parser';

describe('parseFrontmatter', () => {
  it('parses frontmatter with notebooks and scripts', () => {
    const content = `---
notebooks:
  - id: nb
    path: data.ipynb
  - id: nb2
    path: ../models.ipynb
    execute: false
scripts:
  - id: sc
    path: utils.py
---

# Title
`;
    const { frontmatter, body, bodyStartLine } = parseFrontmatter(content);

    expect(frontmatter.notebooks).toHaveLength(2);
    expect(frontmatter.notebooks[0]).toEqual({ id: 'nb', path: 'data.ipynb', execute: true });
    expect(frontmatter.notebooks[1]).toEqual({ id: 'nb2', path: '../models.ipynb', execute: false });
    expect(frontmatter.scripts).toHaveLength(1);
    expect(frontmatter.scripts[0]).toEqual({ id: 'sc', path: 'utils.py' });
    expect(bodyStartLine).toBeGreaterThan(0);
    expect(body).toContain('# Title');
  });

  it('handles templates with no frontmatter', () => {
    const content = '# Just a title\n\nSome content.';
    const { frontmatter, body, bodyStartLine } = parseFrontmatter(content);

    expect(frontmatter.notebooks).toEqual([]);
    expect(frontmatter.scripts).toEqual([]);
    expect(bodyStartLine).toBe(0);
    expect(body).toBe(content);
  });

  it('handles empty frontmatter', () => {
    const content = '---\n---\n\n# Title';
    const { frontmatter, body } = parseFrontmatter(content);

    expect(frontmatter.notebooks).toEqual([]);
    expect(frontmatter.scripts).toEqual([]);
    expect(body).toContain('# Title');
  });

  it('handles frontmatter with no closing ---', () => {
    const content = '---\nnotebooks:\n  - id: nb\n    path: x.ipynb';
    const { frontmatter, body, bodyStartLine } = parseFrontmatter(content);

    // No closing --- means no valid frontmatter, treat entire content as body
    expect(bodyStartLine).toBe(0);
    expect(body).toBe(content);
  });

  it('ignores invalid notebook entries', () => {
    const content = `---
notebooks:
  - id: nb
    path: data.ipynb
  - id: ""
    path: missing-id.ipynb
  - path: no-id.ipynb
---

Content.
`;
    const { frontmatter } = parseFrontmatter(content);
    expect(frontmatter.notebooks).toHaveLength(1);
    expect(frontmatter.notebooks[0].id).toBe('nb');
  });

  it('parses image_folder when present', () => {
    const content = `---
notebooks:
  - id: nb
    path: data.ipynb
    image_folder: images
---

Content.
`;
    const { frontmatter } = parseFrontmatter(content);
    expect(frontmatter.notebooks[0].image_folder).toBe('images');
  });
});

describe('findDirectives', () => {
  it('finds @@code directives', () => {
    const body = '\n# Title\n\n@@code nb:hello\n\nSome text.\n';
    const directives = findDirectives(body, 5);

    expect(directives).toHaveLength(1);
    expect(directives[0].type).toBe('code');
    expect(directives[0].sourceId).toBe('nb');
    expect(directives[0].cellId).toBe('hello');
    expect(directives[0].lineNumber).toBe(8); // 5 + 3
  });

  it('finds @@code-output directives', () => {
    const body = '@@code-output nb:setup limit-lines=5\n';
    const directives = findDirectives(body, 0);

    expect(directives).toHaveLength(1);
    expect(directives[0].type).toBe('code-output');
    expect(directives[0].params).toEqual({ 'limit-lines': '5' });
  });

  it('finds @@code-figure directives', () => {
    const body = '@@code-figure nb:plot format=png quality=90\n';
    const directives = findDirectives(body, 0);

    expect(directives).toHaveLength(1);
    expect(directives[0].type).toBe('code-figure');
    expect(directives[0].params).toEqual({ format: 'png', quality: '90' });
  });

  it('extracts multiple params', () => {
    const body = '@@code nb:hello lines=1-17 strip-spaces=4\n';
    const directives = findDirectives(body, 0);

    expect(directives).toHaveLength(1);
    expect(directives[0].params).toEqual({ lines: '1-17', 'strip-spaces': '4' });
  });

  it('handles lines with extra whitespace', () => {
    const body = '  @@code   nb:hello   lines=1-3  \n';
    const directives = findDirectives(body, 0);

    expect(directives).toHaveLength(1);
    expect(directives[0].sourceId).toBe('nb');
    expect(directives[0].cellId).toBe('hello');
  });

  it('ignores malformed directives', () => {
    const body = '@@code\n@@code nb\n@@code nb:\n@@notacode nb:hello\nregular text\n';
    const directives = findDirectives(body, 0);
    expect(directives).toHaveLength(0);
  });

  it('finds multiple directives', () => {
    const body = '@@code nb:a\n\nText.\n\n@@code-output nb:b\n\n@@code sc:c\n';
    const directives = findDirectives(body, 0);
    expect(directives).toHaveLength(3);
    expect(directives.map(d => d.cellId)).toEqual(['a', 'b', 'c']);
  });
});

describe('parseDirectiveParamString', () => {
  it('parses key=value pairs', () => {
    expect(parseDirectiveParamString(' lines=1-17 strip-spaces=4')).toEqual({
      lines: '1-17',
      'strip-spaces': '4',
    });
  });

  it('returns empty for empty string', () => {
    expect(parseDirectiveParamString('')).toEqual({});
  });

  it('returns empty for whitespace only', () => {
    expect(parseDirectiveParamString('   ')).toEqual({});
  });

  it('handles single param', () => {
    expect(parseDirectiveParamString(' limit-lines=5')).toEqual({ 'limit-lines': '5' });
  });
});

describe('parseTemplate', () => {
  it('parses a complete template', () => {
    const content = `---
notebooks:
  - id: nb
    path: sample.ipynb
scripts:
  - id: sc
    path: sample.py
---

# Test Template

@@code nb:hello

Some text.

@@code-output nb:hello limit-lines=2

@@code sc:block-one
`;
    const parsed = parseTemplate(content);

    expect(parsed.frontmatter.notebooks).toHaveLength(1);
    expect(parsed.frontmatter.scripts).toHaveLength(1);
    expect(parsed.directives).toHaveLength(3);
    expect(parsed.directives[0].type).toBe('code');
    expect(parsed.directives[1].type).toBe('code-output');
    expect(parsed.directives[2].type).toBe('code');
    expect(parsed.directives[2].sourceId).toBe('sc');
  });
});
