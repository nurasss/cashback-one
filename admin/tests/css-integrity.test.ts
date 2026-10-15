import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { expect, it } from 'vitest';

// An unclosed block makes browsers nest every following rule inside it and the whole UI renders unstyled.
it('admin stylesheet has balanced braces and a closed :root block', () => {
  const css = readFileSync(resolve(process.cwd(), 'src/styles/admin.css'), 'utf8');
  const open = (css.match(/\{/g) ?? []).length;
  const close = (css.match(/\}/g) ?? []).length;
  expect(open).toBe(close);
  const root = /:root\{([^}]*)\}/.exec(css);
  expect(root?.[1]).toContain('--shadow');
});
