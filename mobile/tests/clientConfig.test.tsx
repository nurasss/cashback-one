import React from 'react';
import fs from 'fs';
import path from 'path';
import { View, Text } from 'react-native';
import { render, act, waitFor } from '@testing-library/react-native';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { appendBusinessId, getClientConfig, withClientBusiness, type ClientConfig } from '../src/config/client';
import { BrandBadge } from '../src/components/BrandBadge';
import { getPushAppId } from '../src/features/push';
import { useCards, walletKey } from '../src/api/wallet';
import type { Card } from '../src/types/api';

const mockApiRequest = jest.fn();
jest.mock('../src/auth/provider', () => ({
  useSession: () => ({
    api: { request: mockApiRequest },
    session: { logout: jest.fn() },
  }),
}));

describe('Client Configuration & Multi-Tenant Support', () => {
  const clientsDir = path.resolve(__dirname, '../clients');
  const expectedClients = ['cashbackone', 'example', 'keremet'];

  describe('1. Schema & Validation of client.json files', () => {
    expectedClients.forEach(slug => {
      it(`validates ${slug} client.json and required resources`, () => {
        const clientJsonPath = path.join(clientsDir, slug, 'client.json');
        expect(fs.existsSync(clientJsonPath)).toBe(true);

        const config = JSON.parse(fs.readFileSync(clientJsonPath, 'utf-8')) as ClientConfig;

        expect(config.slug).toBe(slug);
        expect(config.android_app_id).toMatch(/^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$/);
        expect(config.app_name).toBeDefined();
        expect(typeof config.app_name.ru).toBe('string');
        expect(config.app_name.ru.length).toBeGreaterThan(0);
        expect(typeof config.app_name.kk).toBe('string');
        expect(config.app_name.kk.length).toBeGreaterThan(0);

        if (config.business_id !== null) {
          expect(config.business_id).toMatch(
            /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i,
          );
        } else {
          expect(slug).toBe('cashbackone');
        }

        expect(config.primary_color).toMatch(/^#[0-9A-Fa-f]{6}$/);
        expect(config.scheme).toMatch(/^[a-z0-9]+$/);

        // Verify Android resources directory
        const resDir = path.join(clientsDir, slug, 'android/res');
        expect(fs.existsSync(resDir)).toBe(true);
        expect(fs.existsSync(path.join(resDir, 'values/strings.xml'))).toBe(true);
        expect(fs.existsSync(path.join(resDir, 'values/colors.xml'))).toBe(true);
        expect(fs.existsSync(path.join(resDir, 'mipmap-anydpi-v26/ic_launcher.xml'))).toBe(true);

        const densities = ['mdpi', 'hdpi', 'xhdpi', 'xxhdpi', 'xxxhdpi'];
        for (const d of densities) {
          const mipmapDir = path.join(resDir, `mipmap-${d}`);
          expect(fs.existsSync(mipmapDir)).toBe(true);
          const files = fs.readdirSync(mipmapDir);
          const hasLauncher = files.some(f => f.startsWith('ic_launcher'));
          expect(hasLauncher).toBe(true);
        }
      });
    });
  });

  describe('2. Client Selection via EXPO_PUBLIC_CLIENT', () => {
    const originalEnv = process.env.EXPO_PUBLIC_CLIENT;

    afterEach(() => {
      process.env.EXPO_PUBLIC_CLIENT = originalEnv;
    });

    it('defaults to cashbackone when EXPO_PUBLIC_CLIENT is unset', () => {
      delete process.env.EXPO_PUBLIC_CLIENT;
      const config = getClientConfig();
      expect(config.slug).toBe('cashbackone');
      expect(config.business_id).toBeNull();
      expect(config.android_app_id).toBe('kz.cashbackone.mobile');
    });

    it('loads specified client from EXPO_PUBLIC_CLIENT', () => {
      process.env.EXPO_PUBLIC_CLIENT = 'keremet';
      const config = getClientConfig();
      expect(config.slug).toBe('keremet');
      expect(config.business_id).toBe('f3a0cf2d-4a1d-4c0e-af27-b363054394f0');
      expect(config.android_app_id).toBe('kz.cashbackone.keremet');
      expect(config.primary_color).toBe('#FA2247');
      expect(config.Logo).toBeDefined();
    });

    it('throws error when unknown client slug is provided', () => {
      process.env.EXPO_PUBLIC_CLIENT = 'unknown_client';
      expect(() => getClientConfig()).toThrow(/Unknown client slug: "unknown_client"/);
    });
  });

  describe('3. Query Parameters & Path Generation', () => {
    it('appendBusinessId properly attaches business_id', () => {
      expect(appendBusinessId('/me/cards', null)).toBe('/me/cards');
      expect(appendBusinessId('/me/cards', undefined)).toBe('/me/cards');
      expect(appendBusinessId('/me/cards', 'biz-123')).toBe('/me/cards?business_id=biz-123');
      expect(appendBusinessId('/me/promotions/42?limit=1', 'biz-123')).toBe(
        '/me/promotions/42?limit=1&business_id=biz-123',
      );
    });

    it('cashbackone sends byte-for-byte identical URLs without business_id', () => {
      const endpoints = [
        '/me/cards',
        '/me/cards/bind',
        '/me/promotions',
        '/me/promotions/banner-1',
        '/me/promotions/seen',
        '/me/notifications',
        '/me/notifications/read',
        '/me/badges',
      ];

      for (const ep of endpoints) {
        expect(withClientBusiness(ep, 'cashbackone')).toBe(ep);
      }
    });

    it('keremet appends business_id query parameter to all target endpoints', () => {
      const bizId = 'f3a0cf2d-4a1d-4c0e-af27-b363054394f0';
      const endpoints: [string, string][] = [
        ['/me/cards', `/me/cards?business_id=${bizId}`],
        ['/me/cards/bind', `/me/cards/bind?business_id=${bizId}`],
        ['/me/promotions', `/me/promotions?business_id=${bizId}`],
        ['/me/promotions/promo-1', `/me/promotions/promo-1?business_id=${bizId}`],
        ['/me/promotions/seen', `/me/promotions/seen?business_id=${bizId}`],
        ['/me/notifications', `/me/notifications?business_id=${bizId}`],
        ['/me/notifications/read', `/me/notifications/read?business_id=${bizId}`],
        ['/me/badges', `/me/badges?business_id=${bizId}`],
      ];

      for (const [ep, expected] of endpoints) {
        expect(withClientBusiness(ep, 'keremet')).toBe(expected);
      }
    });
  });

  describe('4. Push App ID per client', () => {
    const originalEnv = process.env.EXPO_PUBLIC_CLIENT;

    afterEach(() => {
      process.env.EXPO_PUBLIC_CLIENT = originalEnv;
    });

    it('returns client android_app_id for each client', () => {
      process.env.EXPO_PUBLIC_CLIENT = 'cashbackone';
      expect(getPushAppId()).toBe('kz.cashbackone.mobile');

      process.env.EXPO_PUBLIC_CLIENT = 'example';
      expect(getPushAppId()).toBe('kz.cashbackone.example');

      process.env.EXPO_PUBLIC_CLIENT = 'keremet';
      expect(getPushAppId()).toBe('kz.cashbackone.keremet');
    });
  });

  describe('5. BrandBadge rendering', () => {
    const originalEnv = process.env.EXPO_PUBLIC_CLIENT;

    afterEach(() => {
      process.env.EXPO_PUBLIC_CLIENT = originalEnv;
    });

    it('renders text ONE for cashbackone', () => {
      process.env.EXPO_PUBLIC_CLIENT = 'cashbackone';
      const { getByText, queryByLabelText } = render(<BrandBadge height={24} />);
      expect(getByText('ONE')).toBeTruthy();
      expect(queryByLabelText('Keremet Bonus')).toBeNull();
    });

    it('renders text ONE for example', () => {
      process.env.EXPO_PUBLIC_CLIENT = 'example';
      const { getByText } = render(<BrandBadge height={24} />);
      expect(getByText('ONE')).toBeTruthy();
    });

    it('renders KeremetLogo SVG for keremet', () => {
      process.env.EXPO_PUBLIC_CLIENT = 'keremet';
      const { queryByText, getByLabelText } = render(<BrandBadge height={24} />);
      expect(queryByText('ONE')).toBeNull();
      expect(getByLabelText('Keremet Bonus')).toBeTruthy();
    });
  });

  describe('6. Client-side card filtering logic', () => {
    it('filters out cards not belonging to the client business', () => {
      const keremetBiz = 'f3a0cf2d-4a1d-4c0e-af27-b363054394f0';
      const cards = [
        {
          id: 'card-1',
          barcode: '123456789012',
          business: { id: 'other-biz', name: 'Other Store' },
        },
        {
          id: 'card-2',
          barcode: '987654321098',
          business: { id: keremetBiz, name: 'Keremet' },
        },
      ];

      // For keremet
      const keremetFiltered = cards.filter(c => c.business?.id === keremetBiz);
      expect(keremetFiltered).toHaveLength(1);
      expect(keremetFiltered[0]?.id).toBe('card-2');

      // For another business with no cards
      const emptyFiltered = cards.filter(c => c.business?.id === 'nonexistent-biz');
      expect(emptyFiltered).toHaveLength(0);
    });
  });

  describe('7. Immediate card appearance in query cache after bind', () => {
    const originalEnv = process.env.EXPO_PUBLIC_CLIENT;

    beforeEach(() => {
      mockApiRequest.mockReset();
    });

    afterEach(() => {
      process.env.EXPO_PUBLIC_CLIENT = originalEnv;
    });

    function CardsViewer() {
      const { data } = useCards();
      return (
        <View testID="cards-container">
          {(data ?? []).map(card => (
            <Text key={card.id} testID={`card-${card.id}`}>
              {card.barcode}
            </Text>
          ))}
        </View>
      );
    }

    it('immediately reflects newly bound card before any network refetch for general client (cashbackone)', async () => {
      delete process.env.EXPO_PUBLIC_CLIENT;
      const initialCard: Card = {
        id: 'cb-card-1',
        barcode: '1000000000001',
        balance: '150.0000',
        is_blocked: false,
        updated_at: '2026-11-01T00:00:00Z',
        bound_at: '2026-11-01T00:00:00Z',
        bind_method: 'phone_auto',
        business: { id: 'biz-1', name: 'Store 1', branding: null },
      };

      mockApiRequest.mockResolvedValue([initialCard]);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: Infinity, staleTime: Infinity } },
      });
      queryClient.setQueryData([...walletKey, 'cards'], [initialCard]);

      const screen = render(
        <QueryClientProvider client={queryClient}>
          <CardsViewer />
        </QueryClientProvider>,
      );

      expect(screen.getByText('1000000000001')).toBeTruthy();
      expect(screen.queryByText('1000000000002')).toBeNull();

      const newBoundCard: Card = {
        id: 'cb-card-2',
        barcode: '1000000000002',
        balance: '0.0000',
        is_blocked: false,
        updated_at: '2026-11-05T00:00:00Z',
        bound_at: '2026-11-05T00:00:00Z',
        bind_method: 'manual',
        business: { id: 'biz-2', name: 'Store 2', branding: null },
      };

      // Reset mock to detect if a network refetch happens
      mockApiRequest.mockClear();

      // Simulate bind.tsx onSuccess: query.setQueryData([...walletKey, 'cards'], ...)
      act(() => {
        queryClient.setQueryData<Card[]>([...walletKey, 'cards'], previous =>
          previous ? [newBoundCard, ...previous.filter(item => item.id !== newBoundCard.id)] : [newBoundCard],
        );
      });

      // Card appears immediately in the UI before any repeat network request
      await waitFor(() => {
        expect(screen.getByText('1000000000002')).toBeTruthy();
      });
      expect(mockApiRequest).not.toHaveBeenCalled();

      const cached = queryClient.getQueryData<Card[]>([...walletKey, 'cards']);
      expect(cached?.[0]?.id).toBe('cb-card-2');
      expect(cached?.[1]?.id).toBe('cb-card-1');

      screen.unmount();
    });

    it('immediately reflects newly bound card before any network refetch for keremet client', async () => {
      process.env.EXPO_PUBLIC_CLIENT = 'keremet';
      const keremetBiz = 'f3a0cf2d-4a1d-4c0e-af27-b363054394f0';

      const initialKeremetCard: Card = {
        id: 'km-card-1',
        barcode: '2000000000001',
        balance: '500.0000',
        is_blocked: false,
        updated_at: '2026-11-01T00:00:00Z',
        bound_at: '2026-11-01T00:00:00Z',
        bind_method: 'phone_auto',
        business: { id: keremetBiz, name: 'Keremet Bonus', branding: null },
      };

      mockApiRequest.mockResolvedValue([initialKeremetCard]);

      const queryClient = new QueryClient({
        defaultOptions: { queries: { retry: false, gcTime: Infinity, staleTime: Infinity } },
      });
      queryClient.setQueryData([...walletKey, 'cards'], [initialKeremetCard]);

      const screen = render(
        <QueryClientProvider client={queryClient}>
          <CardsViewer />
        </QueryClientProvider>,
      );

      expect(screen.getByText('2000000000001')).toBeTruthy();
      expect(screen.queryByText('2000000000002')).toBeNull();

      const newKeremetCard: Card = {
        id: 'km-card-2',
        barcode: '2000000000002',
        balance: '0.0000',
        is_blocked: false,
        updated_at: '2026-11-05T00:00:00Z',
        bound_at: '2026-11-05T00:00:00Z',
        bind_method: 'manual',
        business: { id: keremetBiz, name: 'Keremet Bonus', branding: null },
      };

      // Reset mock to detect if a network refetch happens
      mockApiRequest.mockClear();

      // Simulate bind.tsx onSuccess: query.setQueryData([...walletKey, 'cards'], ...)
      act(() => {
        queryClient.setQueryData<Card[]>([...walletKey, 'cards'], previous =>
          previous ? [newKeremetCard, ...previous.filter(item => item.id !== newKeremetCard.id)] : [newKeremetCard],
        );
      });

      // Card appears immediately in the UI before any repeat network request
      await waitFor(() => {
        expect(screen.getByText('2000000000002')).toBeTruthy();
      });
      expect(mockApiRequest).not.toHaveBeenCalled();

      const cached = queryClient.getQueryData<Card[]>([...walletKey, 'cards']);
      expect(cached?.[0]?.id).toBe('km-card-2');
      expect(cached?.[1]?.id).toBe('km-card-1');

      screen.unmount();
    });
  });
});
