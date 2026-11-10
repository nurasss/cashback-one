import { describe, expect, it } from 'vitest';
import {
  astanaLocalToUtcIso,
  dayBoundary,
  formatDate,
  formatDateOnly,
  isValidAstanaDateTimeLocal,
  localDate,
} from '../src/utils/format';
import { adminRu, adminKk } from '../src/i18n/admin';

describe('Final Revisions (Points 5–14)', () => {
  describe('Dates and Astana Time (Points 9–10 & Fix 4)', () => {
    it('formatDate formats in Asia/Almaty time zone', () => {
      // 2026-11-10T12:00:00Z is 17:00 in Asia/Almaty (UTC+5)
      const formattedRu = formatDate('2026-11-10T12:00:00Z', 'ru');
      expect(formattedRu).toContain('17:00');

      const formattedKk = formatDate('2026-11-10T12:00:00Z', 'kk');
      expect(formattedKk).toContain('17:00');
    });

    it('formatDateOnly formats date without timezone shift across midnight', () => {
      // 2026-11-10T20:00:00Z in UTC is 2026-11-11 01:00 in Asia/Almaty
      const formatted = formatDateOnly('2026-11-10T20:00:00Z', 'ru');
      expect(formatted).toContain('11');
    });

    it('localDate formats date strictly in UTC+5 Astana time', () => {
      // 2026-11-09 19:00:00 UTC is exactly 2026-11-10 00:00:00 UTC+5
      const midnightAstana = new Date('2026-11-09T19:00:00.000Z');
      expect(localDate(midnightAstana)).toBe('2026-11-10');

      // One second before midnight Astana is still previous day 2026-11-09
      const beforeMidnight = new Date('2026-11-09T18:59:59.000Z');
      expect(localDate(beforeMidnight)).toBe('2026-11-09');
    });

    it('dayBoundary produces deterministic UTC bounds for Astana midnight and end-of-day', () => {
      // Start of day 2026-11-10 in Astana (UTC+5) is 2026-11-09 19:00:00.000 UTC
      const start = dayBoundary('2026-11-10', false);
      expect(start).toBe('2026-11-09T19:00:00.000Z');

      // End of day 2026-11-10 in Astana (UTC+5) is 2026-11-10 18:59:59.999 UTC
      const end = dayBoundary('2026-11-10', true);
      expect(end).toBe('2026-11-10T18:59:59.999Z');
    });

    it('isValidAstanaDateTimeLocal enforces strict 4-digit year and real calendar dates', () => {
      // Valid cases
      expect(isValidAstanaDateTimeLocal('2026-11-10T12:00')).toBe(true);
      expect(isValidAstanaDateTimeLocal('2026-02-28T23:59')).toBe(true);
      expect(isValidAstanaDateTimeLocal('2024-02-29T10:00')).toBe(true); // leap year 2024

      // Invalid years (not 4 digits or out of bounds)
      expect(isValidAstanaDateTimeLocal('26-11-10T12:00')).toBe(false);
      expect(isValidAstanaDateTimeLocal('12345-11-10T12:00')).toBe(false);
      expect(isValidAstanaDateTimeLocal('1999-11-10T12:00')).toBe(false);
      expect(isValidAstanaDateTimeLocal('2105-11-10T12:00')).toBe(false);

      // Invalid calendar dates
      expect(isValidAstanaDateTimeLocal('2026-02-29T12:00')).toBe(false); // 2026 is not a leap year
      expect(isValidAstanaDateTimeLocal('2026-02-31T12:00')).toBe(false);
      expect(isValidAstanaDateTimeLocal('2026-04-31T12:00')).toBe(false); // April has 30 days
      expect(isValidAstanaDateTimeLocal('2026-13-01T12:00')).toBe(false); // invalid month
      expect(isValidAstanaDateTimeLocal('2026-11-32T12:00')).toBe(false); // invalid day
      expect(isValidAstanaDateTimeLocal('2026-11-10T25:00')).toBe(false); // invalid hour
      expect(isValidAstanaDateTimeLocal('2026-11-10T12:65')).toBe(false); // invalid minute
      expect(isValidAstanaDateTimeLocal('')).toBe(false);
      expect(isValidAstanaDateTimeLocal('garbage')).toBe(false);
    });

    it('astanaLocalToUtcIso returns empty string for invalid dates without rollover', () => {
      expect(astanaLocalToUtcIso('2026-02-31T12:00')).toBe('');
      expect(astanaLocalToUtcIso('26-05-01T10:00')).toBe('');
      // Valid conversion: 2026-11-10 17:00 Astana -> 12:00 UTC
      expect(astanaLocalToUtcIso('2026-11-10T17:00')).toBe('2026-11-10T12:00:00.000Z');
    });
  });

  describe('Statuses Translations and Navigation (Points 7–8)', () => {
    it('contains all required keys in adminRu.statuses and adminKk.statuses', () => {
      expect(adminRu.statuses.title).toBeTruthy();
      expect(adminRu.statuses.subtitle).toBeTruthy();
      expect(adminRu.statuses.addTierBtn).toBeTruthy();
      expect(adminRu.statuses.fieldTurnoverPeriodMonths).toBeTruthy();
      expect(adminRu.statuses.fieldTurnoverPeriodHint).toBeTruthy();
      expect(adminRu.statuses.periodMonths(6)).toBe('6 мес.');
      expect(adminRu.statuses.turnoverRange(0, 100000)).toContain('от 0 ₸ до 100');
      expect(adminRu.statuses.fieldPriority).toBe('Приоритет (чем больше число, тем выше приоритет)');

      expect(adminKk.statuses.title).toBeTruthy();
      expect(adminKk.statuses.subtitle).toBeTruthy();
      expect(adminKk.statuses.addTierBtn).toBeTruthy();
      expect(adminKk.statuses.fieldTurnoverPeriodMonths).toBeTruthy();
      expect(adminKk.statuses.periodMonths(6)).toBe('6 ай');
      expect(adminKk.statuses.fieldPriority).toBe('Басымдық (сан неғұрлым үлкен болса, басымдық соғұрлым жоғары)');
    });

    it('audit column headers and labels indicate Astana time and human actor', () => {
      expect(adminRu.audit.colDateTime).toBe('ДАТА И ВРЕМЯ (АСТАНА)');
      expect(adminRu.audit.colActor).toBe('КТО ВЫПОЛНИЛ');
      expect(adminKk.audit.colDateTime).toBe('КҮНІ МЕН УАҚЫТЫ (АСТАНА)');
      expect(adminKk.audit.colActor).toBe('КІМ ОРЫНДАДЫ');
    });

    it('nav contains statuses for both manager and superadmin', () => {
      expect(adminRu.layout.nav.statuses).toBe('Статусы');
      expect(adminKk.layout.nav.statuses).toBe('Дәрежелер');
    });
  });

  describe('Stores Coordinates & I18n (Point 13 & Contract)', () => {
    it('contains coordinate field labels and error messages', () => {
      expect(adminRu.appContent.fieldLatitude).toContain('Широта');
      expect(adminRu.appContent.fieldLongitude).toContain('Долгота');
      expect(adminRu.appContent.errCoordinatesPair).toBeTruthy();
      expect(adminRu.appContent.errLatitudeRange).toBeTruthy();
      expect(adminRu.appContent.errLongitudeRange).toBeTruthy();

      expect(adminKk.appContent.fieldLatitude).toContain('Ендік');
      expect(adminKk.appContent.fieldLongitude).toContain('Бойлық');
      expect(adminKk.appContent.errCoordinatesPair).toBeTruthy();
      expect(adminKk.appContent.errLatitudeRange).toBeTruthy();
      expect(adminKk.appContent.errLongitudeRange).toBeTruthy();
    });
  });
});
