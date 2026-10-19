import React from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowLeft,
  Calendar,
  Compass,
  ExternalLink,
  MapPin,
  Phone,
  ShieldAlert,
} from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { getDestination } from '../api/destinations';
import { ApiError } from '../api/client';
import { useApiResource } from '../hooks/useApiResource';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StatusViews';
import { AdvisoryCard } from '../components/destination/AdvisoryCard';
import { ProvenanceNote } from '../components/destination/ProvenanceNote';
import { RatingSummary } from '../components/destination/RatingSummary';
import { ReviewFeedSection } from '../components/reviews/ReviewFeedSection';
import type { GuideCategory, GuideItem } from '../types';
import { formatCalendarDate, formatNumber, pick } from '../utils/format';

const CATEGORY_ORDER: GuideCategory[] = ['ATTRACTION', 'TRANSPORT', 'ACCOMMODATION', 'FOOD', 'LOCAL_PRACTICE'];
const CATEGORY_LABEL: Record<GuideCategory, [string, string]> = {
  ATTRACTION: ['দর্শনীয় স্থান', 'Attractions'],
  TRANSPORT: ['যাতায়াত', 'Getting there'],
  ACCOMMODATION: ['থাকার ব্যবস্থা', 'Accommodation'],
  FOOD: ['খাবার', 'Food'],
  LOCAL_PRACTICE: ['স্থানীয় রীতি ও আচরণ', 'Local practice'],
};

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export const DestinationDetailPage: React.FC = () => {
  const { id = '' } = useParams<{ id: string }>();
  const { language, t } = useLanguage();
  const validId = UUID_PATTERN.test(id);
  const { data: destination, error, loading, reload } = useApiResource(
    (signal) => (validId ? getDestination(id, { signal }) : Promise.reject(new ApiError(404, 'NOT_FOUND', ''))),
    [id],
  );

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
          <ErrorState error={error} onRetry={reload} />
        )}
      </div>
    );
  }

  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    items: destination.guide_items.filter((item: GuideItem) => item.category === category),
  })).filter((group) => group.items.length > 0);
  const hasCoordinates = destination.latitude !== null && destination.longitude !== null;

  return (
    <div className="flex flex-col gap-8 pb-12 max-w-5xl mx-auto">
      {backLink}

      {/* Header */}
      <header className="tonal-card p-6 sm:p-8 flex flex-col gap-4 bg-surface-sage/60 dark:bg-dark-surface-1">
        <div className="flex flex-wrap items-center gap-2 text-xs font-semibold text-on-surface-variant dark:text-on-dark-muted">
          <MapPin size={14} className="text-forest-primary dark:text-neon-lime" aria-hidden="true" />
          <span>{pick(language, destination.region_bn, destination.region_en)}</span>
          {hasCoordinates && (
            <a
              href={`https://www.openstreetmap.org/?mlat=${destination.latitude}&mlon=${destination.longitude}#map=11/${destination.latitude}/${destination.longitude}`}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 underline underline-offset-2 font-en"
            >
              {destination.latitude?.toFixed(4)}, {destination.longitude?.toFixed(4)}
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
        {destination.content_verified_on && (
          <p className="text-[11px] text-on-surface-variant dark:text-on-dark-muted">
            {t('কনটেন্ট যাচাই', 'Content verified')}: {formatCalendarDate(destination.content_verified_on, language)}
            {destination.content_licence && ` • ${destination.content_licence}`}
          </p>
        )}
      </header>

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

          {groups.map((group) => (
            <section key={group.category} className="tonal-card p-6 flex flex-col gap-4">
              <h2 className="flex items-center gap-2 text-base font-bold font-title text-forest-primary dark:text-neon-lime">
                <Compass size={18} aria-hidden="true" />
                {t(...CATEGORY_LABEL[group.category])}
              </h2>
              {group.items.map((item) => (
                <article key={item.id} className="flex flex-col gap-1.5 pb-4 border-b last:border-b-0 last:pb-0 border-surface-muted/30 dark:border-dark-surface-2">
                  <h3 className="text-sm font-bold font-title text-on-surface dark:text-on-dark">{pick(language, item.title_bn, item.title_en)}</h3>
                  <p className="text-sm font-body leading-relaxed text-on-surface-variant dark:text-on-dark-muted">{pick(language, item.body_bn, item.body_en)}</p>
                  <ProvenanceNote provenance={item.provenance} />
                </article>
              ))}
            </section>
          ))}
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
