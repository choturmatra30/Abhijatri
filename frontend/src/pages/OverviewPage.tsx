import React from 'react';
import { Link } from 'react-router-dom';
import { 
  MapPin, 
  Calculator, 
  DownloadCloud, 
  Sparkles, 
  ArrowRight, 
  ShieldCheck, 
  Activity,
  Star,
  CheckCircle2,
  Calendar,
  Layers
} from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { SEEDED_DESTINATIONS } from '../api/destinations';

export const OverviewPage: React.FC = () => {
  const { language, t } = useLanguage();
  const spotlight = SEEDED_DESTINATIONS[1]; // Sajek Valley

  return (
    <div className="flex flex-col gap-8 pb-12">
      {/* Top Welcome & Context */}
      <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 text-on-surface-variant dark:text-on-dark-muted text-xs font-semibold uppercase tracking-wider mb-1">
            <span className="text-forest-primary dark:text-neon-lime">অভিযাত্রী এক্সপেডিশন</span>
            <span>•</span>
            <span>CSE 3102 Semester MVP</span>
          </div>
          <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold font-title text-on-surface dark:text-on-dark tracking-tight">
            {t('স্বাগতম অভিযাত্রীতে', 'Welcome to Abhijatri')}
            <span className="block sm:inline font-normal text-on-surface-variant dark:text-on-dark-muted sm:ml-2 text-lg sm:text-2xl">
              {t('— বাংলা-ফার্স্ট অফলাইন ট্রাভেল প্ল্যাটফর্ম', '— Bangla-First Offline Travel Platform')}
            </span>
          </h1>
        </div>

        {/* Quick Action Badges */}
        <div className="flex items-center gap-2 flex-wrap">
          <Link
            to="/health"
            className="flex items-center gap-2 px-3.5 py-2 rounded-full bg-surface-container dark:bg-dark-surface-1 border border-surface-muted/30 text-xs font-semibold hover:border-forest-primary dark:hover:border-neon-lime transition-all"
          >
            <Activity size={14} className="text-forest-primary dark:text-neon-lime" />
            <span className="font-en">{t('সিস্টেম হেলথ চেক', 'Verify API Health')}</span>
          </Link>
          <Link
            to="/planner"
            className="flex items-center gap-2 px-4 py-2 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-semibold shadow-sm hover:opacity-95 transition-all"
          >
            <Calculator size={14} />
            <span className="font-title">{t('খরচ অনুমান করুন', 'Calculate Trip Cost')}</span>
          </Link>
        </div>
      </div>

      {/* 4 Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Stat 1 */}
        <div className="tonal-card p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between text-on-surface-variant dark:text-on-dark-muted">
            <span className="text-xs uppercase font-bold font-en tracking-wider">{t('সীডেড গন্তব্য', 'Seeded Profiles')}</span>
            <MapPin size={18} className="text-accent-green dark:text-neon-lime" />
          </div>
          <div className="my-2">
            <span className="text-3xl font-bold font-en text-forest-primary dark:text-neon-lime">5</span>
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted mt-0.5">
              {t('কক্সবাজার, সাজেক, সিলেট, সুন্দরবন, বান্দরবান', "Cox's Bazar, Sajek, Sylhet, Sundarbans, Bandarban")}
            </p>
          </div>
          <div className="flex items-center gap-1 text-[11px] text-forest-primary dark:text-emerald-accent font-medium">
            <CheckCircle2 size={13} />
            <span>{t('গবেষণালব্ধ ও দ্বিভাষিক গাইড প্রস্তুত', 'Researched & Bilingual Ready')}</span>
          </div>
        </div>

        {/* Stat 2 */}
        <div className="tonal-card p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between text-on-surface-variant dark:text-on-dark-muted">
            <span className="text-xs uppercase font-bold font-en tracking-wider">{t('অফলাইন প্যাক', 'Offline Cache')}</span>
            <DownloadCloud size={18} className="text-accent-green dark:text-neon-lime" />
          </div>
          <div className="my-2">
            <span className="text-3xl font-bold font-en text-forest-primary dark:text-neon-lime">10/10</span>
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted mt-0.5">
              {t('এয়ারপ্লেন মোড টেস্টিং টার্গেট', 'Airplane Mode Target (O4)')}
            </p>
          </div>
          <div className="flex items-center gap-1 text-[11px] text-on-surface-variant dark:text-on-dark-muted font-medium">
            <Layers size={13} />
            <span>{t('IndexedDB প্যাক স্টোরেজ সক্রিয়', 'IndexedDB Pack Storage Active')}</span>
          </div>
        </div>

        {/* Stat 3 */}
        <div className="tonal-card p-5 flex flex-col justify-between">
          <div className="flex items-center justify-between text-on-surface-variant dark:text-on-dark-muted">
            <span className="text-xs uppercase font-bold font-en tracking-wider">{t('বেয়সিয়ান রেটিং', 'Bayesian Rating')}</span>
            <Star size={18} className="text-accent-green dark:text-neon-lime" />
          </div>
          <div className="my-2">
            <span className="text-3xl font-bold font-en text-forest-primary dark:text-neon-lime">4.85</span>
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted mt-0.5">
              {t('ফিক্সড-প্রাইর স্বচ্ছ স্কোরিং', 'Fixed-Prior Transparent Score')}
            </p>
          </div>
          <div className="flex items-center gap-1 text-[11px] text-forest-primary dark:text-emerald-accent font-medium">
            <ShieldCheck size={13} />
            <span>{t('মডারেশন নিশ্চিতকরণ ফিল্টারযুক্ত', 'Moderated & Safe Aggregation')}</span>
          </div>
        </div>

        {/* Stat 4 */}
        <div className="tonal-card p-5 bg-surface-sage/70 dark:bg-dark-surface-2 flex flex-col justify-between border-forest-container/20">
          <div className="flex items-center justify-between text-forest-primary dark:text-neon-lime">
            <span className="text-xs uppercase font-bold font-en tracking-wider">{t('খরচ নির্ধারণ রুলস', 'Deterministic Engine')}</span>
            <Calculator size={18} />
          </div>
          <div className="my-2">
            <span className="text-3xl font-bold font-en text-forest-primary dark:text-neon-lime">BDT 10</span>
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted mt-0.5">
              {t('ব্যাখ্যাযোগ্য ও নিরপেক্ষ হিসাবায়ন', 'Explainable Rule-Based Estimate')}
            </p>
          </div>
          <div className="flex items-center gap-1 text-[11px] text-forest-primary dark:text-neon-lime font-medium">
            <Sparkles size={13} />
            <span>{t('শেয়ার্ড ও ব্যক্তিগত খরচ পৃথক', 'Shared & Person Split')}</span>
          </div>
        </div>
      </div>

      {/* Spotlight Destination Hero (Sajek Valley) */}
      <div className="relative rounded-2xl overflow-hidden bg-surface-container/60 dark:bg-dark-surface-1 border border-surface-muted/30 shadow-sm">
        <div className="grid grid-cols-1 lg:grid-cols-12 min-h-[360px]">
          <div className="lg:col-span-7 relative min-h-[260px] lg:min-h-full">
            <img 
              src={spotlight.coverImage} 
              alt={language === 'bn' ? spotlight.nameBn : spotlight.nameEn}
              className="absolute inset-0 w-full h-full object-cover"
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent lg:hidden" />
            <div className="absolute top-4 left-4 flex gap-2">
              <span className="px-3 py-1 rounded-full bg-canvas-light/90 dark:bg-dark-surface-1/90 backdrop-blur-md text-forest-primary dark:text-neon-lime text-xs font-bold uppercase font-en shadow-sm">
                {t('স্পটলাইট গন্তব্য', 'Featured Destination')}
              </span>
              <span className="px-3 py-1 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-bold uppercase font-en">
                {t('মেঘের উপত্যকা', 'Cloud Realm')}
              </span>
            </div>
          </div>

          <div className="lg:col-span-5 p-6 lg:p-8 flex flex-col justify-between">
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2 text-on-surface-variant dark:text-on-dark-muted text-xs">
                <Calendar size={15} className="text-accent-green" />
                <span>{language === 'bn' ? spotlight.seasonalityBn : spotlight.seasonalityEn}</span>
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold font-title text-on-surface dark:text-on-dark">
                {language === 'bn' ? spotlight.nameBn : spotlight.nameEn}
              </h2>
              <p className="text-sm text-on-surface-variant dark:text-on-dark-muted leading-relaxed font-body">
                {language === 'bn' ? spotlight.descriptionBn : spotlight.descriptionEn}
              </p>
              
              <div className="flex flex-wrap gap-1.5 mt-2">
                {(language === 'bn' ? spotlight.highlightsBn : spotlight.highlightsEn).map((h, i) => (
                  <span key={i} className="px-2.5 py-1 rounded-full bg-surface-container-high dark:bg-dark-surface-2 text-xs font-medium">
                    {h}
                  </span>
                ))}
              </div>
            </div>

            <div className="flex items-center gap-3 pt-6 border-t border-surface-muted/30 dark:border-dark-surface-2">
              <Link
                to={`/destinations/${spotlight.id}`}
                className="flex-1 text-center py-2.5 px-4 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-bold shadow-sm hover:opacity-90 transition-all font-title"
              >
                {t('সম্পূর্ণ গাইড দেখুন', 'Explore Full Guide')}
              </Link>
              <Link
                to="/planner"
                className="py-2.5 px-4 rounded-full bg-surface-sage dark:bg-dark-surface-2 text-forest-primary dark:text-neon-lime text-xs font-bold hover:bg-surface-container transition-all font-title"
              >
                {t('বাজেট তৈরি করুন', 'Estimate Budget')}
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Seeded Destinations Section */}
      <div className="flex flex-col gap-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-xl sm:text-2xl font-bold font-title text-on-surface dark:text-on-dark">
              {t('৫টি সীডেড ট্রাভেল গন্তব্য', '5 Seeded Travel Destinations')}
            </h3>
            <p className="text-xs sm:text-sm text-on-surface-variant dark:text-on-dark-muted font-body">
              {t('তারিখ-ভিত্তিক গাইডলাইন, যোগাযোগ নম্বর ও নিরাপত্তা সতর্কতা সংবলিত', 'Source-dated guidance, direct contacts & seasonal advisories')}
            </p>
          </div>
          <Link
            to="/destinations"
            className="flex items-center gap-1 text-xs font-bold text-forest-primary dark:text-neon-lime hover:underline font-en"
          >
            <span>{t('সব গন্তব্য', 'View All')}</span>
            <ArrowRight size={14} />
          </Link>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {SEEDED_DESTINATIONS.slice(0, 3).map((dest) => (
            <Link
              key={dest.id}
              to={`/destinations/${dest.id}`}
              className="tonal-card overflow-hidden flex flex-col group"
            >
              <div className="relative h-44 w-full overflow-hidden">
                <img
                  src={dest.coverImage}
                  alt={language === 'bn' ? dest.nameBn : dest.nameEn}
                  className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500"
                />
                <div className="absolute top-3 left-3">
                  <span className="px-2.5 py-0.5 rounded-full bg-canvas-light/90 dark:bg-dark-surface-1/90 backdrop-blur-md text-[11px] font-bold text-forest-primary dark:text-neon-lime uppercase font-en">
                    {language === 'bn' ? dest.regionBn : dest.regionEn}
                  </span>
                </div>
                <div className="absolute bottom-3 right-3 flex items-center gap-1 px-2 py-0.5 rounded-full bg-black/60 backdrop-blur-md text-white text-xs font-en font-bold">
                  <Star size={12} className="text-yellow-400 fill-yellow-400" />
                  <span>{dest.rating.toFixed(1)}</span>
                </div>
              </div>

              <div className="p-4 flex flex-col justify-between flex-1 gap-3">
                <div>
                  <h4 className="text-lg font-bold font-title text-on-surface dark:text-on-dark group-hover:text-forest-primary dark:group-hover:text-neon-lime transition-colors">
                    {language === 'bn' ? dest.nameBn : dest.nameEn}
                  </h4>
                  <p className="text-xs text-on-surface-variant dark:text-on-dark-muted line-clamp-2 mt-1 font-body">
                    {language === 'bn' ? dest.descriptionBn : dest.descriptionEn}
                  </p>
                </div>

                <div className="flex items-center justify-between pt-2 border-t border-surface-muted/30 dark:border-dark-surface-2 text-xs text-on-surface-variant dark:text-on-dark-muted font-en">
                  <span>{dest.reviewCount} {t('রিভিউ', 'reviews')}</span>
                  <span className="text-forest-primary dark:text-neon-lime font-semibold">
                    {dest.offlinePackSizeMb} MB Pack
                  </span>
                </div>
              </div>
            </Link>
          ))}
        </div>
      </div>
    </div>
  );
};
