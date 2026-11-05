import type { ComponentType } from 'react';
import cashbackoneJson from '../../clients/cashbackone/client.json';
import exampleJson from '../../clients/example/client.json';
import keremetJson from '../../clients/keremet/client.json';
import { KeremetLogo } from '../../clients/keremet/Logo';

export interface ClientConfig {
  slug: string;
  apk_name?: string;
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
