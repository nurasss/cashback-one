import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it } from 'vitest';
import { Navigation } from '../src/features/Navigation';

it('only renders scoped links for a business manager', () => {
  render(<MemoryRouter><Navigation role="business_manager" /></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Агенты/ })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Карты и клиенты/ })).toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Бизнесы/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Журнал событий/ })).not.toBeInTheDocument();
});

it('shows Business and Audit navigation only for superadmin', () => {
  render(<MemoryRouter><Navigation role="superadmin" /></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Бизнесы/ })).toBeInTheDocument();
  expect(screen.getByRole('link', { name: /Журнал событий/ })).toBeInTheDocument();
});
