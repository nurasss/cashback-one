import { fireEvent, render } from '@testing-library/react-native';
import { estimatePoints, LevelsSheet } from '../src/features/LevelsSheet';
import { ru } from '../src/i18n/ru';
import type { Tier } from '../src/types/api';

const tier: Tier = {
  level: 1, name: null, percent: '3.0000', max_percent: '12.0000', spend_total: '0.0000', next_level: 2, next_threshold: '350000.0000', remaining: '350000.0000',
  levels: [
    { level: 1, name: null, threshold: '0.0000', percent: '3.0000' }, { level: 2, name: null, threshold: '350000.0000', percent: '5.0000' },
    { level: 3, name: null, threshold: '800000.0000', percent: '8.0000' }, { level: 4, name: null, threshold: '1500000.0000', percent: '12.0000' },
  ],
};

it('estimates points as a truncated share of the check and rejects checks below the minimum', () => {
  expect(estimatePoints('15000', '3.0000')).toBe('450,00');
  expect(estimatePoints('99', '3')).toBeNull();
  expect(estimatePoints('', '3')).toBeNull();
  expect(estimatePoints('1234', '3.5')).toBe('43,19');
});

it('sheet lists every level with its threshold, marks the current one and estimates points for a check', () => {
  const onClose = jest.fn();
  const screen = render(<LevelsSheet tier={tier} onClose={onClose} />);
  for (const level of [1, 2, 3, 4]) expect(screen.getByText(`Статус ${level}`)).toBeTruthy();
  expect(screen.getByText('от 350 000 ₸')).toBeTruthy();
  expect(screen.getByText('12%')).toBeTruthy();
  expect(screen.getByText('Сейчас статус 1 — 3% от суммы')).toBeTruthy();
  expect(screen.getByText(ru.calcHint)).toBeTruthy();
  fireEvent.changeText(screen.getByLabelText(ru.calcLabel), '40000');
  expect(screen.getByText('Придёт примерно 1 200,00 баллов')).toBeTruthy();
  fireEvent.press(screen.getByRole('button', { name: ru.close }));
  expect(onClose).toHaveBeenCalled();
});
