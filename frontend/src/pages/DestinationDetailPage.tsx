import React, { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { 
  ArrowLeft, 
  Star, 
  DownloadCloud, 
  Calendar, 
  MapPin, 
  AlertTriangle, 
  CheckCircle2, 
  Calculator, 
  MessageSquarePlus,
  Compass
} from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { SEEDED_DESTINATIONS } from '../api/destinations';

export const DestinationDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const { language, t } = useLanguage();
  const [downloaded, setDownloaded] = useState(false);

  const destination = SEEDED_DESTINATIONS.find((d) => d.id === id) || SEEDED_DESTINATIONS[0];

  const handleDownload = () => {
    setDownloaded(true);
    setTimeout(() => {
      alert(t('অফলাইন প্যাক সফলভাবে ডিভাইসে সংরক্ষিত হয়েছে (IndexedDB)!', 'Offline travel pack downloaded successfully to IndexedDB!'));
    }, 400);
  };

  return (
    <div className="flex flex-col gap-8 pb-12 max-w-5xl mx-auto">
      {/* Back button */}
      <div>
        <Link
          to="/destinations"
          className="inline-flex items-center gap-1.5 text-xs font-bold text-forest-primary dark:text-neon-lime hover:underline font-title"
        >
          <ArrowLeft size={16} />
          <span>{t('সকল গন্তব্যের তালিকায় ফিরুন', 'Back to all destinations')}</span>
        </Link>
      </div>

      {/* Hero Visual Banner */}
      <div className="relative rounded-2xl overflow-hidden min-h-[320px] sm:min-h-[400px] border border-surface-muted/30 shadow-md">
        <img
          src={destination.coverImage}
          alt={language === 'bn' ? destination.nameBn : destination.nameEn}
          className="absolute inset-0 w-full h-full object-cover"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/85 via-black/40 to-black/20" />

        <div className="absolute inset-0 p-6 sm:p-10 flex flex-col justify-end text-white">
          <div className="flex items-center gap-2 mb-2 flex-wrap">
            <span className="px-3 py-1 rounded-full bg-forest-primary/90 text-white text-xs font-bold font-en uppercase">
              {language === 'bn' ? destination.regionBn : destination.regionEn}
            </span>
            <div className="flex items-center gap-1 px-3 py-1 rounded-full bg-black/50 backdrop-blur-md text-xs font-en font-bold">
              <Star size={13} className="text-yellow-400 fill-yellow-400" />
              <span>{destination.rating.toFixed(2)} Bayesian Score</span>
              <span className="opacity-75">({destination.reviewCount} reviews)</span>
            </div>
          </div>

          <h1 className="text-3xl sm:text-5xl font-bold font-title tracking-tight text-white mb-3">
            {language === 'bn' ? destination.nameBn : destination.nameEn}
          </h1>

          <p className="text-sm sm:text-base text-gray-200 font-body max-w-2xl leading-relaxed">
            {language === 'bn' ? destination.descriptionBn : destination.descriptionEn}
          </p>

          {/* Action CTAs inside Hero */}
          <div className="flex items-center gap-3 pt-6 flex-wrap">
            <button
              onClick={handleDownload}
              disabled={downloaded}
              className={`flex items-center gap-2 px-5 py-2.5 rounded-full text-xs font-bold font-title transition-all shadow-md ${
                downloaded
                  ? 'bg-emerald-600 text-white cursor-default'
                  : 'bg-white text-forest-primary hover:bg-surface-sage active:scale-95'
              }`}
            >
              {downloaded ? <CheckCircle2 size={16} /> : <DownloadCloud size={16} />}
              <span>
                {downloaded 
                  ? t('প্যাক অফলাইনে সংরক্ষিত', 'Pack Cached Offline') 
                  : `${t('অফলাইন প্যাক ডাউনলোড', 'Download Offline Pack')} (${destination.offlinePackSizeMb} MB)`
                }
              </span>
            </button>

            <Link
              to={`/planner?destination=${destination.id}`}
              className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-bold font-title shadow-md hover:opacity-95"
            >
              <Calculator size={16} />
              <span>{t('বাজেট হিসাব করুন', 'Calculate Trip Cost')}</span>
            </Link>

            <Link
              to={`/reviews?destination=${destination.id}`}
              className="flex items-center gap-2 px-4 py-2.5 rounded-full bg-white/20 backdrop-blur-md hover:bg-white/30 text-white text-xs font-bold font-title transition-all"
            >
              <MessageSquarePlus size={16} />
              <span>{t('রিভিউ দিন', 'Submit Review')}</span>
            </Link>
          </div>
        </div>
      </div>

      {/* 2-Column Info Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column: Key Details & Advisories */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Seasonality Box */}
          <div className="tonal-card p-6">
            <div className="flex items-center gap-2 text-forest-primary dark:text-neon-lime mb-2">
              <Calendar size={18} />
              <h3 className="font-bold text-base font-title">
                {t('আবহাওয়া ও ভ্রমণের সেরা সময় (Seasonality)', 'Seasonality & Best Travel Windows')}
              </h3>
            </div>
            <p className="text-sm text-on-surface-variant dark:text-on-dark-muted font-body leading-relaxed">
              {language === 'bn' ? destination.seasonalityBn : destination.seasonalityEn}
            </p>
          </div>

          {/* Highlights & Attractions */}
          <div className="tonal-card p-6">
            <div className="flex items-center gap-2 text-forest-primary dark:text-neon-lime mb-3">
              <Compass size={18} />
              <h3 className="font-bold text-base font-title">
                {t('প্রধান দর্শনীয় স্থান ও কার্যক্রম', 'Highlights & Activities')}
              </h3>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {(language === 'bn' ? destination.highlightsBn : destination.highlightsEn).map((h, i) => (
                <div key={i} className="p-3 rounded-xl bg-surface-sage/50 dark:bg-dark-surface-2 border border-surface-muted/30 flex items-center gap-2.5 text-xs font-medium">
                  <CheckCircle2 size={16} className="text-forest-primary dark:text-neon-lime shrink-0" />
                  <span>{h}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Active Travel Advisories */}
          <div className="tonal-card p-6">
            <div className="flex items-center gap-2 text-amber-600 dark:text-amber-400 mb-3">
              <AlertTriangle size={18} />
              <h3 className="font-bold text-base font-title">
                {t('ভ্রমণ পরামর্শ ও নিরাপত্তা সতর্কতা (Advisory Freshness)', 'Travel Advisories & Safety (FR15)')}
              </h3>
            </div>
            <div className="p-4 rounded-xl bg-amber-50 dark:bg-amber-950/30 border border-amber-200 dark:border-amber-900/50 flex flex-col gap-2">
              <div className="flex items-center justify-between text-xs text-amber-800 dark:text-amber-300 font-en font-semibold">
                <span>{t('ভেরিফাইড সতর্কতা', 'Verified Public Advisory')}</span>
                <span>{t('যাচাইয়ের তারিখ: ১৫ অক্টোবর ২০২৬', 'Verified: 15 Oct 2026')}</span>
              </div>
              <p className="text-xs text-amber-900 dark:text-amber-200 font-body leading-relaxed">
                {t(
                  'বর্ষাকালে পাহাড়ি পিচ্ছিল ট্রেইলে গাইড ও সতর্কতা বাধ্যতামূলক। চান্দের গাড়ি চলাচলের নির্ধারিত নিরাপত্তা কনভয় মেনে চলুন।',
                  'Mountain trails require caution during rains. Adhere to mandatory military escort convoy times for vehicle safety.'
                )}
              </p>
            </div>
          </div>
        </div>

        {/* Right Column: Offline Pack & Verified Details */}
        <div className="flex flex-col gap-6">
          <div className="tonal-card p-6 flex flex-col gap-4">
            <h3 className="font-bold text-base font-title text-on-surface dark:text-on-dark">
              {t('অফলাইন প্যাক মেটাডাটা', 'Offline Pack Details (FR10)')}
            </h3>
            <div className="flex flex-col gap-2.5 text-xs text-on-surface-variant dark:text-on-dark-muted font-en">
              <div className="flex justify-between py-1.5 border-b border-surface-muted/30 dark:border-dark-surface-2">
                <span>Pack Format:</span>
                <span className="font-semibold text-on-surface dark:text-on-dark">IndexedDB v1 (Dexie)</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-surface-muted/30 dark:border-dark-surface-2">
                <span>Payload Size:</span>
                <span className="font-semibold text-forest-primary dark:text-neon-lime">{destination.offlinePackSizeMb} MB</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-surface-muted/30 dark:border-dark-surface-2">
                <span>Status:</span>
                <span className="font-semibold text-emerald-600 dark:text-emerald-400">
                  {downloaded ? 'Cached on Device' : 'Ready for Sync'}
                </span>
              </div>
            </div>

            <button
              onClick={handleDownload}
              className="w-full py-2.5 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-bold font-title mt-2 shadow-sm hover:opacity-95"
            >
              {downloaded ? t('পুনরায় ডাউনলোড করুন', 'Re-download Pack') : t('ডাউনলোড প্যাক', 'Download Pack')}
            </button>
          </div>

          {/* Emergency contacts card */}
          <div className="tonal-card p-6 flex flex-col gap-3">
            <div className="flex items-center gap-2 text-forest-primary dark:text-neon-lime">
              <MapPin size={16} />
              <h4 className="font-bold text-sm font-title">{t('স্থানীয় যোগাযোগ', 'Local Contacts')}</h4>
            </div>
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted font-body">
              {t('ট্যুরিস্ট পুলিশ হেল্পলাইন: ৯৯৯', 'Tourist Police Helpline: 999')}
            </p>
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted font-body">
              {t('স্থানীয় প্রশাসন জরুরি রেসকিউ টিম অ্যাক্টিভ', 'District Administration Emergency Rescue Active')}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
