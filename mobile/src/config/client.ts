import type { ComponentType } from 'react';
import type { ImageSourcePropType } from 'react-native';
import cashbackoneJson from '../../clients/cashbackone/client.json';
import exampleJson from '../../clients/example/client.json';
import keremetJson from '../../clients/keremet/client.json';
import { KeremetLogo } from '../../clients/keremet/Logo';
import { keremetStatuses, type ClientStatuses } from '../../clients/keremet/statuses';

export interface ClientConfig {
  slug: string;
  apk_name?: string;
  // File name of this client's version manifest under /app/ (default: version.json for the general app, `<slug>-version.json` otherwise).
  update_manifest?: string;
  android_app_id: string;
  app_name: {
    ru: string;
    kk: string;
  };
  android_label?: string;
  business_id: string | null;
  primary_color: string;
  scheme: string;
  Logo?: ComponentType<{ height?: number; accessibilityLabel?: string }>;
  // Round badge for the home header; when absent the shared text badge is used.
  headerBadge?: ImageSourcePropType;
  // Client-specific named loyalty statuses with artwork. Clients without it keep the server's levels and the shared coin artwork.
  statuses?: ClientStatuses;
}

const CLIENT_CONFIGS: Record<string, ClientConfig> = {
  cashbackone: {
    ...cashbackoneJson,
  },
  example: {
    ...exampleJson,
  },
  keremet: {
    ...keremetJson,
    Logo: KeremetLogo,
    headerBadge: require('../../clients/keremet/header_badge.png') as ImageSourcePropType,
    statuses: keremetStatuses,
  },
};

export function getClientConfig(slugOverride?: string): ClientConfig {
  const slug = slugOverride ?? process.env.EXPO_PUBLIC_CLIENT ?? 'cashbackone';
  const config = CLIENT_CONFIGS[slug];
  if (!config) {
    throw new Error(
      `Unknown client slug: "${slug}". Supported clients: ${Object.keys(CLIENT_CONFIGS).join(', ')}`,
    );
  }
  return config;
}

export function appendBusinessId(path: string, businessId?: string | null): string {
  if (!businessId) return path;
  const separator = path.includes('?') ? '&' : '?';
  return `${path}${separator}business_id=${encodeURIComponent(businessId)}`;
}

export function withClientBusiness(path: string, slugOverride?: string): string {
  const client = getClientConfig(slugOverride);
  if (!client.business_id) return path;
  return appendBusinessId(path, client.business_id);
}
