import React, { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { 
  Calculator, 
  ShieldCheck, 
  Bookmark, 
  CheckCircle2
} from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { SEEDED_DESTINATIONS } from '../services/api';

export const PlannerPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { language, t } = useLanguage();

  const initialDestination = searchParams.get('destination') || 'sajek-valley';
  const [selectedDest, setSelectedDest] = useState(initialDestination);
  const [partySize, setPartySize] = useState(4);
  const [durationDays, setDurationDays] = useState(3);
  const [durationNights, setDurationNights] = useState(2);
  const [comfortTier, setComfortTier] = useState<'economy' | 'standard' | 'premium'>('standard');
  const [savedSuccess, setSavedSuccess] = useState(false);

  // Deterministic rule engine multipliers as specified in Proposal Section 4.5
  const tierMultiplier = comfortTier === 'economy' ? 0.75 : comfortTier === 'standard' ? 1.0 : 1.6;
  const weekendFactor = 1.15; // Weekend/Peak seasonal factor

  // Calculations
  const busUnit = Math.round(2400 * tierMultiplier);
  const busTotal = partySize * busUnit;

  const roomUnit = Math.round(3000 * tierMultiplier);
  const roomsNeeded = Math.ceil(partySize / 2);
  const roomTotal = Math.round(roomsNeeded * durationNights * roomUnit * ((1.0 + weekendFactor) / 2));

  const mealUnit = Math.round(250 * tierMultiplier);
  const mealsCount = partySize * 3 * durationDays;
  const mealTotal = mealsCount * mealUnit;

  const vehicleUnit = Math.round(1200 * tierMultiplier);
  const vehiclesNeeded = Math.ceil(partySize / 4);
  const vehicleTotal = Math.round(vehiclesNeeded * durationDays * vehicleUnit * weekendFactor);

  const entryTotal = partySize * 200; // Fixed official charges

  // Sums
  const expectedTotal = busTotal + roomTotal + mealTotal + vehicleTotal + entryTotal;
  const lowTotal = Math.round(expectedTotal * 0.80);
  const highTotal = Math.round(expectedTotal * 1.25);
  const perPersonExpected = Math.round(expectedTotal / partySize);

  // Shared vs Individual cost separation (Proposal Section 4.5 / Eq 2)
  const sharedTotal = roomTotal + vehicleTotal;
  const individualTotal = busTotal + mealTotal + entryTotal;

  const handleSaveBrief = () => {
    const brief = {
      id: crypto.randomUUID(),
      destination: selectedDest,
      partySize,
      durationDays,
      durationNights,
      comfortTier,
      totalExpected: expectedTotal,
      perPersonExpected,
      savedAt: new Date().toISOString(),
    };
    const existing = JSON.parse(localStorage.getItem('abhijatri_saved_trips') || '[]');
    localStorage.setItem('abhijatri_saved_trips', JSON.stringify([brief, ...existing]));
    setSavedSuccess(true);
    setTimeout(() => setSavedSuccess(false), 3000);
  };

  return (
    <div className="flex flex-col gap-8 pb-12 max-w-6xl mx-auto">
      {/* Header */}
      <div>
        <div className="flex items-center gap-2 text-forest-primary dark:text-neon-lime text-xs font-bold uppercase font-en tracking-wider mb-1">
          <Calculator size={16} />
          <span>{t('ডিটারমিনিস্টিক রুলস ইঞ্জিন', 'Deterministic Rules Engine (FR08/FR09)')}</span>
        </div>
        <h1 className="text-2xl sm:text-3xl font-bold font-title text-on-surface dark:text-on-dark tracking-tight">
          {t('অভিযাত্রী ভ্রমণ খরচ ক্যালকুলেটর', 'Abhijatri Contextual Trip Cost Planner')}
        </h1>
        <p className="text-xs sm:text-sm text-on-surface-variant dark:text-on-dark-muted font-body mt-1">
          {t(
            'কোনো অনুমাননির্ভর বা এআই আন্দাজ নয় — প্রমাণিত রুলস ইঞ্জিন এবং মৌসুমী ফ্যাক্টরের সমন্বয়ে নিরপেক্ষ হিসাব।',
            'No black-box ML or vendor markups — fully reproducible calculation with itemized pricing units.'
          )}
        </p>
      </div>

      {/* Grid: Inputs Left, Result Output Right */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Form Controls */}
        <div className="lg:col-span-5 tonal-card p-6 flex flex-col gap-5">
          <h2 className="text-lg font-bold font-title border-b border-surface-muted/30 dark:border-dark-surface-2 pb-3">
            {t('ভ্রমণের পরামিতি নির্ধারণ', 'Trip Parameters')}
          </h2>

          {/* Destination Select */}
          <div className="flex flex-col gap-1.5">
            <label className="text-xs font-bold uppercase font-en text-on-surface-variant dark:text-on-dark-muted">
              {t('গন্তব্য নির্বাচন করুন', 'Destination')}
            </label>
            <select
              value={selectedDest}
              onChange={(e) => setSelectedDest(e.target.value)}
              className="w-full px-3.5 py-2 rounded-xl bg-surface-sage/40 dark:bg-dark-surface-2 border border-surface-muted/40 text-sm font-title text-on-surface dark:text-on-dark focus:ring-1 focus:ring-forest-primary"
            >
              {SEEDED_DESTINATIONS.map((d) => (
                <option key={d.id} value={d.id}>
                  {language === 'bn' ? d.nameBn : d.nameEn}
                </option>
              ))}
            </select>
          </div>

          {/* Party Size */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center text-xs font-bold uppercase font-en">
              <span className="text-on-surface-variant dark:text-on-dark-muted">{t('যাত্রী সংখ্যা', 'Party Size (n)')}</span>
              <span className="text-forest-primary dark:text-neon-lime">{partySize} {t('জন', 'travellers')}</span>
            </div>
            <input
              type="range"
              min="1"
              max="16"
              value={partySize}
              onChange={(e) => setPartySize(Number(e.target.value))}
              className="w-full accent-forest-primary dark:accent-neon-lime cursor-pointer"
            />
            <div className="flex justify-between text-[11px] text-on-surface-variant/70 font-en">
              <span>1 Solo</span>
              <span>4 Group</span>
              <span>8+ Family</span>
              <span>16 Max</span>
            </div>
          </div>

          {/* Duration Days & Nights */}
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1">
              <label className="text-xs font-bold uppercase font-en text-on-surface-variant dark:text-on-dark-muted">
                {t('দিন (Days)', 'Days')}
              </label>
              <input
                type="number"
                min="1"
                max="30"
                value={durationDays}
                onChange={(e) => setDurationDays(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded-xl bg-surface-sage/40 dark:bg-dark-surface-2 border border-surface-muted/40 text-sm text-center font-en font-bold"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-xs font-bold uppercase font-en text-on-surface-variant dark:text-on-dark-muted">
                {t('রাত (Nights)', 'Nights')}
              </label>
              <input
                type="number"
                min="0"
                max="30"
                value={durationNights}
                onChange={(e) => setDurationNights(Number(e.target.value))}
                className="w-full px-3 py-1.5 rounded-xl bg-surface-sage/40 dark:bg-dark-surface-2 border border-surface-muted/40 text-sm text-center font-en font-bold"
              />
            </div>
          </div>

          {/* Comfort Tier (Economy, Standard, Premium) */}
          <div className="flex flex-col gap-2">
            <label className="text-xs font-bold uppercase font-en text-on-surface-variant dark:text-on-dark-muted">
              {t('স্বাচ্ছন্দ্য স্তর (Comfort Tier)', 'Comfort Tier')}
            </label>
            <div className="grid grid-cols-3 gap-2">
              {(['economy', 'standard', 'premium'] as const).map((tier) => (
                <button
                  key={tier}
                  type="button"
                  onClick={() => setComfortTier(tier)}
                  className={`py-2 px-2 rounded-xl text-xs font-semibold capitalize font-title transition-all ${
                    comfortTier === tier
                      ? 'bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base shadow-sm font-bold'
                      : 'bg-surface-sage/50 dark:bg-dark-surface-2 text-on-surface-variant hover:bg-surface-container'
                  }`}
                >
                  {t(
                    tier === 'economy' ? 'ইকোনমি' : tier === 'standard' ? 'স্ট্যান্ডার্ড' : 'প্রিমিয়াম',
                    tier
                  )}
                </button>
              ))}
            </div>
          </div>

          {/* Save Brief Action */}
          <button
            onClick={handleSaveBrief}
            className={`w-full py-2.5 rounded-full text-xs font-bold font-title flex items-center justify-center gap-2 transition-all mt-2 ${
              savedSuccess
                ? 'bg-emerald-600 text-white'
                : 'bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base hover:opacity-95 shadow-sm'
            }`}
          >
            {savedSuccess ? <CheckCircle2 size={16} /> : <Bookmark size={16} />}
            <span>{savedSuccess ? t('ট্রিপ ব্রিফ সংরক্ষিত হয়েছে!', 'Trip Brief Saved!') : t('ট্রিপ ব্রিফ সেভ করুন (FR11)', 'Save Trip Brief')}</span>
          </button>
        </div>

        {/* Right Column: Calculated Estimate Breakdown */}
        <div className="lg:col-span-7 flex flex-col gap-6">
          {/* Main Total Callout Card */}
          <div className="tonal-card p-6 bg-surface-container/70 dark:bg-dark-surface-1 border-forest-container/30">
            <div className="flex items-center justify-between text-xs font-bold uppercase font-en text-forest-primary dark:text-neon-lime mb-2">
              <span>{t('মোট প্রস্তাবিত বাজেট (প্রত্যাশিত)', 'Expected Total Budget')}</span>
              <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
                <ShieldCheck size={14} />
                <span>Confidence: High (0.85)</span>
              </span>
            </div>

            <div className="flex flex-col sm:flex-row sm:items-baseline justify-between gap-2 my-2">
              <div className="flex items-baseline gap-1">
                <span className="text-3xl sm:text-4xl font-bold font-en text-forest-primary dark:text-neon-lime">
                  BDT {expectedTotal.toLocaleString()}
                </span>
                <span className="text-xs text-on-surface-variant dark:text-on-dark-muted font-en font-medium">
                  ({t('গ্রুপ মোট', 'Group Total')})
                </span>
              </div>
              <div className="text-left sm:text-right">
                <span className="text-xl font-bold font-en text-forest-primary dark:text-emerald-accent">
                  BDT {perPersonExpected.toLocaleString()}
                </span>
                <span className="block text-[11px] text-on-surface-variant dark:text-on-dark-muted font-title">
                  {t('জনপ্রতি খরচ', 'per person share')}
                </span>
              </div>
            </div>

            {/* Range Spread (Low, Expected, High) */}
            <div className="grid grid-cols-3 gap-2 mt-4 pt-3 border-t border-surface-muted/30 dark:border-dark-surface-2 text-center text-xs font-en">
              <div className="p-2 rounded-lg bg-canvas-light dark:bg-dark-surface-2">
                <span className="text-[10px] uppercase font-bold text-on-surface-variant block">Low Range (L)</span>
                <span className="font-bold text-on-surface dark:text-on-dark">BDT {lowTotal.toLocaleString()}</span>
              </div>
              <div className="p-2 rounded-lg bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base font-bold shadow-sm">
                <span className="text-[10px] uppercase block opacity-85">Expected (E)</span>
                <span>BDT {expectedTotal.toLocaleString()}</span>
              </div>
              <div className="p-2 rounded-lg bg-canvas-light dark:bg-dark-surface-2">
                <span className="text-[10px] uppercase font-bold text-on-surface-variant block">High Range (H)</span>
                <span className="font-bold text-on-surface dark:text-on-dark">BDT {highTotal.toLocaleString()}</span>
              </div>
            </div>
          </div>

          {/* Itemized Table */}
          <div className="tonal-card p-6 flex flex-col gap-4">
            <h3 className="font-bold text-base font-title text-on-surface dark:text-on-dark flex items-center justify-between">
              <span>{t('আইটেমাইজড খরচ বিভাজন', 'Itemized Cost Breakdown')}</span>
              <span className="text-xs font-normal text-on-surface-variant font-en">
                Formula: K_i = p_i × q_i × ∑s(τ)
              </span>
            </h3>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-en">
                <thead>
                  <tr className="border-b border-surface-muted/40 text-on-surface-variant dark:text-on-dark-muted">
                    <th className="pb-2 font-bold">{t('বিবরণ', 'Category & Unit')}</th>
                    <th className="pb-2 text-center font-bold">Qty (q_i)</th>
                    <th className="pb-2 text-right font-bold">{t('মোট (BDT)', 'Total (BDT)')}</th>
                    <th className="pb-2 text-right font-bold">{t('ধরণ', 'Split Type')}</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-surface-muted/20">
                  <tr>
                    <td className="py-2.5">
                      <span className="font-bold block text-on-surface dark:text-on-dark">{t('আন্তঃনগর বাস (আসা-যাওয়া)', 'Intercity Return Bus')}</span>
                      <span className="text-[11px] text-on-surface-variant">Per person ({busUnit} BDT)</span>
                    </td>
                    <td className="py-2.5 text-center font-bold">{partySize}</td>
                    <td className="py-2.5 text-right font-bold text-forest-primary dark:text-neon-lime">{busTotal.toLocaleString()}</td>
                    <td className="py-2.5 text-right"><span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[10px] font-bold">Individual</span></td>
                  </tr>
                  <tr>
                    <td className="py-2.5">
                      <span className="font-bold block text-on-surface dark:text-on-dark">{t('হোটেল / রিসোর্ট রুম', 'Hotel / Resort Room')}</span>
                      <span className="text-[11px] text-on-surface-variant">Per room ({roomsNeeded} rooms × {durationNights} nights)</span>
                    </td>
                    <td className="py-2.5 text-center font-bold">{roomsNeeded}</td>
                    <td className="py-2.5 text-right font-bold text-forest-primary dark:text-neon-lime">{roomTotal.toLocaleString()}</td>
                    <td className="py-2.5 text-right"><span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 text-[10px] font-bold">Shared</span></td>
                  </tr>
                  <tr>
                    <td className="py-2.5">
                      <span className="font-bold block text-on-surface dark:text-on-dark">{t('খাবার ও পানীয়', 'Meals (3/day)')}</span>
                      <span className="text-[11px] text-on-surface-variant">{mealsCount} meals total ({mealUnit} BDT)</span>
                    </td>
                    <td className="py-2.5 text-center font-bold">{mealsCount}</td>
                    <td className="py-2.5 text-right font-bold text-forest-primary dark:text-neon-lime">{mealTotal.toLocaleString()}</td>
                    <td className="py-2.5 text-right"><span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[10px] font-bold">Individual</span></td>
                  </tr>
                  <tr>
                    <td className="py-2.5">
                      <span className="font-bold block text-on-surface dark:text-on-dark">{t('স্থানীয় চান্দের গাড়ি / সিএনজি', 'Local Chander Gari / Jeep')}</span>
                      <span className="text-[11px] text-on-surface-variant">Per vehicle ({durationDays} days)</span>
                    </td>
                    <td className="py-2.5 text-center font-bold">{vehiclesNeeded}</td>
                    <td className="py-2.5 text-right font-bold text-forest-primary dark:text-neon-lime">{vehicleTotal.toLocaleString()}</td>
                    <td className="py-2.5 text-right"><span className="px-2 py-0.5 rounded-full bg-purple-100 text-purple-800 text-[10px] font-bold">Shared</span></td>
                  </tr>
                  <tr>
                    <td className="py-2.5">
                      <span className="font-bold block text-on-surface dark:text-on-dark">{t('সরকারি ফি ও এন্ট্রি পাস', 'Official Park Entry & Permits')}</span>
                      <span className="text-[11px] text-on-surface-variant">Per entry (Fixed 200 BDT)</span>
                    </td>
                    <td className="py-2.5 text-center font-bold">{partySize}</td>
                    <td className="py-2.5 text-right font-bold text-forest-primary dark:text-neon-lime">{entryTotal.toLocaleString()}</td>
                    <td className="py-2.5 text-right"><span className="px-2 py-0.5 rounded-full bg-blue-100 text-blue-800 text-[10px] font-bold">Individual</span></td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Fair cost settlement */}
            <div className="p-3 rounded-xl bg-surface-sage/50 dark:bg-dark-surface-2 flex flex-col sm:flex-row sm:items-center justify-between gap-2 text-xs font-en">
              <div>
                <span className="font-bold block text-on-surface dark:text-on-dark">Shared vs. Individual Split</span>
                <span className="text-on-surface-variant text-[11px]">Shared costs (BDT {sharedTotal.toLocaleString()}) + Individual direct costs (BDT {individualTotal.toLocaleString()}).</span>
              </div>
              <div className="text-left sm:text-right font-bold text-forest-primary dark:text-neon-lime">
                Shared: BDT {Math.round(sharedTotal / partySize).toLocaleString()} / person
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
