import { createHash } from 'node:crypto';
import { existsSync, readFileSync } from 'node:fs';
import { expect, it } from 'vitest';
import { publicKk, publicRu } from '../src/i18n/public';

it('offers APK 1.0.10 without JavaScript and uses an absolute social image URL', () => {
  const html = readFileSync('index.html', 'utf8');
  const noscript = html.match(/<noscript>([\s\S]*?)<\/noscript>/)?.[1];
  expect(noscript).toContain('href="/app/cashback-one-1.0.10.apk"');
  expect(noscript).toContain('APK 1.0.10');
  expect(html).not.toContain('cashback-one-1.0.2.apk');
  expect(html).toContain('content="https://cashback-qr.poscenter.kz/logo.png"');
});

it('does not advertise unapproved legal drafts in the sitemap', () => {
  const sitemap = readFileSync('public/sitemap.xml', 'utf8');
  const robots = readFileSync('public/robots.txt', 'utf8');
  expect(sitemap).toContain('<loc>https://cashback-qr.poscenter.kz/</loc>');
  expect(sitemap).not.toMatch(/\/(privacy|terms)</);
  expect(robots).toContain('Disallow: /admin');
  expect(robots).toContain('Disallow: /privacy');
  expect(robots).toContain('Disallow: /terms');
});

it('references content-hashed landing screen images while keeping legacy PNGs intact', () => {
  expect(publicKk.hero.screens.map((s) => s.src)).toEqual(publicRu.hero.screens.map((s) => s.src));
  expect(publicRu.hero.screens).toHaveLength(4);

  for (const screen of publicRu.hero.screens) {
    const match = screen.src.match(/^\/landing\/(screen-[a-z]+)\.([0-9a-f]{8})\.png$/);
    expect(match, `expected content-hashed src for ${screen.id}, got ${screen.src}`).not.toBeNull();
    const [, baseName, shortHash] = match!;
    const hashedFile = `public/landing/${baseName}.${shortHash}.png`;
    const legacyFile = `public/landing/${baseName}.png`;

    expect(existsSync(hashedFile), `${hashedFile} must exist`).toBe(true);
    expect(existsSync(legacyFile), `${legacyFile} must remain on disk`).toBe(true);

    const actualDigest = createHash('sha256').update(readFileSync(hashedFile)).digest('hex');
    expect(actualDigest.slice(0, 8)).toBe(shortHash);
  }
});
