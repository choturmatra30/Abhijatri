import React from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  ExternalLink,
  MapPin,
  Phone,
  ShieldAlert,
} from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { loadDestination } from '../offline/destinationSource';
import { ApiError } from '../api/client';
import { useApiResource } from '../hooks/useApiResource';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StatusViews';
import { AdvisoryCard } from '../components/destination/AdvisoryCard';
import { ProvenanceNote } from '../components/destination/ProvenanceNote';
import { RatingSummary } from '../components/destination/RatingSummary';
import { CategoryAverages } from '../components/destination/CategoryAverages';
import { GuideSections } from '../components/destination/GuideSections';
import { ReviewFeedSection } from '../components/reviews/ReviewFeedSection';
import { PackBanner } from '../components/offline/PackBanner';
import { PackDownloadButton } from '../components/offline/PackDownloadButton';
import { googleMapsUrl } from '../utils/destinationSort';
import { formatCalendarDate, formatNumber, pick } from '../utils/format';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const DestinationDetailPage: React.FC = () => {
  const { id = '' } = useParams<{ id: string }>();
  const { language, t } = useLanguage();
  const validId = UUID_PATTERN.test(id);
  // Online the network; offline the downloaded pack first, then the opened-page copy (R13).
  const { data: loaded, error, loading, reload } = useApiResource(
    (signal) => (validId ? loadDestination(id, { signal }) : Promise.reject(new ApiError(404, 'NOT_FOUND', ''))),
    [id],
  );
  const destination = loaded?.profile ?? null;

  const backLink = (
    <Link
      to="/destinations"
      className="inline-flex items-center gap-1.5 min-h-[44px] text-xs font-bold text-forest-primary dark:text-neon-lime hover:underline font-title"
    >
      <ArrowLeft size={16} aria-hidden="true" />
      {t('সব গন্তব্যে ফিরুন', 'Back to all destinations')}
    </Link>
  );

  if (loading) {
    return (
      <div className="flex flex-col gap-4 max-w-5xl mx-auto">
        {backLink}
        <LoadingState label={t('গাইড লোড হচ্ছে…', 'Loading guide…')} />
      </div>
    );
  }

  if (error || !destination) {
    const notFound = error instanceof ApiError && error.code === 'NOT_FOUND';
    return (
      <div className="flex flex-col gap-4 max-w-5xl mx-auto">
        {backLink}
        {notFound ? (
          <EmptyState
            title={t('গন্তব্যটি পাওয়া যায়নি', 'Destination not found')}
            hint={t('লিংকটি পুরনো হতে পারে, অথবা গন্তব্যটি এখন প্রকাশিত নেই।', 'The link may be old, or the destination is no longer published.')}
          />
        ) : (
          <ErrorState
            error={error}
            onRetry={reload}
            offlineHint={t(
              'এই গন্তব্যটি এই ডিভাইসে সংরক্ষিত নেই। অনলাইনে থাকার সময় খোলা গন্তব্য ৭ দিন পর্যন্ত অফলাইনে দেখা যায়।',
              'This destination is not saved on this device. Destinations you open while online stay readable offline for up to 7 days.',
            )}
            offlineAction={
              <Link to="/destinations" className="text-sm font-semibold text-primary underline underline-offset-4">
                {t('সংরক্ষিত গন্তব্য দেখুন', 'See saved destinations')}
              </Link>
            }
          />
        )}
      </div>
    );
  }


  return (
    <div className="flex flex-col gap-8 pb-12 max-w-5xl mx-auto">
      {backLink}
      {loaded?.source === 'pack' && loaded.stored && <PackBanner stored={loaded.stored} />}

      {/* Header */}
      <header className="tonal-card p-6 sm:p-8 flex flex-col gap-4 bg-surface-sage/60 dark:bg-dark-surface-1">
        <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-on-surface-variant dark:text-on-dark-muted">
          <MapPin size={14} className="text-forest-primary dark:text-neon-lime" aria-hidden="true" />
          <span>{pick(language, destination.region_bn, destination.region_en)}</span>
          {destination.latitude !== null && destination.longitude !== null && (
            <a
              href={googleMapsUrl(destination.latitude, destination.longitude)}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 min-h-[44px] sm:min-h-0 underline underline-offset-2"
            >
              {t('গুগল ম্যাপে দেখুন', 'Open in Google Maps')}
              <ExternalLink size={11} aria-hidden="true" />
            </a>
          )}
        </div>
        <h1 className="text-3xl sm:text-4xl font-bold font-title tracking-tight text-on-surface dark:text-on-dark">
          {pick(language, destination.name_bn, destination.name_en)}
        </h1>
        <p className="text-base font-body leading-relaxed text-on-surface-variant dark:text-on-dark-muted max-w-3xl">
          {pick(language, destination.summary_bn, destination.summary_en)}
        </p>
        <RatingSummary community={destination.community_rating} guest={destination.guest_feedback} />
        <CategoryAverages
          averages={destination.community_rating.category_averages}
          title={t('কমিউনিটি রেটিং: বিষয়ভিত্তিক', 'Community Rating by category')}
        />
        <CategoryAverages
          averages={destination.guest_feedback.category_averages}
          title={t('অতিথি মতামত: বিষয়ভিত্তিক', 'Guest Feedback by category')}
        />
        {destination.content_verified_on && (
          <p className="text-[11px] text-on-surface-variant dark:text-on-dark-muted">
            {t('কনটেন্ট যাচাই', 'Content verified')}: {formatCalendarDate(destination.content_verified_on, language)}
            {destination.content_licence && ` • ${destination.content_licence}`}
          </p>
        )}
      </header>

      <PackDownloadButton destinationId={destination.id} />

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Advisories first: safety before attractions */}
          <section aria-labelledby="advisories-heading" className="tonal-card p-6 flex flex-col gap-3">
            <h2 id="advisories-heading" className="flex items-center gap-2 text-base font-bold font-title text-amber-700 dark:text-amber-300">
              <AlertTriangle size={18} aria-hidden="true" />
              {t('ভ্রমণ সতর্কতা', 'Travel advisories')}
            </h2>
            {destination.advisories.length === 0 ? (
              <p className="text-sm text-on-surface-variant dark:text-on-dark-muted">
                {t('এই মুহূর্তে কোনো কার্যকর সতর্কতা নেই।', 'No advisories are in effect right now.')}
              </p>
            ) : (
              destination.advisories.map((advisory) => <AdvisoryCard key={advisory.id} advisory={advisory} />)
            )}
            <p className="text-[11px] text-on-surface-variant dark:text-on-dark-muted">
              {t(
                `অবস্থা ${formatCalendarDate(destination.as_of, language)} তারিখ (ঢাকা সময়) অনুযায়ী। ${formatNumber(destination.stale_after_days, language)} দিনের বেশি আগে যাচাই করা সতর্কতা "পুরনো যাচাই" হিসেবে চিহ্নিত।`,
                `States as of ${formatCalendarDate(destination.as_of, language)} (Dhaka date). Advisories verified more than ${destination.stale_after_days} days ago are flagged as not recently verified.`,
              )}
            </p>
          </section>

          {(destination.seasonality_bn || destination.seasonality_en) && (
            <section className="tonal-card p-6 flex flex-col gap-2">
              <h2 className="flex items-center gap-2 text-base font-bold font-title text-forest-primary dark:text-neon-lime">
                <Calendar size={18} aria-hidden="true" />
                {t('ভ্রমণের সময়', 'When to go')}
              </h2>
              <p className="text-sm font-body leading-relaxed text-on-surface dark:text-on-dark">
                {pick(language, destination.seasonality_bn, destination.seasonality_en)}
              </p>
            </section>
          )}

          <GuideSections items={destination.guide_items} />
        </div>

        <aside className="flex flex-col gap-6">
          {(destination.restrictions_bn || destination.restrictions_en) && (
            <section className="tonal-card p-6 flex flex-col gap-2">
              <h2 className="flex items-center gap-2 text-sm font-bold font-title text-on-surface dark:text-on-dark">
                <ShieldAlert size={16} className="text-amber-600 dark:text-amber-400" aria-hidden="true" />
                {t('বিধিনিষেধ', 'Restrictions')}
              </h2>
              <p className="text-sm font-body leading-relaxed text-on-surface-variant dark:text-on-dark-muted">
                {pick(language, destination.restrictions_bn, destination.restrictions_en)}
              </p>
            </section>
          )}

          <section className="tonal-card p-6 flex flex-col gap-3">
            <h2 className="flex items-center gap-2 text-sm font-bold font-title text-on-surface dark:text-on-dark">
              <Phone size={16} className="text-forest-primary dark:text-neon-lime" aria-hidden="true" />
              {t('জরুরি যোগাযোগ', 'Emergency contacts')}
            </h2>
            {destination.contacts.length === 0 ? (
              <p className="text-sm text-on-surface-variant">{t('কোনো যাচাইকৃত নম্বর নেই।', 'No verified numbers yet.')}</p>
            ) : (
              <ul className="flex flex-col gap-3">
                {destination.contacts.map((contact) => (
                  <li key={contact.id} className="flex flex-col gap-1">
                    <span className="text-sm font-semibold text-on-surface dark:text-on-dark">{pick(language, contact.name_bn, contact.name_en)}</span>
                    <a
                      href={`tel:${contact.phone.replace(/[\s-]/g, '')}`}
                      className="self-start inline-flex items-center gap-2 min-h-[44px] px-4 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-sm font-bold font-en"
                    >
                      <Phone size={14} aria-hidden="true" />
                      {contact.phone}
                    </a>
                    {contact.latitude !== null && contact.longitude !== null && (
                      <a
                        href={googleMapsUrl(contact.latitude, contact.longitude)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="self-start inline-flex items-center gap-1 min-h-[44px] text-xs font-semibold underline underline-offset-2 text-forest-primary dark:text-neon-lime"
                      >
                        <MapPin size={13} aria-hidden="true" />
                        {t('গুগল ম্যাপে দেখুন', 'Open in Google Maps')}
                        <ExternalLink size={11} aria-hidden="true" />
                      </a>
                    )}
                    <ProvenanceNote provenance={contact.provenance} />
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </div>

      <ReviewFeedSection destinationId={destination.id} />
    </div>
  );
};
