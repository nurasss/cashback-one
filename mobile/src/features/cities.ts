import { ru } from '../i18n/ru';

export function cityOptions(translate: (key: keyof typeof ru) => string, saved: string) {
  const options = Array.from({ length: 23 }, (_, index) => {
    const key = `cityOption${index}` as keyof typeof ru;
    return { value: ru[key], label: translate(key) };
  });
  if (saved && !options.some(option => option.value === saved)) {
    options.unshift({ value: saved, label: saved });
  }
  return options;
}
