import * as Location from 'expo-location';
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from 'react';
import { ActivityIndicator, Alert, AppState, type AppStateStatus, StyleSheet, Text, View } from 'react-native';
import { Icon } from '../components/icons';
import { PressScale } from '../components/motion';
import { useI18n, type Key, type Language } from '../i18n';
import { openMapUrl } from './mapLink';
import { fonts, type Colors } from '../theme';
import { useTheme, useThemedStyles } from '../theme/ThemeProvider';
import type { AppStoreItem } from '../types/api';

/**
 * Calculates straight-line distance in meters between two lat/lon coordinates
 * using the Haversine formula.
 * Validates ranges: lat in [-90, 90], lon in [-180, 180]. Clamps 'a' in [0, 1]
 * to prevent NaN from precision limits or antipodes. Returns null on invalid inputs.
 */
export function calculateDirectDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number,
): number | null {
  if (
    typeof lat1 !== 'number' ||
    typeof lon1 !== 'number' ||
    typeof lat2 !== 'number' ||
    typeof lon2 !== 'number' ||
    !Number.isFinite(lat1) ||
    !Number.isFinite(lon1) ||
    !Number.isFinite(lat2) ||
    !Number.isFinite(lon2)
  ) {
    return null;
  }
  if (lat1 < -90 || lat1 > 90 || lat2 < -90 || lat2 > 90) {
    return null;
  }
  if (lon1 < -180 || lon1 > 180 || lon2 < -180 || lon2 > 180) {
    return null;
  }
  const R = 6371e3; // Earth's mean radius in meters
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const sinDlat2 = Math.sin(dLat / 2);
  const sinDlon2 = Math.sin(dLon / 2);
  const rawA =
    sinDlat2 * sinDlat2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * sinDlon2 * sinDlon2;
  // Clamped in [0, 1] to avoid NaN at antipodal points or numerical rounding
  const a = Math.max(0, Math.min(1, rawA));
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  const res = Math.round(R * c);
  return Number.isFinite(res) ? Math.max(0, res) : null;
}

/**
 * Formats distance in meters or kilometers.
 * Allows 0 m; returns distanceUnavailable on non-finite or negative distances.
 */
export function formatDistance(
  meters: number,
  t: (key: Key, params?: Record<string, string | number>) => string,
): string {
  if (!Number.isFinite(meters) || meters < 0) {
    return t('distanceUnavailable');
  }
  if (meters < 1000) {
    return t('metersUnit', { distance: String(Math.max(0, Math.round(meters))) });
  }
  const km = (meters / 1000).toFixed(1).replace(/\.0$/, '');
  return t('kilometersUnit', { distance: km });
}

export interface UserCoordinates {
  latitude: number;
  longitude: number;
}

export interface StatusStoresListProps {
  stores?: AppStoreItem[] | null;
  language: Language;
  userCoords?: UserCoordinates | null;
  userCoordsTimestamp?: number | null;
  onOpenMap?: (url: string) => void;
  onLocationRequested?: () => void;
}

const LOCATION_TIMEOUT_MS = 10000;
// A fix this recent is good enough for a "distance in a straight line" figure when a fresh one cannot be obtained in time.
const LAST_KNOWN_MAX_AGE_MS = 5 * 60 * 1000;
// The fallback read and the services check are quick local lookups; neither may keep the spinner on if the system never answers.
// The permission dialog is NOT bounded by these limits: it waits for the person as long as they need.
const LAST_KNOWN_TIMEOUT_MS = 2000;
const SERVICES_CHECK_TIMEOUT_MS = 3000;
// Re-request automatically only after the user has been away from the active app for at least 30 minutes.
export const ABSENCE_REFRESH_MS = 30 * 60 * 1000;

function pluralKey<K extends Key>(n: number, one: K, few: K, many: K): K {
  const mod100 = n % 100;
  const mod10 = n % 10;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few;
  return many;
}

export function formatLocationUpdatedAgo(
  timestamp: number,
  now: number,
  t: (key: Key, params?: Record<string, string | number>) => string,
): string {
  const diffMs = Math.max(0, now - timestamp);
  if (diffMs < 60_000) {
    return t('locationUpdatedJustNow');
  }
  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) {
    return t(
      pluralKey(minutes, 'locationUpdatedMinuteOne', 'locationUpdatedMinuteFew', 'locationUpdatedMinuteMany'),
      { count: minutes },
    );
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return t(
      pluralKey(hours, 'locationUpdatedHourOne', 'locationUpdatedHourFew', 'locationUpdatedHourMany'),
      { count: hours },
    );
  }
  const days = Math.floor(hours / 24);
  return t(
    pluralKey(days, 'locationUpdatedDayOne', 'locationUpdatedDayFew', 'locationUpdatedDayMany'),
    { count: days },
  );
}

// Resolves with the value of `work`, or with `fallback` when it rejects or does not settle within `ms`. The timer is always cleared,
// and a late result is ignored (its rejection is swallowed so it cannot surface as an unhandled rejection).
async function settleWithin<T>(work: PromiseLike<T> | T, ms: number, fallback: T): Promise<T> {
  let timer: ReturnType<typeof setTimeout> | null = null;
  const guarded = Promise.resolve(work).catch(() => fallback);
  try {
    return await Promise.race([
      guarded,
      new Promise<T>(resolve => {
        timer = setTimeout(() => resolve(fallback), ms);
      }),
    ]);
  } finally {
    if (timer) clearTimeout(timer);
  }
}

export type LocationFailure = 'denied' | 'services-off' | 'timeout' | 'error';
export type LocateOutcome =
  | { ok: true; coords: UserCoordinates; timestamp: number }
  | { ok: false; failure: LocationFailure; canAskAgain?: boolean };

const isFiniteNumber = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value);

// A store has usable coordinates only when both are finite numbers inside the valid ranges.
export function hasStoreCoordinates(store: Pick<AppStoreItem, 'latitude' | 'longitude'>): boolean {
  const { latitude, longitude } = store;
  return isFiniteNumber(latitude) && isFiniteNumber(longitude) && Math.abs(latitude) <= 90 && Math.abs(longitude) <= 180;
}

function toUserCoordinates(position: { coords?: { latitude?: unknown; longitude?: unknown } } | null | undefined): UserCoordinates | null {
  const latitude = position?.coords?.latitude;
  const longitude = position?.coords?.longitude;
  if (!isFiniteNumber(latitude) || !isFiniteNumber(longitude) || Math.abs(latitude) > 90 || Math.abs(longitude) > 180) return null;
  return { latitude, longitude };
}

function resolvePositionTimestamp(position: { timestamp?: unknown } | null | undefined, now: number = Date.now()): number {
  const ts = position?.timestamp;
  if (typeof ts === 'number' && Number.isFinite(ts) && ts > 0) {
    return Math.min(ts, now);
  }
  return now;
}

function failureFromError(error: unknown): LocationFailure {
  const code = typeof (error as { code?: unknown } | null)?.code === 'string' ? ((error as { code: string }).code) : '';
  const message = error instanceof Error ? error.message : '';
  if (/SERVICES_DISABLED|SETTINGS_UNSATISFIED|PROVIDER/i.test(code) || /services? (are |is )?disabled/i.test(message)) return 'services-off';
  if (/TIMEOUT|TIMED_OUT/i.test(code) || message === 'LOCATION_TIMEOUT') return 'timeout';
  return 'error';
}

// Foreground-only: permission is asked while the app is open, the position is read once and stays on the phone.
// Every outcome is returned, never swallowed, so the screen can say why no distance appeared.
// `automatic` is the attempt made without a tap: it may show the system permission dialog only while the answer is still
// "undetermined"; after a refusal it never asks again (the person decides through the button or the phone settings).
export async function locateForeground(
  timeoutMs: number = LOCATION_TIMEOUT_MS,
  lastKnownTimeoutMs: number = LAST_KNOWN_TIMEOUT_MS,
  automatic: boolean = false,
  onPermissionDialogChange?: (open: boolean) => void,
): Promise<LocateOutcome> {
  let permission = await Location.getForegroundPermissionsAsync().catch(() => null);
  if (!permission || permission.status !== 'granted') {
    const mayAsk = !automatic || (permission?.status === 'undetermined' && permission.canAskAgain !== false);
    if (mayAsk) {
      onPermissionDialogChange?.(true);
      try {
        permission = await Location.requestForegroundPermissionsAsync().catch(() => null);
      } finally {
        onPermissionDialogChange?.(false);
      }
    }
  }
  if (!permission || permission.status !== 'granted') {
    return { ok: false, failure: 'denied', canAskAgain: permission?.canAskAgain !== false };
  }

  if (typeof Location.hasServicesEnabledAsync === 'function') {
    // No answer in time means "unknown": carry on, the position request below has its own limit and will report a real failure.
    const enabled = await settleWithin<boolean>(Location.hasServicesEnabledAsync(), SERVICES_CHECK_TIMEOUT_MS, true);
    if (enabled === false) return { ok: false, failure: 'services-off' };
  }

  let failure: LocationFailure = 'error';
  let timer: ReturnType<typeof setTimeout> | null = null;
  try {
    const current = Promise.resolve(Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced }));
    current.catch(() => undefined); // a late result after the timeout must not become an unhandled rejection
    const timeout = new Promise<never>((_, reject) => {
      timer = setTimeout(() => reject(new Error('LOCATION_TIMEOUT')), timeoutMs);
    });
    const position = await Promise.race([current, timeout]);
    const coords = toUserCoordinates(position);
    if (coords) return { ok: true, coords, timestamp: resolvePositionTimestamp(position) };
  } catch (error) {
    failure = failureFromError(error);
  } finally {
    if (timer) clearTimeout(timer);
  }
  if (failure === 'services-off') return { ok: false, failure };

  // No fresh fix: a recent last known one is acceptable; otherwise report the reason.
  if (typeof Location.getLastKnownPositionAsync === 'function') {
    const lastPosition = await settleWithin<Awaited<ReturnType<typeof Location.getLastKnownPositionAsync>>>(
      Location.getLastKnownPositionAsync({ maxAge: LAST_KNOWN_MAX_AGE_MS }),
      lastKnownTimeoutMs,
      null,
    );
    const last = toUserCoordinates(lastPosition);
    if (last) return { ok: true, coords: last, timestamp: resolvePositionTimestamp(lastPosition) };
  }
  return { ok: false, failure };
}

interface StoreLocationState {
  coords: UserCoordinates | null;
  coordsTimestamp: number | null;
  loadingLocation: boolean;
  failure: { reason: LocationFailure; canAskAgain: boolean } | null;
  requestManualLocation: () => void;
}

export const StoreLocationContext = createContext<StoreLocationState | null>(null);

function useStoreLocationController({
  authenticated,
  sessionKey,
  stores,
  disabled = false,
}: {
  authenticated: boolean;
  sessionKey: string;
  stores?: AppStoreItem[] | null;
  disabled?: boolean;
}): StoreLocationState {
  const [coords, setCoords] = useState<UserCoordinates | null>(null);
  const [coordsTimestamp, setCoordsTimestamp] = useState<number | null>(null);
  const [loadingLocation, setLoadingLocation] = useState(false);
  const [failure, setFailure] = useState<{ reason: LocationFailure; canAskAgain: boolean } | null>(null);
  const [appActive, setAppActive] = useState<boolean>(() => AppState.currentState === 'active');
  const mountedRef = useRef(true);
  const requestRef = useRef(0);
  const sessionEpochRef = useRef(0);
  const inFlightRef = useRef(false);
  const autoAttemptedRef = useRef(false);
  const askingPermissionRef = useRef(false);
  const leftActiveAtRef = useRef<number | null>(null);
  const appStateRef = useRef<AppStateStatus>(AppState.currentState);

  const anyStoreHasCoordinates = (stores ?? []).some(hasStoreCoordinates);
  const authenticatedRef = useRef(authenticated);
  authenticatedRef.current = authenticated;
  const hasCoordsRef = useRef(anyStoreHasCoordinates);
  hasCoordsRef.current = anyStoreHasCoordinates;

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const sessionIdentity = authenticated ? sessionKey : '__unauthenticated__';
  useEffect(() => {
    sessionEpochRef.current += 1;
    requestRef.current += 1;
    inFlightRef.current = false;
    autoAttemptedRef.current = false;
    askingPermissionRef.current = false;
    leftActiveAtRef.current = null;
    setCoords(null);
    setCoordsTimestamp(null);
    setFailure(null);
    setLoadingLocation(false);
  }, [sessionIdentity]);

  const locate = useCallback(async (automatic: boolean) => {
    if (disabled || !authenticatedRef.current || inFlightRef.current) return;
    const requestId = ++requestRef.current;
    const requestSessionEpoch = sessionEpochRef.current;
    inFlightRef.current = true;
    setFailure(null);
    setLoadingLocation(true);
    let outcome: LocateOutcome;
    try {
      outcome = await locateForeground(undefined, undefined, automatic, open => {
        askingPermissionRef.current = open;
        if (open) {
          leftActiveAtRef.current = null;
        }
      });
    } catch {
      outcome = { ok: false, failure: 'error' };
    }
    if (
      !mountedRef.current ||
      requestRef.current !== requestId ||
      sessionEpochRef.current !== requestSessionEpoch
    ) {
      return;
    }
    inFlightRef.current = false;
    askingPermissionRef.current = false;
    if (outcome.ok) {
      setCoords(outcome.coords);
      setCoordsTimestamp(outcome.timestamp);
    } else {
      if (outcome.failure === 'denied') {
        // Permission revoked or denied: hide coordinates and distances.
        setCoords(null);
        setCoordsTimestamp(null);
      }
      setFailure({ reason: outcome.failure, canAskAgain: outcome.canAskAgain !== false });
    }
    setLoadingLocation(false);
  }, [disabled]);

  const requestManualLocation = useCallback(() => {
    void locate(false);
  }, [locate]);

  // Automatic attempt once per session, only while the app is active, after session is ready and stores have valid coordinates.
  useEffect(() => {
    if (disabled || !authenticated || !anyStoreHasCoordinates || !appActive || autoAttemptedRef.current) return;
    autoAttemptedRef.current = true;
    void locate(true);
  }, [disabled, authenticated, anyStoreHasCoordinates, appActive, sessionIdentity, locate]);

  // Return to active app: no automatic request if absent < 30 minutes; one automatic attempt if absent >= 30 minutes.
  useEffect(() => {
    if (disabled) return undefined;
    const sub = AppState.addEventListener('change', nextState => {
      const prevState = appStateRef.current;
      appStateRef.current = nextState;
      setAppActive(nextState === 'active');

      if (askingPermissionRef.current) {
        // Returning from the system permission dialog does not count as leaving/returning to the app.
        leftActiveAtRef.current = null;
        return;
      }

      if (nextState !== 'active') {
        if (prevState === 'active' || leftActiveAtRef.current === null) {
          leftActiveAtRef.current = Date.now();
        }
        return;
      }

      const leftAt = leftActiveAtRef.current;
      leftActiveAtRef.current = null;
      if (
        !autoAttemptedRef.current ||
        leftAt === null ||
        !authenticatedRef.current ||
        !hasCoordsRef.current ||
        inFlightRef.current
      ) {
        return;
      }
      if (Date.now() - leftAt >= ABSENCE_REFRESH_MS) {
        void locate(true);
      }
    });
    return () => sub.remove();
  }, [disabled, locate]);

  return { coords, coordsTimestamp, loadingLocation, failure, requestManualLocation };
}

export function StoreLocationProvider({
  authenticated,
  sessionKey,
  stores,
  children,
}: {
  authenticated: boolean;
  sessionKey: string;
  stores?: AppStoreItem[] | null;
  children: ReactNode;
}) {
  const value = useStoreLocationController({ authenticated, sessionKey, stores });
  return <StoreLocationContext.Provider value={value}>{children}</StoreLocationContext.Provider>;
}

export function StatusStoresList({
  stores,
  language,
  userCoords,
  userCoordsTimestamp,
  onOpenMap,
  onLocationRequested,
}: StatusStoresListProps) {
  const { t } = useI18n();
  const styles = useThemedStyles(makeStyles);
  const { colors } = useTheme();
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const contextLocation = useContext(StoreLocationContext);
  // A caller that passes `userCoords` (even null) owns the position: nothing is requested here on its own.
  const controlled = userCoords !== undefined;
  const standaloneLocation = useStoreLocationController({
    authenticated: true,
    sessionKey: 'standalone',
    stores,
    disabled: controlled || contextLocation !== null,
  });
  const location = contextLocation ?? standaloneLocation;

  const activeCoords = controlled ? userCoords : location.coords;
  const activeCoordsTimestamp = controlled ? (userCoordsTimestamp ?? null) : location.coordsTimestamp;
  const loadingLocation = controlled ? false : location.loadingLocation;
  const failure = controlled ? null : location.failure;
  const anyStoreHasCoordinates = (stores ?? []).some(hasStoreCoordinates);

  const handleRequestLocation = useCallback(() => {
    if (controlled || loadingLocation) return;
    onLocationRequested?.();
    location.requestManualLocation();
  }, [controlled, loadingLocation, location, onLocationRequested]);

  if (!stores || stores.length === 0) return null;

  const langKey = language === 'kz' ? 'kk' : 'ru';
  const sorted = [...stores].sort((a, b) => a.sort_order - b.sort_order);

  const handleOpenMap = (mapUrl: string | null) => {
    if (!mapUrl) return;
    if (onOpenMap) {
      onOpenMap(mapUrl);
      return;
    }
    void openMapUrl(mapUrl).then(opened => {
      if (!opened && mountedRef.current) Alert.alert(t('app'), t('mapOpenFailed'));
    });
  };

  return (
    <View testID="status-stores-list" style={styles.container}>
      <View style={styles.headerRow}>
        <Text accessibilityRole="header" style={styles.sectionTitle}>
          {t('ourStores')}
        </Text>
        {anyStoreHasCoordinates && (
          <PressScale
            testID="show-distances-button"
            accessibilityRole="button"
            accessibilityLabel={
              loadingLocation
                ? t('locatingDistances')
                : activeCoords
                  ? t('updateDistances')
                  : failure
                    ? t('retryDistances')
                    : t('showDistances')
            }
            disabled={loadingLocation}
            onPress={handleRequestLocation}
            style={[styles.locationButton, loadingLocation && styles.locationButtonDisabled]}
          >
            {loadingLocation ? (
              <ActivityIndicator size="small" color={colors.primaryText} />
            ) : (
              <Text style={styles.locationButtonText}>
                {activeCoords ? t('updateDistances') : failure ? t('retryDistances') : t('showDistances')}
              </Text>
            )}
          </PressScale>
        )}
      </View>

      {!anyStoreHasCoordinates && (
        <Text testID="stores-coords-missing-note" style={styles.permissionDeniedText}>
          {t('storesCoordsNotSet')}
        </Text>
      )}

      {anyStoreHasCoordinates && activeCoords && activeCoordsTimestamp !== null && (
        <Text testID="location-updated-at" style={styles.permissionDeniedText}>
          {formatLocationUpdatedAgo(activeCoordsTimestamp, Date.now(), t)}
        </Text>
      )}

      {failure?.reason === 'denied' && (
        <View testID="location-denied-note">
          <Text style={styles.permissionDeniedText}>{t('locationPermissionDenied')}</Text>
          {!failure.canAskAgain && <Text style={styles.permissionDeniedText}>{t('locationPermissionSettingsHint')}</Text>}
        </View>
      )}
      {failure && failure.reason !== 'denied' && (
        <Text testID="location-failure-note" accessibilityLiveRegion="polite" style={styles.permissionDeniedText}>
          {t(failure.reason === 'services-off' ? 'locationServicesOff' : failure.reason === 'timeout' ? 'locationTimeout' : 'locationError')}
        </Text>
      )}

      <View style={styles.list}>
        {sorted.map(store => {
          const title = (langKey === 'kk' ? store.title_kk : store.title_ru) || '';
          const address = (langKey === 'kk' ? store.address_kk : store.address_ru) || '';

          // Never a made-up distance: a number only when both the phone and this store have real coordinates.
          let distanceLabel: string;
          if (!hasStoreCoordinates(store)) {
            distanceLabel = `${t('distanceDirect')}: ${t('storeCoordsMissing')}`;
          } else if (activeCoords && isFiniteNumber(activeCoords.latitude) && isFiniteNumber(activeCoords.longitude)) {
            const meters = calculateDirectDistance(
              activeCoords.latitude,
              activeCoords.longitude,
              store.latitude as number,
              store.longitude as number,
            );
            distanceLabel = `${t('distanceDirect')}: ${meters !== null ? formatDistance(meters, t) : t('distanceUnavailable')}`;
          } else {
            distanceLabel = `${t('distanceDirect')}: ${loadingLocation ? t('distanceLocating') : t('distanceUnavailable')}`;
          }

          const hasMap = Boolean(store.map_url);

          return (
            <PressScale
              key={store.id}
              testID={`status-store-item-${store.id}`}
              disabled={!hasMap}
              accessibilityRole={hasMap ? 'button' : 'none'}
              accessibilityLabel={`${title}. ${address}. ${distanceLabel}`}
              onPress={() => handleOpenMap(store.map_url)}
              scale={hasMap ? 0.98 : 1}
              style={[styles.card, !hasMap && styles.cardDisabled]}
            >
              <View style={styles.cardHeader}>
                <Text style={styles.storeTitle}>{title || address}</Text>
                {hasMap && (
                  <Icon name="chevronRight" size={16} color={colors.primaryText} />
                )}
              </View>
              {title && address ? (
                <Text style={styles.storeAddress}>{address}</Text>
              ) : null}
              <View style={styles.distanceRow}>
                <Text testID={`store-distance-${store.id}`} style={styles.distanceText}>
                  {distanceLabel}
                </Text>
              </View>
            </PressScale>
          );
        })}
      </View>
    </View>
  );
}

const makeStyles = (c: Colors) =>
  StyleSheet.create({
    container: {
      gap: 12,
      marginTop: 8,
    },
    headerRow: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      paddingHorizontal: 4,
    },
    sectionTitle: {
      fontFamily: fonts.bold,
      fontSize: 18,
      color: c.text,
    },
    locationButton: {
      paddingVertical: 6,
      paddingHorizontal: 12,
      borderRadius: 12,
      backgroundColor: c.softPrimary,
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: 32,
    },
    locationButtonDisabled: {
      opacity: 0.6,
    },
    locationButtonText: {
      fontFamily: fonts.semibold,
      fontSize: 12,
      color: c.primaryText,
    },
    permissionDeniedText: {
      fontFamily: fonts.regular,
      fontSize: 12,
      color: c.muted,
      paddingHorizontal: 6,
      marginTop: -4,
    },
    list: {
      gap: 10,
    },
    card: {
      backgroundColor: c.surface,
      borderColor: c.cardBorder,
      borderWidth: 1,
      borderRadius: 16,
      padding: 16,
      gap: 6,
    },
    cardDisabled: {
      opacity: 0.9,
    },
    cardHeader: {
      flexDirection: 'row',
      alignItems: 'center',
      justifyContent: 'space-between',
      gap: 8,
    },
    storeTitle: {
      fontFamily: fonts.semibold,
      fontSize: 16,
      color: c.text,
      flex: 1,
    },
    storeAddress: {
      fontFamily: fonts.regular,
      fontSize: 14,
      color: c.muted,
      lineHeight: 20,
    },
    distanceRow: {
      flexDirection: 'row',
      alignItems: 'center',
      marginTop: 4,
    },
    distanceText: {
      fontFamily: fonts.medium,
      fontSize: 13,
      color: c.muted,
    },
  });
