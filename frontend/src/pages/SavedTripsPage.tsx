import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Bookmark, Calendar, Users, Trash2, ArrowRight } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { SEEDED_DESTINATIONS } from '../services/api';

interface SavedBrief {
  id: string;
  destination: string;
  partySize: number;
  durationDays: number;
  durationNights: number;
  comfortTier: string;
  totalExpected: number;
  perPersonExpected: number;
  savedAt: string;
}

export const SavedTripsPage: React.FC = () => {
  const { language, t } = useLanguage();
  const [trips, setTrips] = useState<SavedBrief[]>([]);

  useEffect(() => {
    const saved = localStorage.getItem('abhijatri_saved_trips');
    if (saved) {
      try {
        setTrips(JSON.parse(saved));
      } catch {
        setTrips([]);
      }
    }
  }, []);

  const handleDelete = (id: string) => {
    const updated = trips.filter((t) => t.id !== id);
    setTrips(updated);
    localStorage.setItem('abhijatri_saved_trips', JSON.stringify(updated));
  };

  return (
    <div className="flex flex-col gap-6 pb-12 max-w-4xl mx-auto">
      <div>
        <div className="flex items-center gap-2 text-forest-primary dark:text-neon-lime text-xs font-bold uppercase font-en tracking-wider mb-1">
          <Bookmark size={16} />
          <span>{t('স্থানীয় ট্রিপ সামারি', 'Saved Trip Briefs (FR11)')}</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold font-title text-on-surface dark:text-on-dark tracking-tight">
          {t('সংরক্ষিত ট্রিপ ব্রিফ ও বাজেট', 'Saved Trip Briefs & Estimates')}
        </h1>
        <p className="text-xs sm:text-sm text-on-surface-variant dark:text-on-dark-muted font-body mt-1">
          {t(
            'আপনার সংরক্ষিত ট্রিপের হিসাব, দিন-রাতের বিবরণ ও যোগাযোগের সংক্ষিপ্ত নোট।',
            'Compact trip summaries and cost estimates saved locally on your device.'
          )}
        </p>
      </div>

      {trips.length === 0 ? (
        <div className="tonal-card p-12 text-center flex flex-col items-center gap-4">
          <div className="w-14 h-14 rounded-full bg-surface-sage dark:bg-dark-surface-2 flex items-center justify-center text-forest-primary dark:text-neon-lime">
            <Bookmark size={28} />
          </div>
          <div>
            <h3 className="font-bold text-lg font-title text-on-surface dark:text-on-dark">
              {t('এখনো কোনো ট্রিপ ব্রিফ সংরক্ষিত নেই', 'No Saved Trip Briefs Yet')}
            </h3>
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted max-w-md mx-auto mt-1 font-body">
              {t(
                'ভ্রমণ খরচ ক্যালকুলেটর থেকে আপনার প্রত্যাশিত বাজেট হিসাব করে এক ক্লিকে এখানে সেভ করে রাখতে পারেন।',
                'Calculate a trip budget using the Cost Planner and save the brief for quick offline access.'
              )}
            </p>
          </div>
          <Link
            to="/planner"
            className="flex items-center gap-2 px-5 py-2.5 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-bold font-title shadow-sm hover:opacity-95 mt-2"
          >
            <span>{t('বাজেট ক্যালকুলেটরে যান', 'Open Cost Planner')}</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4">
          {trips.map((trip) => {
            const dest = SEEDED_DESTINATIONS.find((d) => d.id === trip.destination);
            return (
              <div
                key={trip.id}
                className="tonal-card p-5 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4"
              >
                <div className="flex flex-col gap-1.5">
                  <div className="flex items-center gap-2">
                    <h3 className="font-bold text-lg font-title text-on-surface dark:text-on-dark">
                      {dest ? (language === 'bn' ? dest.nameBn : dest.nameEn) : trip.destination}
                    </h3>
                    <span className="px-2 py-0.5 rounded-full bg-surface-container text-forest-primary text-[11px] font-bold capitalize font-en">
                      {trip.comfortTier}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-on-surface-variant font-en">
                    <span className="flex items-center gap-1">
                      <Users size={13} /> {trip.partySize} {t('জন', 'travellers')}
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar size={13} /> {trip.durationDays}D / {trip.durationNights}N
                    </span>
                    <span>
                      Saved: {new Date(trip.savedAt).toLocaleDateString()}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-4 self-end sm:self-center">
                  <div className="text-right">
                    <span className="text-lg font-bold font-en text-forest-primary dark:text-neon-lime block">
                      BDT {trip.totalExpected.toLocaleString()}
                    </span>
                    <span className="text-[11px] text-on-surface-variant font-en">
                      BDT {trip.perPersonExpected.toLocaleString()} / person
                    </span>
                  </div>
                  <button
                    onClick={() => handleDelete(trip.id)}
                    className="p-2 rounded-xl text-red-600 hover:bg-red-50 dark:hover:bg-red-950/40 transition-colors"
                    title={t('মুছে ফেলুন', 'Delete')}
                  >
                    <Trash2 size={16} />
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
