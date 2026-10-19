
const DEFAULT_TIMEZONE = 'Asia/Dhaka';
const DEFAULT_LOCALE = 'en-BD';

export function formatToLocalTime(utcIsoString) {
  if (!utcIsoString) return '';

  const date = new Date(utcIsoString);

  if (Number.isNaN(date.getTime())) {
    return '';
  }

  const timeZone =
    import.meta.env.VITE_DEFAULT_TIMEZONE || DEFAULT_TIMEZONE;

  const locale =
    import.meta.env.VITE_DEFAULT_LOCALE || DEFAULT_LOCALE;

  try {
    return new Intl.DateTimeFormat(locale, {
      timeZone,
      dateStyle: 'medium',
      timeStyle: 'short',
    }).format(date);
  } catch (error) {
    console.error('Failed to format date:', error);
    return '';
  }
}
