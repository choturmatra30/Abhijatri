import React, { useMemo, useState } from 'react';
import { Bed, Bus, Compass, HandHeart, Landmark, Search, Utensils, type LucideIcon } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import type { GuideCategory, GuideItem } from '../../types';
import { filterGuideItems } from '../../utils/destinationSort';
import { formatNumber, pick } from '../../utils/format';
import { EmptyState } from '../common/StatusViews';
import { ProvenanceNote } from './ProvenanceNote';

const CATEGORY_ORDER: GuideCategory[] = ['ATTRACTION', 'TRANSPORT', 'ACCOMMODATION', 'FOOD', 'LOCAL_PRACTICE'];
const CATEGORY: Record<GuideCategory, { label: [string, string]; icon: LucideIcon }> = {
  ATTRACTION: { label: ['দর্শনীয় স্থান', 'Attractions'], icon: Landmark },
  TRANSPORT: { label: ['যাতায়াত', 'Getting there'], icon: Bus },
  ACCOMMODATION: { label: ['থাকার ব্যবস্থা', 'Accommodation'], icon: Bed },
  FOOD: { label: ['খাবার', 'Food'], icon: Utensils },
  LOCAL_PRACTICE: { label: ['স্থানীয় রীতি ও আচরণ', 'Local practice'], icon: HandHeart },
};

type Filter = GuideCategory | 'ALL';

/**
 * The guide of one destination, browsable by type and by words (Phase 1 update, 11 Nov 2026).
 * The API sends guide entries as text under five types; it has no separate places with their own map
 * point or rating yet (Handoff-Backend P1), so the filter and search work on these entries. Everything
 * is filtered on the device, so it also works offline from a pack or a saved page.
 */
export const GuideSections: React.FC<{ items: GuideItem[] }> = ({ items }) => {
  const { language, t } = useLanguage();
  const [filter, setFilter] = useState<Filter>('ALL');
  const [query, setQuery] = useState('');

  const present = CATEGORY_ORDER.filter((category) => items.some((item) => item.category === category));
  // A type can disappear when the content changes (pack update); fall back to All.
  const active: Filter = filter !== 'ALL' && !present.includes(filter) ? 'ALL' : filter;
  const visible = useMemo(() => filterGuideItems(items, active, query), [items, active, query]);

  if (items.length === 0) return null;

  const groups = CATEGORY_ORDER.map((category) => ({
    category,
    items: visible.filter((item) => item.category === category),
  })).filter((group) => group.items.length > 0);

  const chip = (value: Filter, label: string, count: number, Icon: LucideIcon) => {
    const selected = active === value;
    return (
      <button
        key={value}
        type="button"
        aria-pressed={selected}
        onClick={() => setFilter(value)}
        className={`inline-flex items-center gap-1.5 min-h-[44px] px-3.5 rounded-full text-xs font-bold font-title border transition-colors ${
          selected
            ? 'bg-forest-primary text-white border-forest-primary dark:bg-neon-lime dark:text-dark-bg-base dark:border-neon-lime'
            : 'bg-surface-sage/50 dark:bg-dark-surface-1 text-on-surface dark:text-on-dark border-surface-muted/40 dark:border-dark-surface-2 hover:border-forest-primary dark:hover:border-neon-lime'
        }`}
      >
        <Icon size={14} aria-hidden="true" />
        {label}
        <span className="opacity-75 font-normal">{formatNumber(count, language)}</span>
      </button>
    );
  };

  return (
    <section aria-labelledby="guide-heading" className="flex flex-col gap-4">
      <div className="tonal-card p-5 flex flex-col gap-3">
        <h2 id="guide-heading" className="flex items-center gap-2 text-base font-bold font-title text-forest-primary dark:text-neon-lime">
          <Compass size={18} aria-hidden="true" />
          {t('ভ্রমণ গাইড', 'Travel guide')}
        </h2>
        <div role="group" aria-label={t('ধরন অনুযায়ী দেখুন', 'Show by type')} className="flex flex-wrap gap-2">
          {chip('ALL', t('সব', 'All'), items.length, Compass)}
          {present.map((category) =>
            chip(category, t(...CATEGORY[category].label), items.filter((item) => item.category === category).length, CATEGORY[category].icon),
          )}
        </div>
        <label className="relative w-full sm:max-w-sm">
          <span className="sr-only">{t('গাইডে খুঁজুন', 'Search the guide')}</span>
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant" size={16} aria-hidden="true" />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={t('নাম বা শব্দ দিয়ে খুঁজুন', 'Search by name or word')}
            className="w-full pl-10 pr-4 min-h-[44px] rounded-full bg-surface-sage/50 dark:bg-dark-surface-1 border border-surface-muted/40 dark:border-dark-surface-2 text-sm text-on-surface dark:text-on-dark"
          />
        </label>
        <p role="status" className="sr-only">
          {t(`${formatNumber(visible.length, language)}টি ফলাফল`, `${visible.length} result${visible.length === 1 ? '' : 's'}`)}
        </p>
      </div>

      {groups.length === 0 && (
        <EmptyState
          variant="no-results"
          title={t('গাইডে কিছু মেলেনি', 'Nothing in the guide matches')}
          hint={t('অন্য শব্দ দিয়ে খুঁজুন বা সব ধরন দেখুন; বাংলা ও ইংরেজি দুই ভাষাতেই খোঁজা যায়।', 'Try another word or show all types; Bangla and English both work.')}
          action={
            <button
              type="button"
              onClick={() => {
                setQuery('');
                setFilter('ALL');
              }}
              className="min-h-[44px] px-4 text-sm font-bold underline underline-offset-2 text-forest-primary dark:text-neon-lime"
            >
              {t('সব দেখান', 'Show everything')}
            </button>
          }
        />
      )}

      {groups.map((group) => {
        const Icon = CATEGORY[group.category].icon;
        return (
          <section key={group.category} className="tonal-card p-6 flex flex-col gap-4">
            <h3 className="flex items-center gap-2 text-base font-bold font-title text-forest-primary dark:text-neon-lime">
              <Icon size={18} aria-hidden="true" />
              {t(...CATEGORY[group.category].label)}
            </h3>
            {group.items.map((item) => (
              <article key={item.id} className="flex flex-col gap-1.5 pb-4 border-b last:border-b-0 last:pb-0 border-surface-muted/30 dark:border-dark-surface-2">
                <h4 className="text-sm font-bold font-title text-on-surface dark:text-on-dark">{pick(language, item.title_bn, item.title_en)}</h4>
                <p className="text-sm font-body leading-relaxed text-on-surface-variant dark:text-on-dark-muted">{pick(language, item.body_bn, item.body_en)}</p>
                <ProvenanceNote provenance={item.provenance} />
              </article>
            ))}
          </section>
        );
      })}
    </section>
  );
};
