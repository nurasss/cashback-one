// The session lasts as long as the server allows, so no screen promises a term ("14 дней" / "14 күн"), and the login screen has no note under the form.
import { render } from '@testing-library/react-native';
import Login from '../app/login';
import { I18nProvider, type Language } from '../src/i18n';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';

jest.mock('../src/auth/provider', () => ({
  useSession: () => ({ api: { request: jest.fn() }, session: { accept: jest.fn(), logout: jest.fn() } }),
}));
jest.mock('expo-router', () => ({ router: { push: jest.fn(), replace: jest.fn(), navigate: jest.fn(), back: jest.fn(), canGoBack: () => true } }));
jest.mock('react-native-safe-area-context', () => {
  const { View } = jest.requireActual<typeof import('react-native')>('react-native');
  return { SafeAreaView: View, useSafeAreaInsets: () => ({ top: 0, bottom: 0, left: 0, right: 0 }) };
});
jest.mock('../src/storage/secure', () => ({ deviceId: jest.fn(() => Promise.resolve('test-device-id')) }));

const TERM = /\b14\b|запомним|есте сақтаймыз|\b2 недел|(две|двух) недел|\b2 апта/i;
type Node = { children?: (string | Node)[] | null };
const texts = (node: Node | Node[] | null): string[] => {
  if (!node) return [];
  if (Array.isArray(node)) return node.flatMap(texts);
  return (node.children ?? []).flatMap(child => (typeof child === 'string' ? [child] : texts(child)));
};

it.each<Language>(['ru', 'kz'])('login screen in %s has no session-term note and nothing is rendered after the form', language => {
  const screen = render(<I18nProvider initial={language}><Login /></I18nProvider>);
  const all = texts(screen.toJSON());
  expect(all.filter(text => TERM.test(text))).toEqual([]);
  expect(all.at(-1)).toBe(language === 'ru' ? ru.requestCode : kz.requestCode); // the last text on the screen is the button, no note below it
  screen.unmount();
});

it('no dictionary entry promises a session term, and the removed key is gone', () => {
  for (const [name, dictionary] of Object.entries({ ru, kz })) {
    expect(Object.keys(dictionary)).not.toContain('sessionNote');
    expect(Object.entries(dictionary).filter(([, value]) => typeof value === 'string' && TERM.test(value)).map(([key]) => `${name}.${key}`)).toEqual([]);
  }
});
