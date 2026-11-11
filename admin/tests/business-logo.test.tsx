import { fireEvent, render } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { AccountAvatar } from '../src/layout/AdminLayout';
import { resolveBusinessLogoSource } from '../src/utils/businessLogo';

describe('business logos', () => {
  it('accepts HTTPS URLs and same-origin relative URLs but rejects external HTTP', () => {
    expect(resolveBusinessLogoSource('https://cdn.example.test/logo.webp')).toEqual({
      ok: true,
      src: 'https://cdn.example.test/logo.webp',
    });
    expect(resolveBusinessLogoSource('/media/logo.webp')).toEqual({
      ok: true,
      src: `${window.location.origin}/media/logo.webp`,
    });
    expect(resolveBusinessLogoSource('http://cdn.example.test/logo.webp')).toEqual({
      ok: false,
      reason: 'https',
    });
  });

  it('shows the business logo and falls back to the login initial if it fails to load', () => {
    const { container, rerender } = render(
      <AccountAvatar login="manager@keremet" logoUrl="https://cdn.example.test/logo.webp" />,
    );
    const image = container.querySelector('img');
    expect(image?.getAttribute('src')).toBe('https://cdn.example.test/logo.webp');
    expect(image).toHaveStyle({ objectFit: 'contain' });

    fireEvent.error(image!);
    expect(container.querySelector('img')).toBeNull();
    expect(container.textContent).toBe('M');

    rerender(<AccountAvatar login="manager@keremet" logoUrl="http://cdn.example.test/logo.webp" />);
    expect(container.querySelector('img')).toBeNull();
    expect(container.textContent).toBe('M');
  });
});
