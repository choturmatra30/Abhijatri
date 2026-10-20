import type { Language } from '../types';

/** Calendar rules and displayed dates follow Asia/Dhaka (Platform Foundation 11.2). */
export const DISPLAY_TIME_ZONE = import.meta.env.VITE_DEFAULT_TIMEZONE || 'Asia/Dhaka';

const locale = (language: Language) => (language === 'bn' ? 'bn-BD' : 'en-GB');

/** Pick the field for the current language, falling back to the other language. */
export function pick(language: Language, bn: string | null | undefined, en: string | null | undefined): string {
  return (language === 'bn' ? bn || en : en || bn) ?? '';
}

export function formatNumber(value: number, language: Language, fractionDigits = 0): string {
  return new Intl.NumberFormat(locale(language), {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  }).format(value);
}

/** A calendar date from the API (`YYYY-MM-DD`) shown without time-zone drift. */
export function formatCalendarDate(isoDate: string, language: Language): string {
  const [year, month, day] = isoDate.split('-').map(Number);
  if (!year || !month || !day) return isoDate;
  return new Intl.DateTimeFormat(locale(language), { dateStyle: 'medium', timeZone: 'UTC' }).format(
    new Date(Date.UTC(year, month - 1, day)),
  );
}

/** A UTC timestamp shown in the display time zone. */
export function formatTimestamp(isoTimestamp: string, language: Language): string {
  const date = new Date(isoTimestamp);
  if (Number.isNaN(date.getTime())) return '';
  return new Intl.DateTimeFormat(locale(language), {
    dateStyle: 'medium',
    timeZone: DISPLAY_TIME_ZONE,
  }).format(date);
}

/** Today in the display time zone as `YYYY-MM-DD` (the guest footprint counts one visit per day). */
export function currentDisplayDate(now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: DISPLAY_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now);
}

/** Current month in the display time zone as `YYYY-MM` (the latest allowed visit month). */
export function currentDisplayMonth(now: Date = new Date()): string {
  const parts = new Intl.DateTimeFormat('en-CA', {
    timeZone: DISPLAY_TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
  }).formatToParts(now);
  const year = parts.find((p) => p.type === 'year')?.value;
  const month = parts.find((p) => p.type === 'month')?.value;
  return `${year}-${month}`;
}
