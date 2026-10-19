import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowRight, MapPin, MessageSquarePlus, Users } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { listAllDestinations } from '../api/destinations';
import { useApiResource } from '../hooks/useApiResource';
import { ErrorState, LoadingState } from '../components/common/StatusViews';
import { RatingSummary } from '../components/destination/RatingSummary';
import { formatNumber, pick } from '../utils/format';

export const OverviewPage: React.FC = () => {
  const { language, t } = useLanguage();
  const { data, error, loading, reload } = useApiResource((signal) => listAllDestinations(signal), []);

  const destinations = data ?? [];
  const advisoryTotal = destinations.reduce((sum, d) => sum + d.active_advisory_count, 0);
  const guestReviewTotal = destinations.reduce((sum, d) => sum + d.guest_feedback.count, 0);
  const withAdvisories = destinations.filter((d) => d.active_advisory_count > 0);

  const metrics = [
    { icon: MapPin, value: destinations.length, label: t('প্রকাশিত গন্তব্য', 'Published destinations') },
    { icon: AlertTriangle, value: advisoryTotal, label: t('কার্যকর ভ্রমণ সতর্কতা', 'Advisories in effect') },
    { icon: Users, value: guestReviewTotal, label: t('প্রকাশিত অতিথি রিভিউ', 'Published guest reviews') },
  ];

  return (
    <div className="flex flex-col gap-8 pb-12">
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold font-title text-on-surface dark:text-on-dark tracking-tight">
            {t('স্বাগতম অভিযাত্রীতে', 'Welcome to Abhijatri')}
          </h1>
          <p className="text-sm sm:text-base text-on-surface-variant dark:text-on-dark-muted font-body mt-1 max-w-2xl">
            {t(
              'বাংলাদেশ ভ্রমণের জন্য সূত্র ও তারিখসহ গাইড, নিরাপত্তা সতর্কতা আর মডারেশন করা ভ্রমণকারীর রিভিউ।',
              'Source-dated guides, safety advisories and moderated traveller reviews for travel in Bangladesh.',
            )}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to="/destinations" className="inline-flex items-center gap-2 min-h-[44px] px-5 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-bold font-title">
            {t('গন্তব্য দেখুন', 'Browse destinations')}
            <ArrowRight size={14} aria-hidden="true" />
          </Link>
          <Link to="/reviews" className="inline-flex items-center gap-2 min-h-[44px] px-5 rounded-full bg-surface-sage dark:bg-dark-surface-2 text-forest-primary dark:text-neon-lime text-xs font-bold font-title">
            <MessageSquarePlus size={14} aria-hidden="true" />
            {t('রিভিউ লিখুন', 'Write a review')}
          </Link>
        </div>
      </div>

      {loading && <LoadingState />}
      {!loading && error !== null && <ErrorState error={error} onRetry={reload} />}

      {!loading && !error && (
        <>
          <ul className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {metrics.map(({ icon: Icon, value, label }) => (
              <li key={label} className="tonal-card p-5 flex items-center gap-4">
                <span className="w-11 h-11 rounded-2xl bg-surface-sage dark:bg-dark-surface-2 text-forest-primary dark:text-neon-lime flex items-center justify-center shrink-0">
                  <Icon size={20} aria-hidden="true" />
                </span>
                <span className="flex flex-col">
                  <span className="text-2xl font-bold font-en text-forest-primary dark:text-neon-lime">{formatNumber(value, language)}</span>
                  <span className="text-xs text-on-surface-variant dark:text-on-dark-muted">{label}</span>
                </span>
              </li>
            ))}
          </ul>

          {withAdvisories.length > 0 && (
            <section aria-labelledby="safety-heading" className="tonal-card p-6 flex flex-col gap-3 border-amber-200 dark:border-amber-900/50">
              <h2 id="safety-heading" className="flex items-center gap-2 text-base font-bold font-title text-amber-700 dark:text-amber-300">
                <AlertTriangle size={18} aria-hidden="true" />
                {t('যাওয়ার আগে সতর্কতা দেখুন', 'Check advisories before you go')}
              </h2>
              <ul className="flex flex-wrap gap-2">
                {withAdvisories.map((d) => (
                  <li key={d.id}>
                    <Link to={`/destinations/${d.id}`} className="inline-flex items-center gap-2 min-h-[44px] px-4 rounded-full bg-amber-50 dark:bg-amber-950/30 text-amber-900 dark:text-amber-200 text-xs font-semibold">
                      {pick(language, d.name_bn, d.name_en)}
                      <span className="px-1.5 rounded-full bg-amber-200/70 dark:bg-amber-900/60 font-en">{formatNumber(d.active_advisory_count, language)}</span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          )}

          <section aria-labelledby="destinations-heading" className="flex flex-col gap-4">
            <div className="flex items-center justify-between">
              <h2 id="destinations-heading" className="text-xl sm:text-2xl font-bold font-title text-on-surface dark:text-on-dark">
                {t('গন্তব্যসমূহ', 'Destinations')}
              </h2>
              <Link to="/destinations" className="inline-flex items-center gap-1 min-h-[44px] text-xs font-bold text-forest-primary dark:text-neon-lime hover:underline">
                {t('সব দেখুন', 'View all')}
                <ArrowRight size={14} aria-hidden="true" />
              </Link>
            </div>
            <ul className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
              {destinations.slice(0, 6).map((dest) => (
                <li key={dest.id}>
                  <Link to={`/destinations/${dest.id}`} className="tonal-card p-5 h-full flex flex-col gap-2 group">
                    <span className="text-[11px] font-semibold text-on-surface-variant dark:text-on-dark-muted">{pick(language, dest.region_bn, dest.region_en)}</span>
                    <span className="text-lg font-bold font-title text-on-surface dark:text-on-dark group-hover:text-forest-primary dark:group-hover:text-neon-lime">
                      {pick(language, dest.name_bn, dest.name_en)}
                    </span>
                    <span className="text-xs text-on-surface-variant dark:text-on-dark-muted font-body line-clamp-2">{pick(language, dest.summary_bn, dest.summary_en)}</span>
                    <RatingSummary community={dest.community_rating} guest={dest.guest_feedback} compact />
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        </>
      )}
    </div>
  );
};
