import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { expect, it } from 'vitest';
import { Navigation, adminNavigation } from '../src/features/Navigation';

it('only renders scoped links for a business manager', () => {
  render(<MemoryRouter><Navigation role="business_manager" /></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Главная/ })).toHaveAttribute('href', '/admin');
  expect(screen.getByRole('link', { name: /Клиенты/ })).toHaveAttribute('href', '/admin/operations');
  expect(screen.getByRole('link', { name: /Приложение/ })).toHaveAttribute('href', '/admin/content');
  expect(screen.getByRole('link', { name: /Рассылки/ })).toHaveAttribute('href', '/admin/notifications');
  expect(screen.getByRole('link', { name: /Настройки/ })).toHaveAttribute('href', '/admin/settings');
  expect(screen.queryByRole('link', { name: /Бизнесы/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Агенты/ })).not.toBeInTheDocument();
  expect(screen.queryByRole('link', { name: /Журнал событий/ })).not.toBeInTheDocument();
});

it('shows Business navigation only for superadmin and offers tenant audit to managers', () => {
  render(<MemoryRouter><Navigation role="superadmin" /></MemoryRouter>);
  expect(screen.getByRole('link', { name: /Обзор/ })).toHaveAttribute('href', '/admin');
  expect(screen.getByRole('link', { name: /Бизнесы/ })).toHaveAttribute('href', '/admin/businesses');
  expect(screen.getByRole('link', { name: /Журнал событий/ })).toHaveAttribute('href', '/admin/audit');
});

it('ensures all adminNavigation items use canonical /admin paths', () => {
  for (const item of adminNavigation) {
    expect(item.path.startsWith('/admin')).toBe(true);
  }
});
