import React from 'react';
import { AlertTriangle, CloudOff } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import type { StoredPack } from '../../offline/db';
import { isPackExpired } from '../../offline/packAdapter';
import { formatCalendarDate, formatTimestamp } from '../../utils/format';

/**
 * Shown on a destination page read from a downloaded pack (Offline-Frontend-Guideline 5.6): when the
 * snapshot was made and when its advisories were verified. Past `expires_at` it says "Out of date":
 * the content still shows, clearly labelled, and is never presented as current safety guidance
 * (PF 18.4, Security 7.4; owner's decision 7 Nov 2026).
 */
export const PackBanner: React.FC<{ stored: StoredPack }> = ({ stored }) => {
  const { language, t } = useLanguage();
  const { pack } = stored;
  const expired = isPackExpired(stored);
  const verified = pack.advisories_verified_on ? formatCalendarDate(pack.advisories_verified_on, language) : null;

  if (expired) {
    return (
      <div role="alert" className="flex items-start gap-2 rounded-xl border border-red-300 dark:border-red-900 bg-red-50 dark:bg-red-950/40 px-4 py-3 text-sm text-red-900 dark:text-red-100">
        <AlertTriangle size={16} className="shrink-0 mt-0.5" aria-hidden="true" />
        <span>
          <strong>{t('পুরনো তথ্য।', 'Out of date.')}</strong>{' '}
          {t(
            `এই অফলাইন কপি ${formatTimestamp(pack.generated_at, language)}-এর। সতর্কতা ও অন্যান্য তথ্য এখন আর সঠিক নাও হতে পারে; সংযোগ ফিরলে হালনাগাদ করুন।`,
            `This offline copy is from ${formatTimestamp(pack.generated_at, language)}. Advisories and other details may no longer be accurate; update it when you are back online.`,
          )}
        </span>
      </div>
    );
  }

  return (
    <div role="status" className="flex items-start gap-2 rounded-xl border border-amber-300 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-900 dark:text-amber-100">
      <CloudOff size={16} className="shrink-0 mt-0.5" aria-hidden="true" />
      <span>
        {t(
          `অফলাইন কপি দেখছেন, তৈরি ${formatTimestamp(pack.generated_at, language)}।`,
          `You are reading the offline copy made on ${formatTimestamp(pack.generated_at, language)}.`,
        )}
        {verified && ` ${t(`সতর্কতা যাচাই: ${verified}।`, `Advisories verified on ${verified}.`)}`}
      </span>
    </div>
  );
};
