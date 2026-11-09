import { createHash } from 'crypto';
import { existsSync, readFileSync } from 'fs';
import { join } from 'path';
import { inflateSync } from 'zlib';

const MOBILE = join(__dirname, '..');
const DENSITIES = { mdpi: 24, hdpi: 36, xhdpi: 48, xxhdpi: 72, xxxhdpi: 96 } as const;

// Minimal decoder for 8-bit RGBA, non-interlaced PNG (what the icons are); enough to inspect the alpha mask.
function readPng(path: string) {
  const data = readFileSync(path);
  expect(data.subarray(0, 8).toString('hex')).toBe('89504e470d0a1a0a');
  let width = 0; let height = 0; let colorType = -1; let bitDepth = 0; let interlace = -1;
  const idat: Buffer[] = [];
  for (let offset = 8; offset < data.length;) {
    const length = data.readUInt32BE(offset);
    const type = data.subarray(offset + 4, offset + 8).toString('latin1');
    const body = data.subarray(offset + 8, offset + 8 + length);
    if (type === 'IHDR') { width = body.readUInt32BE(0); height = body.readUInt32BE(4); bitDepth = body[8]!; colorType = body[9]!; interlace = body[12]!; }
    if (type === 'IDAT') idat.push(body);
    offset += 12 + length;
  }
  expect({ bitDepth, colorType, interlace }).toEqual({ bitDepth: 8, colorType: 6, interlace: 0 });
  const raw = inflateSync(Buffer.concat(idat));
  const stride = width * 4;
  const out = Buffer.alloc(stride * height);
  for (let y = 0; y < height; y++) {
    const filter = raw[y * (stride + 1)]!;
    for (let x = 0; x < stride; x++) {
      const cur = raw[y * (stride + 1) + 1 + x]!;
      const left = x >= 4 ? out[y * stride + x - 4]! : 0;
      const up = y > 0 ? out[(y - 1) * stride + x]! : 0;
      const upLeft = y > 0 && x >= 4 ? out[(y - 1) * stride + x - 4]! : 0;
      let value: number;
      if (filter === 0) value = cur;
      else if (filter === 1) value = cur + left;
      else if (filter === 2) value = cur + up;
      else if (filter === 3) value = cur + ((left + up) >> 1);
      else {
        const p = left + up - upLeft; const pa = Math.abs(p - left); const pb = Math.abs(p - up); const pc = Math.abs(p - upLeft);
        value = cur + (pa <= pb && pa <= pc ? left : pb <= pc ? up : upLeft);
      }
      out[y * stride + x] = value & 255;
    }
  }
  const alpha = (x: number, y: number) => out[y * stride + x * 4 + 3]!;
  const rgb = (x: number, y: number) => [out[y * stride + x * 4]!, out[y * stride + x * 4 + 1]!, out[y * stride + x * 4 + 2]!];
  return { width, height, alpha, rgb };
}

const iconPath = (slug: string, density: string) => join(MOBILE, 'clients', slug, 'android', 'res', `drawable-${density}`, 'notification_icon.png');
const sha = (path: string) => createHash('sha256').update(readFileSync(path)).digest('hex');
function stats(slug: string, density: keyof typeof DENSITIES) {
  const png = readPng(iconPath(slug, density));
  let opaque = 0; let visible = 0; let nonWhite = 0;
  const rowWidth: number[] = [];
  for (let y = 0; y < png.height; y++) {
    let row = 0;
    for (let x = 0; x < png.width; x++) {
      const a = png.alpha(x, y);
      if (a > 0) { visible++; if (png.rgb(x, y).some(c => c !== 255)) nonWhite++; }
      if (a >= 128) { opaque++; row++; }
    }
    rowWidth.push(row);
  }
  const corners = [png.alpha(0, 0), png.alpha(png.width - 1, 0), png.alpha(0, png.height - 1), png.alpha(png.width - 1, png.height - 1)];
  return { png, opaqueShare: opaque / (png.width * png.height), visible, nonWhite, corners, rowWidth };
}

describe.each(['keremet', 'cashbackone'] as const)('push notification icon resources: %s', slug => {
  it.each(Object.entries(DENSITIES))('has a drawable-%s notification_icon of the right size, white on transparent', (density, size) => {
    const { png, nonWhite, corners, visible } = stats(slug, density as keyof typeof DENSITIES);
    expect([png.width, png.height]).toEqual([size, size]);
    expect(visible).toBeGreaterThan(0);
    // Android reads only the alpha: any coloured pixel would be dead weight and means a non-silhouette source image.
    expect(nonWhite).toBe(0);
    expect(corners).toEqual([0, 0, 0, 0]);
  });

  it('is a silhouette, not a solid square or a filled backing plate', () => {
    for (const density of Object.keys(DENSITIES) as (keyof typeof DENSITIES)[]) {
      const { opaqueShare } = stats(slug, density);
      expect(opaqueShare).toBeGreaterThan(0.2);
      expect(opaqueShare).toBeLessThan(0.7);
    }
  });
});

describe('each client uses its own sign', () => {
  it('Keremet and Cashback One have different icons at every density', () => {
    for (const density of Object.keys(DENSITIES)) {
      expect(sha(iconPath('keremet', density))).not.toBe(sha(iconPath('cashbackone', density)));
    }
  });

  it('Keremet is the new "k": a stem on top, with the arms opening below it (the old ONE coin is a filled disc)', () => {
    const { rowWidth, png, opaqueShare } = stats('keremet', 'xxxhdpi');
    const rows = rowWidth.map((width, y) => ({ width, y })).filter(row => row.width > 0);
    const top = rows[0]!.y; const bottom = rows[rows.length - 1]!.y; const height = bottom - top + 1;
    const stemRow = rowWidth[top + Math.round(height * 0.12)]!;
    const middleBand = rowWidth.slice(top + Math.round(height * 0.4), top + Math.round(height * 0.8));
    expect(Math.max(...middleBand)).toBeGreaterThan(stemRow * 1.8);
    // Centred in the canvas with margin, so launchers/ROMs that crop to a circle do not cut it.
    expect(top).toBeGreaterThanOrEqual(Math.floor(png.height * 0.05));
    expect(bottom).toBeLessThanOrEqual(Math.ceil(png.height * 0.95));
    expect(opaqueShare).toBeLessThan(0.5);
  });

  it('Cashback One keeps the existing ONE-coin silhouette: a disc with the lettering cut out', () => {
    const { png } = stats('cashbackone', 'xxxhdpi');
    expect(png.alpha(48, 18)).toBeGreaterThan(200); // upper part of the disc
    expect(png.alpha(48, 78)).toBeGreaterThan(200); // lower part of the disc
    expect(png.alpha(48, 48)).toBeLessThan(40); // the lettering is transparent (cut out)
  });

  it('the accent colour of the small icon follows the client brand', () => {
    const keremetColors = readFileSync(join(MOBILE, 'clients/keremet/android/res/values/colors.xml'), 'utf8');
    const keremetJson = JSON.parse(readFileSync(join(MOBILE, 'clients/keremet/client.json'), 'utf8')) as { primary_color: string };
    expect(keremetColors).toContain(`<color name="notification_icon_color">${keremetJson.primary_color}</color>`);
    const oneColors = readFileSync(join(MOBILE, 'clients/cashbackone/android/res/values/colors.xml'), 'utf8');
    expect(oneColors).toContain('name="notification_icon_color"');
  });
});

describe('how the resource reaches the flavor', () => {
  const gradle = join(MOBILE, 'android/app/build.gradle');
  const manifest = join(MOBILE, 'android/app/src/main/AndroidManifest.xml');

  // mobile/android/ is local-only (git-ignored): these checks run where it exists and are skipped on a clean clone.
  (existsSync(gradle) ? it : it.skip)('each flavor compiles clients/<slug>/android/res as its resource directory (it overrides main/)', () => {
    const text = readFileSync(gradle, 'utf8');
    for (const slug of ['cashbackone', 'keremet']) {
      expect(text).toMatch(new RegExp(`${slug} \\{\\s*res\\.srcDirs = \\[file\\("\\$\\{projectDir\\}/\\.\\./\\.\\./clients/${slug}/android/res"\\)\\]`));
    }
  });

  (existsSync(manifest) ? it : it.skip)('FCM and Expo default notification icons both point at @drawable/notification_icon', () => {
    const text = readFileSync(manifest, 'utf8');
    expect(text).toContain('com.google.firebase.messaging.default_notification_icon" android:resource="@drawable/notification_icon"');
    expect(text).toContain('expo.modules.notifications.default_notification_icon" android:resource="@drawable/notification_icon"');
  });
});
