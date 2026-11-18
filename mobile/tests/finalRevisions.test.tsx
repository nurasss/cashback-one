import fs from 'fs';
import path from 'path';
import { act, fireEvent, render, screen } from '@testing-library/react-native';
import type { ReactElement } from 'react';
import { AppState } from 'react-native';
import * as Location from 'expo-location';

import { I18nProvider, type Key } from '../src/i18n';
import { ru } from '../src/i18n/ru';
import { kz } from '../src/i18n/kz';
import { ThemeProvider } from '../src/theme/ThemeProvider';
import { calculateDirectDistance, formatDistance, StatusStoresList } from '../src/features/stores';
import { pointsText, percentText } from '../src/utils/format';
import type { AppStoreItem } from '../src/types/api';

jest.mock('expo-location', () => ({
  getForegroundPermissionsAsync: jest.fn(),
  requestForegroundPermissionsAsync: jest.fn(),
  getCurrentPositionAsync: jest.fn(),
  Accuracy: { Balanced: 3 },
  PermissionStatus: {
    UNDETERMINED: 'undetermined',
    GRANTED: 'granted',
    DENIED: 'denied',
  },
}));

function mount(element: ReactElement, language: 'ru' | 'kz' = 'ru') {
  return render(
    <ThemeProvider initialPreference="light">
      <I18nProvider initial={language}>{element}</I18nProvider>
    </ThemeProvider>,
  );
}

describe('Points and currency formatting without fractional tiyns (Item 3)', () => {
  it('truncates decimals to zero and handles negative values without -0', () => {
    expect(pointsText('0')).toBe('0');
    expect(pointsText('0.99')).toBe('0');
    expect(pointsText('-0.99')).toBe('0');
    expect(pointsText('1234.56')).toBe('1 234');
    expect(pointsText('-1234.56')).toBe('-1 234');
    expect(pointsText('-0.00')).toBe('0');
    expect(pointsText('-0.01')).toBe('0');
    expect(pointsText('0.00')).toBe('0');
  });

  it('preserves full precision for long Decimal values without Number precision loss', () => {
    const longDecimal = '999999999999999999999999.95';
    expect(pointsText(longDecimal)).toBe('999 999 999 999 999 999 999 999');
    const negativeLong = '-999999999999999999999999.95';
    expect(pointsText(negativeLong)).toBe('-999 999 999 999 999 999 999 999');
  });

  it('percentText keeps decimals without automatic rounding', () => {
    expect(percentText('3.5')).toBe('3,5');
    expect(percentText('4.25')).toBe('4,25');
    expect(percentText('2')).toBe('2');
  });

});

describe('Stores list and straight-line distances (Item 4)', () => {
  const mockStores: AppStoreItem[] = [
    {
      id: 'store-1',
      title_ru: 'Супермаркет Керемет 1',
      title_kk: 'Керемет 1 супермаркеті',
      address_ru: 'ул. Достык, 10',
      address_kk: 'Достық к-сі, 10',
      map_url: 'https://maps.example.com/store1',
      sort_order: 1,
      latitude: 43.238949,
      longitude: 76.889709,
    },
    {
      id: 'store-2',
      title_ru: 'Супермаркет Керемет 2',
      title_kk: 'Керемет 2 супермаркеті',
      address_ru: 'пр. Абая, 50',
      address_kk: 'Абай даңғылы, 50',
      map_url: null,
      sort_order: 2,
      latitude: null,
      longitude: null,
    },
  ];

  it('calculates direct distance accurately via Haversine formula', () => {
    // Distance between Almaty points ~813 meters
    const d = calculateDirectDistance(43.238949, 76.889709, 43.238949, 76.899709);
    expect(d).toBeGreaterThan(800);
    expect(d).toBeLessThan(830);

    // Same point is 0
    expect(calculateDirectDistance(43.0, 76.0, 43.0, 76.0)).toBe(0);
  });

  it('formats distance in meters and kilometers correctly', () => {
    const fakeT = (key: Key, params?: Record<string, string | number>) => {
      if (key === 'metersUnit') return `${params?.distance} м`;
      if (key === 'kilometersUnit') return `${params?.distance} км`;
      return String(key);
    };
    expect(formatDistance(350, fakeT)).toBe('350 м');
    expect(formatDistance(1200, fakeT)).toBe('1.2 км');
    expect(formatDistance(2000, fakeT)).toBe('2 км');
  });

  it('renders stores list with direct distance when coordinates available', () => {
    const userCoords = { latitude: 43.238949, longitude: 76.899709 };
    mount(<StatusStoresList stores={mockStores} language="ru" userCoords={userCoords} />);

    expect(screen.getByText('Супермаркет Керемет 1')).toBeTruthy();
    expect(screen.getByText('ул. Достык, 10')).toBeTruthy();
    // store-1 has coordinates, distance should be calculated
    expect(screen.getByTestId('store-distance-store-1').props.children).toContain('По прямой:');
    expect(screen.getByTestId('store-distance-store-1').props.children).toContain('м');

    // store-2 has no coordinates: it says so, and never shows an invented distance
    expect(screen.getByText('Супермаркет Керемет 2')).toBeTruthy();
    expect(screen.getByTestId('store-distance-store-2').props.children).toContain('Координаты магазина не указаны');
  });

  it('renders "Расстояние недоступно" when user coordinates are not available', () => {
    mount(<StatusStoresList stores={mockStores} language="ru" userCoords={null} />);
    expect(screen.getByTestId('store-distance-store-1').props.children).toContain('Расстояние недоступно');
    expect(screen.getByTestId('store-distance-store-2').props.children).toContain('Координаты магазина не указаны');
  });

  it('opens map_url when store item is tapped', () => {
    const onOpenMap = jest.fn();
    mount(<StatusStoresList stores={mockStores} language="ru" onOpenMap={onOpenMap} />);
    fireEvent.press(screen.getByTestId('status-store-item-store-1'));
    expect(onOpenMap).toHaveBeenCalledWith('https://maps.example.com/store1');
  });

  it('renders Kazakh translations correctly', () => {
    mount(<StatusStoresList stores={mockStores} language="kz" userCoords={null} />, 'kz');
    expect(screen.getByText('Керемет 1 супермаркеті')).toBeTruthy();
    expect(screen.getByText('Достық к-сі, 10')).toBeTruthy();
    expect(screen.getByTestId('store-distance-store-1').props.children).toContain('Тікелей бойынша: Қашықтық қолжетімді емес');
  });

  describe('Coordinate math stability and edge cases', () => {
    it('returns exact 0 for identical coordinates and formats as 0 м', () => {
      const dist = calculateDirectDistance(43.238949, 76.889709, 43.238949, 76.889709);
      expect(dist).toBe(0);
      const fakeT = (key: Key, params?: Record<string, string | number>) =>
        key === 'metersUnit' ? `${params?.distance} м` : String(key);
      expect(formatDistance(0, fakeT)).toBe('0 м');
    });

    it('handles antipodes and poles cleanly without NaN', () => {
      // Antipodes on equator
      const antipodalDist = calculateDirectDistance(0, 0, 0, 180);
      expect(antipodalDist).not.toBeNull();
      expect(Number.isFinite(antipodalDist)).toBe(true);
      expect(antipodalDist).toBeGreaterThan(19_000_000);

      // North pole to South pole
      const poleDist = calculateDirectDistance(90, 0, -90, 0);
      expect(poleDist).not.toBeNull();
      expect(Number.isFinite(poleDist)).toBe(true);
      expect(poleDist).toBeGreaterThan(19_000_000);
    });

    it('rejects out of bounds and non-finite coordinates with null and safe format fallback', () => {
      expect(calculateDirectDistance(95, 0, 43, 76)).toBeNull();
      expect(calculateDirectDistance(-95, 0, 43, 76)).toBeNull();
      expect(calculateDirectDistance(43, 185, 43, 76)).toBeNull();
      expect(calculateDirectDistance(43, -185, 43, 76)).toBeNull();
      expect(calculateDirectDistance(NaN, 0, 43, 76)).toBeNull();
      expect(calculateDirectDistance(43, Infinity, 43, 76)).toBeNull();

      const fakeT = (key: Key) => String(key);
      expect(formatDistance(NaN, fakeT)).toBe('distanceUnavailable');
      expect(formatDistance(-5, fakeT)).toBe('distanceUnavailable');
    });
  });

  describe('Foreground geolocation flow and button states', () => {
    const originalAppState = AppState.currentState;
    beforeEach(() => {
      (AppState as { currentState: typeof AppState.currentState }).currentState = 'active';
    });
    afterEach(() => {
      (AppState as { currentState: typeof AppState.currentState }).currentState = originalAppState;
      jest.restoreAllMocks();
    });

    it('requests foreground permission and updates distances on grant', async () => {
      (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: Location.PermissionStatus.UNDETERMINED,
        granted: false,
        canAskAgain: true,
        expires: 'never',
      });
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: Location.PermissionStatus.GRANTED,
        granted: true,
        canAskAgain: true,
        expires: 'never',
      });
      (Location.getCurrentPositionAsync as jest.Mock).mockResolvedValue({
        coords: {
          latitude: 43.238949,
          longitude: 76.889709,
          altitude: 0,
          accuracy: 10,
          altitudeAccuracy: 0,
          heading: 0,
          speed: 0,
        },
        timestamp: Date.now(),
      });

      mount(<StatusStoresList stores={mockStores} language="ru" />);
      expect(screen.getByTestId('show-distances-button')).toBeTruthy();
      // Since 2026-11-17 the position is requested when the screen opens: no tap on "Показать расстояния" is needed.
      expect(screen.getByLabelText('Определяем геопозицию…')).toBeTruthy();
      await act(async () => {
        await Promise.resolve();
      });

      expect(Location.requestForegroundPermissionsAsync).toHaveBeenCalledTimes(1);
      expect(Location.getCurrentPositionAsync).toHaveBeenCalled();
      // Distance should now be shown for store-1
      expect(screen.getByTestId('store-distance-store-1').props.children).toContain('По прямой: 0 м');
      // Button should now show "Обновить расстояния"
      expect(screen.getByText('Обновить расстояния')).toBeTruthy();
    });

    it('displays notice when permission is denied and leaves distances unavailable', async () => {
      (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: Location.PermissionStatus.DENIED,
        granted: false,
        canAskAgain: false,
        expires: 'never',
      });
      (Location.requestForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: Location.PermissionStatus.DENIED,
        granted: false,
        canAskAgain: false,
        expires: 'never',
      });

      mount(<StatusStoresList stores={mockStores} language="ru" />);
      const btn = screen.getByTestId('show-distances-button');

      await act(async () => {
        fireEvent.press(btn);
      });

      expect(screen.getByTestId('location-denied-note')).toBeTruthy();
      expect(screen.getByText('Доступ к геопозиции отключён')).toBeTruthy();
      expect(screen.getByTestId('store-distance-store-1').props.children).toContain('Расстояние недоступно');
    });

    it('handles location timeout gracefully without crashing', async () => {
      (Location.getForegroundPermissionsAsync as jest.Mock).mockResolvedValue({
        status: Location.PermissionStatus.GRANTED,
        granted: true,
        canAskAgain: true,
        expires: 'never',
      });
      (Location.getCurrentPositionAsync as jest.Mock).mockRejectedValue(new Error('LOCATION_TIMEOUT'));

      mount(<StatusStoresList stores={mockStores} language="ru" />);
      const btn = screen.getByTestId('show-distances-button');

      await act(async () => {
        fireEvent.press(btn);
      });

      // Does not crash; distance remains unavailable and the reason is shown (it is no longer swallowed silently)
      expect(screen.getByTestId('store-distance-store-1').props.children).toContain('Расстояние недоступно');
      expect(screen.getByTestId('location-failure-note')).toBeTruthy();
    });
  });
});

describe('Terminology: «Бонусы» in RU texts (Item 1)', () => {
  it('uses «Бонусы» in pointsSum and related keys', () => {
    expect(ru.pointsSum).toBe('Сумма бонусов');
    expect(ru.dontMiss).toContain('бонусов');
    expect(ru.storeNoteDefaultLead).toContain('бонусы');
    expect(ru.offerHitsDiscountBody).toContain('скидок / бонусов');
    expect(ru.offerCardBonusBody).toContain('скидок / бонусов');
    expect(ru.howToLead).toContain('бонусов');
    expect(ru.howToLead).not.toMatch(/прикинуть|калькулятор/i);
    expect(ru.enableNotificationsPrompt).toContain('бонусы');
    expect(ru.statusLeadLifetime).toContain('бонусы');
  });

  it('does not corrupt Kazakh keys', () => {
    expect(kz.pointsSum).toBe('Бонустар сомасы');
    expect(kz.whereToSpendBonuses).toBe('Бонустарымды қайда жұмсай аламын?');
    expect(kz.ourStores).toBe('Біздің дүкендер');
    expect(kz.howToLead).not.toMatch(/есептеуге/i);
  });
});

describe('Navigation straight to stores section (Item 2)', () => {
  it('home link points directly to status with section=stores parameter', () => {
    // Check that home screen where-to-spend link targets /status with section: 'stores'
    const indexSource = fs.readFileSync(
      path.join(__dirname, '../app/(app)/(tabs)/index.tsx'),
      'utf8',
    );
    expect(indexSource).toContain('testID="where-to-spend-link"');
    expect(indexSource).toContain('onPress={openStores}');
    expect(indexSource).toContain("params: { section: 'stores', at: String(now) }");
  });

  it('status screen registers onLayout scroll to stores when section=stores is requested', () => {
    const statusSource = fs.readFileSync(
      path.join(__dirname, '../app/(app)/status.tsx'),
      'utf8',
    );
    // The scroll logic lives in useScrollToStores (behaviour is tested in storesLink.test.tsx); the screens wire it to a view that is a
    // direct child of the scroll content, because the y from onLayout is relative to the parent.
    const hookSource = fs.readFileSync(path.join(__dirname, '../src/features/useScrollToStores.ts'), 'utf8');
    expect(hookSource).toContain("section !== 'stores'");
    expect(hookSource).toContain('scrollRef.current?.scrollTo');
    expect(statusSource).toContain('useScrollToStores(section, at)');
    expect(statusSource.match(/<View testID="stores-section" onLayout=\{onStoresLayout\}>/g)).toHaveLength(2);
    expect(statusSource).not.toContain('handleStoresLayout');
  });
});
