import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Star, DownloadCloud, AlertTriangle, ShieldCheck } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { SEEDED_DESTINATIONS } from '../api/destinations';

export const DestinationsPage: React.FC = () => {
  const { language, t } = useLanguage();
  const [filter, setFilter] = useState<'all' | 'sea' | 'hills' | 'forest'>('all');

  const filteredDestinations = SEEDED_DESTINATIONS.filter((d) => {
    if (filter === 'sea') return d.id === 'coxs-bazar';
    if (filter === 'hills') return d.id === 'sajek-valley' || d.id === 'bandarban';
    if (filter === 'forest') return d.id === 'sundarbans' || d.id === 'sylhet';
    return true;
  });

  return (
    <div className="flex flex-col gap-6 pb-12">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold font-title text-on-surface dark:text-on-dark tracking-tight">
            {t('গন্তব্য ও কিউরেটেড ট্রাভেল গাইড', 'Destinations & Curated Guides')}
          </h1>
          <p className="text-sm text-on-surface-variant dark:text-on-dark-muted font-body mt-1">
            {t(
              'বাংলাদেশের ৫টি প্রধান সীডেড গন্তব্যের দ্বিভাষিক তথ্য, নিরাপত্তা সতর্কতা ও যোগাযোগের তালিকা।',
              'Bilingual profiles, active advisories, seasonality, and emergency contacts for 5 seeded locations.'
            )}
          </p>
        </div>

        {/* Filter Tabs */}
        <div className="flex items-center gap-1.5 p-1 rounded-full bg-surface-container dark:bg-dark-surface-1 border border-surface-muted/30 self-start md:self-auto overflow-x-auto max-w-full">
          <button
            onClick={() => setFilter('all')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold font-title transition-all ${
              filter === 'all'
                ? 'bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base shadow-sm'
                : 'text-on-surface-variant dark:text-on-dark-muted hover:text-on-surface'
            }`}
          >
            {t('সব গন্তব্য', 'All Guides')}
          </button>
          <button
            onClick={() => setFilter('hills')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold font-title transition-all ${
              filter === 'hills'
                ? 'bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base shadow-sm'
                : 'text-on-surface-variant dark:text-on-dark-muted hover:text-on-surface'
            }`}
          >
            {t('পাহাড় ও মেঘ', 'Hills & Clouds')}
          </button>
          <button
            onClick={() => setFilter('sea')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold font-title transition-all ${
              filter === 'sea'
                ? 'bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base shadow-sm'
                : 'text-on-surface-variant dark:text-on-dark-muted hover:text-on-surface'
            }`}
          >
            {t('সমুদ্র সৈকত', 'Sea Beach')}
          </button>
          <button
            onClick={() => setFilter('forest')}
            className={`px-3.5 py-1.5 rounded-full text-xs font-semibold font-title transition-all ${
              filter === 'forest'
                ? 'bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base shadow-sm'
                : 'text-on-surface-variant dark:text-on-dark-muted hover:text-on-surface'
            }`}
          >
            {t('অরণ্য ও হাওড়', 'Forest & Wetlands')}
          </button>
        </div>
      </div>

      {/* Destinations Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {filteredDestinations.map((dest) => (
          <div key={dest.id} className="tonal-card overflow-hidden flex flex-col justify-between group">
            <div>
              <div className="relative h-48 w-full overflow-hidden">
                <img
                  src={dest.coverImage}
                  alt={language === 'bn' ? dest.nameBn : dest.nameEn}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                />
                <div className="absolute top-3 left-3 flex items-center gap-1.5">
                  <span className="px-2.5 py-1 rounded-full bg-canvas-light/90 dark:bg-dark-surface-1/90 backdrop-blur-md text-[11px] font-bold text-forest-primary dark:text-neon-lime uppercase font-en">
                    {language === 'bn' ? dest.regionBn : dest.regionEn}
                  </span>
                  {dest.activeAdvisoriesCount > 0 && (
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/90 text-white text-[10px] font-bold flex items-center gap-1">
                      <AlertTriangle size={11} />
                      {dest.activeAdvisoriesCount}
                    </span>
                  )}
                </div>
                <div className="absolute bottom-3 right-3 flex items-center gap-1 px-2.5 py-1 rounded-full bg-black/60 backdrop-blur-md text-white text-xs font-en font-bold">
                  <Star size={12} className="text-yellow-400 fill-yellow-400" />
                  <span>{dest.rating.toFixed(1)}</span>
                  <span className="opacity-70 text-[10px]">({dest.reviewCount})</span>
                </div>
              </div>

              <div className="p-5 flex flex-col gap-2.5">
                <h3 className="text-xl font-bold font-title text-on-surface dark:text-on-dark group-hover:text-forest-primary dark:group-hover:text-neon-lime transition-colors">
                  {language === 'bn' ? dest.nameBn : dest.nameEn}
                </h3>
                <p className="text-xs text-on-surface-variant dark:text-on-dark-muted line-clamp-3 font-body leading-relaxed">
                  {language === 'bn' ? dest.descriptionBn : dest.descriptionEn}
                </p>

                <div className="flex flex-wrap gap-1.5 mt-1">
                  {(language === 'bn' ? dest.highlightsBn : dest.highlightsEn).slice(0, 3).map((h, i) => (
                    <span key={i} className="px-2 py-0.5 rounded-md bg-surface-container dark:bg-dark-surface-2 text-[11px] text-on-surface-variant dark:text-on-dark-muted">
                      {h}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <div className="p-5 pt-0">
              <div className="flex items-center justify-between py-2 border-t border-surface-muted/30 dark:border-dark-surface-2 text-xs text-on-surface-variant dark:text-on-dark-muted font-en mb-3">
                <div className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400 font-semibold">
                  <ShieldCheck size={14} />
                  <span>{t('বায়েসিয়ান ভেরিফাইড', 'Bayesian Verified')}</span>
                </div>
                <div className="flex items-center gap-1">
                  <DownloadCloud size={13} />
                  <span>{dest.offlinePackSizeMb} MB</span>
                </div>
              </div>

              <div className="flex items-center gap-2">
                <Link
                  to={`/destinations/${dest.id}`}
                  className="flex-1 text-center py-2 px-3 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-bold hover:opacity-95 transition-all font-title"
                >
                  {t('গাইড ও রিভিউ দেখুন', 'View Guide & Reviews')}
                </Link>
                <Link
                  to={`/planner?destination=${dest.id}`}
                  className="py-2 px-3 rounded-full bg-surface-sage dark:bg-dark-surface-2 text-forest-primary dark:text-neon-lime text-xs font-bold hover:bg-surface-container transition-all font-title"
                >
                  {t('বাজেট', 'Cost')}
                </Link>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
