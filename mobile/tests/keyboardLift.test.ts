import { overlap } from '../src/components/useKeyboardLift';

it('does not double-lift a viewport already resized above the keyboard', () => {
  expect(overlap(500, 500, 10)).toBe(0);
  expect(overlap(480, 500, 10)).toBe(0);
});

it('lifts an unresized sheet by the overlap plus the safety margin', () => {
  expect(overlap(800, 500, 10)).toBe(310);
  expect(overlap(800, 620, 8)).toBe(188);
});
