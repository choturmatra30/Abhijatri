import React from 'react';
import { AlertOctagon, AlertTriangle, Clock, Info } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import type { Advisory, AdvisorySeverity, AdvisoryState } from '../../types';
import { formatCalendarDate, pick } from '../../utils/format';
import { ProvenanceNote } from './ProvenanceNote';

const SEVERITY_STYLE: Record<AdvisorySeverity, { icon: typeof Info; box: string; ink: string }> = {
  INFO: {
    icon: Info,
    box: 'bg-sky-50 border-sky-200 dark:bg-sky-950/30 dark:border-sky-900/50',
    ink: 'text-sky-900 dark:text-sky-200',
  },
  CAUTION: {
    icon: AlertTriangle,
    box: 'bg-amber-50 border-amber-200 dark:bg-amber-950/30 dark:border-amber-900/50',
    ink: 'text-amber-900 dark:text-amber-200',
  },
  WARNING: {
    icon: AlertTriangle,
    box: 'bg-orange-50 border-orange-300 dark:bg-orange-950/30 dark:border-orange-900/60',
    ink: 'text-orange-900 dark:text-orange-200',
  },
  CRITICAL: {
    icon: AlertOctagon,
    box: 'bg-red-50 border-red-300 dark:bg-red-950/30 dark:border-red-900/60',
    ink: 'text-red-900 dark:text-red-200',
  },
};

const SEVERITY_LABEL: Record<AdvisorySeverity, [string, string]> = {
  INFO: ['তথ্য', 'Information'],
  CAUTION: ['সতর্কতা', 'Caution'],
  WARNING: ['জরুরি সতর্কতা', 'Warning'],
  CRITICAL: ['গুরুতর', 'Critical'],
};

/** Expired is never shown as current; stale is flagged (Proposal "Advisory freshness"). */
const STATE_LABEL: Record<AdvisoryState, [string, string]> = {
  CURRENT: ['বর্তমান', 'Current'],
  STALE: ['পুরনো যাচাই', 'Not recently verified'],
  EXPIRED: ['মেয়াদোত্তীর্ণ', 'Expired'],
  NOT_YET_EFFECTIVE: ['এখনো কার্যকর নয়', 'Not yet in effect'],
};

export const AdvisoryCard: React.FC<{ advisory: Advisory }> = ({ advisory }) => {
  const { language, t } = useLanguage();
  const style = SEVERITY_STYLE[advisory.severity];
  const Icon = style.icon;
  const muted = advisory.state === 'EXPIRED' || advisory.state === 'STALE';

  return (
    <article className={`p-4 rounded-xl border flex flex-col gap-2 ${style.box} ${muted ? 'opacity-80' : ''}`}>
      <header className={`flex flex-wrap items-center gap-2 text-xs font-semibold ${style.ink}`}>
        <Icon size={16} aria-hidden="true" />
        <span>{t(...SEVERITY_LABEL[advisory.severity])}</span>
        <span aria-hidden="true">•</span>
        <span className={advisory.state === 'CURRENT' ? '' : 'inline-flex items-center gap-1 underline decoration-dotted'}>
          {advisory.state !== 'CURRENT' && <Clock size={12} aria-hidden="true" />}
          {t(...STATE_LABEL[advisory.state])}
        </span>
        <span className="ml-auto font-normal">
          {t('মেয়াদ', 'Valid until')}: {formatCalendarDate(advisory.valid_until, language)}
        </span>
      </header>
      <h4 className={`text-sm font-bold font-title ${style.ink}`}>{pick(language, advisory.title_bn, advisory.title_en)}</h4>
      <p className={`text-sm font-body leading-relaxed ${style.ink}`}>{pick(language, advisory.text_bn, advisory.text_en)}</p>
      <ProvenanceNote provenance={advisory.provenance} />
    </article>
  );
};
