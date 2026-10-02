export function formatDate(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value));
}
export function formatDateOnly(value: string): string {
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'medium', timeZone: 'UTC' }).format(new Date(value));
}
export function formatBalance(value: string): string {
  const [integer = '0', fraction = ''] = value.split('.');
  const normalizedFraction = fraction.replace(/0+$/, '');
  return `${integer.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')}${normalizedFraction ? `,${normalizedFraction}` : ''}`;
}
export function localDate(value: Date): string {
  const date = new Date(value.getTime() - value.getTimezoneOffset() * 60_000);
  return date.toISOString().slice(0, 10);
}
export function dayBoundary(day: string, end: boolean): string {
  const date = new Date(`${day}T00:00:00`);
  if (end) date.setDate(date.getDate() + 1);
  if (end) date.setMilliseconds(date.getMilliseconds() - 1);
  return date.toISOString();
}
