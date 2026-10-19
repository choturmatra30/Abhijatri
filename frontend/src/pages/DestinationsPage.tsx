import React, { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, MapPin, Search } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { listAllDestinations } from '../api/destinations';
import { useApiResource } from '../hooks/useApiResource';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StatusViews';
import { RatingSummary } from '../components/destination/RatingSummary';
import { formatNumber, pick } from '../utils/format';

export const DestinationsPage: React.FC = () => {
  const { language, t } = useLanguage();
  const [query, setQuery] = useState('');
  const { data, error, loading, reload } = useApiResource((signal) => listAllDestinations(signal), []);

  const visible = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase();
    if (!data || !needle) return data ?? [];
    return data.filter((d) =>
      [d.name_bn, d.name_en, d.region_bn, d.region_en].some((v) => v?.toLocaleLowerCase().includes(needle)),
    );
  }, [data, query]);

  return (
    <div className="flex flex-col gap-6 pb-12">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold font-title text-on-surface dark:text-on-dark tracking-tight">
            {t('গন্তব্য ও ভ্রমণ গাইড', 'Destinations & Guides')}
          </h1>
          <p className="text-sm text-on-surface-variant dark:text-on-dark-muted font-body mt-1">
            {t(
              'সূত্র ও তারিখসহ দ্বিভাষিক তথ্য, নিরাপত্তা সতর্কতা ও জরুরি যোগাযোগ।',
              'Bilingual, source-dated guidance with safety advisories and emergency contacts.',
            )}
          </p>
        </div>

        <label className="relative w-full md:w-72">
          <span className="sr-only">{t('গন্তব্য খুঁজুন', 'Filter destinations')}</span>
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant" size={16} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('নাম বা এলাকা দিয়ে খুঁজুন', 'Filter by name or region')}
            className="w-full pl-10 pr-4 min-h-[44px] rounded-full bg-surface-sage/50 dark:bg-dark-surface-1 border border-surface-muted/40 dark:border-dark-surface-2 text-sm text-on-surface dark:text-on-dark"
          />
        </label>
      </div>

      {loading && <LoadingState label={t('গন্তব্যের তালিকা লোড হচ্ছে…', 'Loading destinations…')} />}
      {!loading && error !== null && <ErrorState error={error} onRetry={reload} />}
      {!loading && !error && data && data.length === 0 && (
        <EmptyState
          title={t('এখনো কোনো প্রকাশিত গন্তব্য নেই', 'No published destinations yet')}
          hint={t('কনটেন্ট প্রকাশিত হলে এখানে দেখা যাবে।', 'Destinations appear here once their content is published.')}
        />
      )}
      {!loading && !error && data && data.length > 0 && visible.length === 0 && (
        <EmptyState title={t('কোনো মিল পাওয়া যায়নি', 'No matches')} hint={t('অন্য শব্দ দিয়ে খুঁজুন।', 'Try another word.')} />
      )}

      {!loading && !error && visible.length > 0 && (
        <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {visible.map((dest) => (
            <li key={dest.id} className="tonal-card flex flex-col justify-between p-5 gap-4">
              <div className="flex flex-col gap-2.5">
                <div className="flex items-center justify-between gap-2 text-[11px] font-semibold text-on-surface-variant dark:text-on-dark-muted">
                  <span className="inline-flex items-center gap-1">
                    <MapPin size={13} className="text-forest-primary dark:text-neon-lime" aria-hidden="true" />
                    {pick(language, dest.region_bn, dest.region_en)}
                  </span>
                  {dest.active_advisory_count > 0 && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-100 text-amber-900 dark:bg-amber-950/50 dark:text-amber-200">
                      <AlertTriangle size={12} aria-hidden="true" />
                      {formatNumber(dest.active_advisory_count, language)} {t('সতর্কতা', dest.active_advisory_count === 1 ? 'advisory' : 'advisories')}
                    </span>
                  )}
                </div>
                <h2 className="text-xl font-bold font-title text-on-surface dark:text-on-dark">
                  {pick(language, dest.name_bn, dest.name_en)}
                </h2>
                <p className="text-sm text-on-surface-variant dark:text-on-dark-muted font-body leading-relaxed line-clamp-3">
                  {pick(language, dest.summary_bn, dest.summary_en)}
                </p>
                <RatingSummary community={dest.community_rating} guest={dest.guest_feedback} compact />
              </div>

              <Link
                to={`/destinations/${dest.id}`}
                className="inline-flex items-center justify-center gap-2 min-h-[44px] px-4 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-bold font-title hover:opacity-95"
              >
                {t('গাইড ও রিভিউ দেখুন', 'View guide & reviews')}
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
