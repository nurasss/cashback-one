import { TextInput } from 'react-native';
import { fireEvent, render } from '@testing-library/react-native';
import { LevelsSheet } from '../src/features/LevelsSheet';
import { kz } from '../src/i18n/kz';
import { ru } from '../src/i18n/ru';
import type { Tier } from '../src/types/api';

const tier: Tier = {
  level: 1, name: null, percent: '3.0000', max_percent: '12.0000', spend_total: '0.0000', next_level: 2, next_threshold: '350000.0000', remaining: '350000.0000',
  levels: [
    { level: 1, name: null, threshold: '0.0000', percent: '3.0000' }, { level: 2, name: null, threshold: '350000.0000', percent: '5.0000' },
    { level: 3, name: null, threshold: '800000.0000', percent: '8.0000' }, { level: 4, name: null, threshold: '1500000.0000', percent: '12.0000' },
  ],
};

const NO_CALC = [/Сумма чека/, /Чек сомасы/, /Придёт примерно/, /Введите сумму/, /ориентировочный/, /Сейчас статус/, /% от суммы/];

function expectNoCalculator(screen: ReturnType<typeof render>, labels: string[] = []) {
  for (const label of labels) expect(screen.queryByLabelText(label)).toBeNull();
  for (const pattern of NO_CALC) expect(screen.queryByText(pattern)).toBeNull();
  expect(screen.queryByPlaceholderText('0')).toBeNull();
  for (const amount of ['5 000', '15 000', '40 000', '120 000']) expect(screen.queryByText(amount)).toBeNull();
}

it('sheet lists every level with its threshold and percent and has no bonus calculator', () => {
  const onClose = jest.fn();
  const screen = render(<LevelsSheet tier={tier} onClose={onClose} />);
  for (const level of [1, 2, 3, 4]) expect(screen.getByText(`Статус ${level}`)).toBeTruthy();
  expect(screen.getByText('от 350 000 ₸')).toBeTruthy();
  expect(screen.getByText('12%')).toBeTruthy();
  expectNoCalculator(screen, ['Сумма чека']);
  expect(screen.UNSAFE_queryAllByType(TextInput)).toHaveLength(0);
  fireEvent.press(screen.getByRole('button', { name: ru.close }));
  expect(onClose).toHaveBeenCalled();
});

it('calculator strings no longer exist in RU and KK dictionaries', () => {
  for (const dict of [ru, kz] as Record<string, string>[]) {
    for (const key of ['calcLabel', 'calcHint', 'calcResult', 'calcDisclaimer', 'currentStatusLine', 'statusCurrentNamed']) {
      expect(dict[key]).toBeUndefined();
    }
  }
});
