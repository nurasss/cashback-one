import { readFileSync } from 'node:fs';
import { expect, it } from 'vitest';

it('offers APK 1.0.3 without JavaScript and uses an absolute social image URL', () => {
  const html = readFileSync('index.html', 'utf8');
  const noscript = html.match(/<noscript>([\s\S]*?)<\/noscript>/)?.[1];
  expect(noscript).toContain('href="/app/cashback-one-1.0.3.apk"');
  expect(noscript).toContain('APK 1.0.3');
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
