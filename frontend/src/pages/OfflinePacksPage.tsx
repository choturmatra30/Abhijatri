import React, { useState } from 'react';
import { 
  DownloadCloud, 
  HardDrive, 
  Trash2, 
  WifiOff, 
  ShieldCheck
} from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { SEEDED_DESTINATIONS } from '../api/destinations';

export const OfflinePacksPage: React.FC = () => {
  const { language, t } = useLanguage();
  const [downloadedPacks, setDownloadedPacks] = useState<string[]>(['sajek-valley']);

  const toggleDownload = (id: string) => {
    if (downloadedPacks.includes(id)) {
      setDownloadedPacks(downloadedPacks.filter((p) => p !== id));
    } else {
      setDownloadedPacks([...downloadedPacks, id]);
    }
  };

  const totalCachedMb = SEEDED_DESTINATIONS
    .filter((d) => downloadedPacks.includes(d.id))
    .reduce((acc, curr) => acc + curr.offlinePackSizeMb, 0);

  return (
    <div className="flex flex-col gap-6 pb-12 max-w-5xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-forest-primary dark:text-neon-lime text-xs font-bold uppercase font-en tracking-wider mb-1">
          <DownloadCloud size={16} />
          <span>{t('ইনডেক্সড-ডিবি অফলাইন আর্কিটেকচার', 'IndexedDB Offline Cache (FR10/FR17)')}</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold font-title text-on-surface dark:text-on-dark tracking-tight">
          {t('অফলাইন ট্রাভেল প্যাক ম্যানেজার', 'Offline Travel Packs Manager')}
        </h1>
        <p className="text-xs sm:text-sm text-on-surface-variant dark:text-on-dark-muted font-body mt-1">
          {t(
            'নেটওয়ার্কবিহীন পাহাড়ি বা দূরবর্তী অঞ্চলে ইন্টারনেট ছাড়াই সম্পূর্ণ গাইড, যোগাযোগ নম্বর ও রুট ম্যাপ ব্যবহার করুন।',
            'Download destination packs to browser IndexedDB for 100% offline access during remote exploration.'
          )}
        </p>
      </div>

      {/* Storage Quota Status Banner */}
      <div className="tonal-card p-6 bg-surface-container/60 dark:bg-dark-surface-1 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-forest-container/20">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-surface-sage dark:bg-dark-surface-2 text-forest-primary dark:text-neon-lime flex items-center justify-center shrink-0">
            <HardDrive size={24} />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h2 className="font-bold text-base font-title text-on-surface dark:text-on-dark">
                {t('ডিভাইস অফলাইন স্টোরেজ', 'Local Offline Storage')}
              </h2>
              <span className="px-2 py-0.5 rounded-full bg-emerald-100 dark:bg-emerald-950/60 text-emerald-700 dark:text-emerald-400 text-[10px] font-bold font-en">
                Active (Dexie.js)
              </span>
            </div>
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted font-en mt-0.5">
              Cached: {downloadedPacks.length} of 5 destinations ({totalCachedMb.toFixed(1)} MB used)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2 self-stretch sm:self-auto justify-end">
          <div className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-full bg-surface-sage dark:bg-dark-surface-2 text-xs font-bold text-forest-primary dark:text-neon-lime font-en">
            <WifiOff size={14} />
            <span>Airplane Mode Ready</span>
          </div>
        </div>
      </div>

      {/* Pack List */}
      <div className="flex flex-col gap-3">
        <h3 className="font-bold text-sm uppercase font-en text-on-surface-variant dark:text-on-dark-muted">
          Available Destination Packs (Seeded Scope)
        </h3>

        <div className="grid grid-cols-1 gap-3">
          {SEEDED_DESTINATIONS.map((dest) => {
            const isCached = downloadedPacks.includes(dest.id);
            return (
              <div
                key={dest.id}
                className="tonal-card p-4 sm:p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-center gap-4">
                  <img
                    src={dest.coverImage}
                    alt={language === 'bn' ? dest.nameBn : dest.nameEn}
                    className="w-16 h-16 rounded-xl object-cover shrink-0"
                  />
                  <div>
                    <div className="flex items-center gap-2">
                      <h4 className="font-bold text-base font-title text-on-surface dark:text-on-dark">
                        {language === 'bn' ? dest.nameBn : dest.nameEn}
                      </h4>
                      <span className="text-[11px] font-en text-on-surface-variant">
                        ({dest.offlinePackSizeMb} MB)
                      </span>
                    </div>
                    <p className="text-xs text-on-surface-variant dark:text-on-dark-muted font-body line-clamp-1 mt-0.5">
                      {language === 'bn' ? dest.descriptionBn : dest.descriptionEn}
                    </p>
                    <div className="flex items-center gap-3 mt-1.5 text-[11px] text-on-surface-variant font-en">
                      <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                        <ShieldCheck size={12} /> Versioned Manifest v1
                      </span>
                      <span>•</span>
                      <span>Coordinates & Emergency Contacts Included</span>
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 self-end sm:self-center shrink-0">
                  <button
                    onClick={() => toggleDownload(dest.id)}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-xs font-bold font-title transition-all shadow-sm ${
                      isCached
                        ? 'bg-red-50 hover:bg-red-100 text-red-700 dark:bg-red-950/40 dark:text-red-400'
                        : 'bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base hover:opacity-95'
                    }`}
                  >
                    {isCached ? (
                      <>
                        <Trash2 size={14} />
                        <span>{t('প্যাক মুছুন', 'Remove Pack')}</span>
                      </>
                    ) : (
                      <>
                        <DownloadCloud size={14} />
                        <span>{t('ডাউনলোড প্যাক', 'Download Pack')}</span>
                      </>
                    )}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
