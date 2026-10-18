import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Calculator, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { SEEDED_DESTINATIONS } from '../services/api';
import { CostEstimateResult } from '../types';

type ComfortTier = 'economy' | 'standard' | 'premium';
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

export const PlannerPage: React.FC = () => {
  const [searchParams] = useSearchParams();
  const { language, t } = useLanguage();
  const [selectedDest, setSelectedDest] = useState(searchParams.get('destination') || 'sajek-valley');
  const [partySize, setPartySize] = useState(4);
  const [durationDays, setDurationDays] = useState(3);
  const [durationNights, setDurationNights] = useState(2);
  const [comfortTier, setComfortTier] = useState<ComfortTier>('standard');
  const [estimate, setEstimate] = useState<CostEstimateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [savedSuccess, setSavedSuccess] = useState(false);

  const calculateEstimate = async () => {
    setLoading(true); setError(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/estimates`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
        body: JSON.stringify({ destination_id: selectedDest, party_size: partySize, duration_days: durationDays, duration_nights: durationNights, comfort_tier: comfortTier }),
      });
      if (!response.ok) throw new Error(`Estimate request failed (${response.status})`);
      const data: unknown = await response.json();
      if (!data || typeof data !== 'object' || typeof (data as CostEstimateResult).totalExpected !== 'number' || !Array.isArray((data as CostEstimateResult).items)) throw new Error('Backend returned an invalid estimate');
      setEstimate(data as CostEstimateResult);
    } catch (err: unknown) { setEstimate(null); setError(err instanceof Error ? err.message : 'Unable to calculate estimate'); }
    finally { setLoading(false); }
  };

  useEffect(() => { void calculateEstimate(); }, [selectedDest, partySize, durationDays, durationNights, comfortTier]);

  const handleSaveBrief = () => {
    if (!estimate) return;
    const brief = { id: crypto.randomUUID(), destination: selectedDest, partySize, durationDays, durationNights, comfortTier, totalExpected: estimate.totalExpected, perPersonExpected: estimate.perPersonExpected, savedAt: new Date().toISOString() };
    let existing: unknown[] = [];
    try { existing = JSON.parse(localStorage.getItem('abhijatri_saved_trips') || '[]'); } catch { existing = []; }
    localStorage.setItem('abhijatri_saved_trips', JSON.stringify([brief, ...existing]));
    setSavedSuccess(true); setTimeout(() => setSavedSuccess(false), 3000);
  };
  const money = (value: number) => `BDT ${value.toLocaleString()}`;

  return <div className="flex flex-col gap-8 pb-12 max-w-6xl mx-auto">
    <div><div className="flex items-center gap-2 text-forest-primary dark:text-neon-lime text-xs font-bold uppercase font-en tracking-wider mb-1"><Calculator size={16} /><span>{t('ডিটারমিনিস্টিক রুলস ইঞ্জিন', 'Server-authoritative Cost Planner')}</span></div><h1 className="text-2xl sm:text-3xl font-bold font-title text-on-surface dark:text-on-dark tracking-tight">{t('অভিযাত্রী ভ্রমণ খরচ ক্যালকুলেটর', 'Abhijatri Contextual Trip Cost Planner')}</h1><p className="text-xs sm:text-sm text-on-surface-variant font-body mt-1">{t('সার্ভার যাচাইকৃত মূল্য ও নিয়মের ভিত্তিতে হিসাব।', 'All pricing, rules, and confidence values come from the backend.')}</p></div>
    <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
      <div className="lg:col-span-5 tonal-card p-6 flex flex-col gap-5"><h2 className="text-lg font-bold border-b pb-3">{t('ভ্রমণের পরামিতি নির্ধারণ', 'Trip Parameters')}</h2>
        <label className="flex flex-col gap-1.5 text-xs font-bold uppercase">{t('গন্তব্য', 'Destination')}<select value={selectedDest} onChange={e => setSelectedDest(e.target.value)} className="w-full px-3.5 py-2 rounded-xl border text-sm normal-case">{SEEDED_DESTINATIONS.map(d => <option key={d.id} value={d.id}>{language === 'bn' ? d.nameBn : d.nameEn}</option>)}</select></label>
        <div><div className="flex justify-between text-xs font-bold uppercase"><span>{t('যাত্রী সংখ্যা', 'Party Size')}</span><span>{partySize} {t('জন', 'travellers')}</span></div><input type="range" min="1" max="16" value={partySize} onChange={e => setPartySize(Number(e.target.value))} className="w-full" /></div>
        <div className="grid grid-cols-2 gap-3"><label className="flex flex-col gap-1 text-xs font-bold uppercase">{t('দিন', 'Days')}<input type="number" min="1" max="30" value={durationDays} onChange={e => setDurationDays(Number(e.target.value))} className="px-3 py-1.5 rounded-xl border text-center" /></label><label className="flex flex-col gap-1 text-xs font-bold uppercase">{t('রাত', 'Nights')}<input type="number" min="0" max="30" value={durationNights} onChange={e => setDurationNights(Number(e.target.value))} className="px-3 py-1.5 rounded-xl border text-center" /></label></div>
        <div><label className="text-xs font-bold uppercase">{t('স্বাচ্ছন্দ্য স্তর', 'Comfort Tier')}</label><div className="grid grid-cols-3 gap-2 mt-2">{(['economy', 'standard', 'premium'] as ComfortTier[]).map(tier => <button key={tier} type="button" onClick={() => setComfortTier(tier)} className={`py-2 px-2 rounded-xl text-xs font-semibold capitalize ${comfortTier === tier ? 'bg-forest-primary text-white' : 'bg-surface-sage/50'}`}>{t(tier === 'economy' ? 'ইকোনমি' : tier === 'standard' ? 'স্ট্যান্ডার্ড' : 'প্রিমিয়াম', tier)}</button>)}</div></div>
        <button onClick={() => void calculateEstimate()} disabled={loading} className="w-full py-2.5 rounded-full bg-forest-primary text-white text-xs font-bold disabled:opacity-50">{loading ? t('হিসাব হচ্ছে...', 'Calculating...') : t('হিসাব আপডেট করুন', 'Refresh Estimate')}</button>
        <button onClick={handleSaveBrief} disabled={!estimate || loading} className={`w-full py-2.5 rounded-full text-xs font-bold flex items-center justify-center gap-2 ${savedSuccess ? 'bg-emerald-600 text-white' : 'bg-surface-container'}`}><CheckCircle2 size={16} />{savedSuccess ? t('সংরক্ষিত হয়েছে!', 'Saved!') : t('ট্রিপ ব্রিফ সেভ করুন', 'Save Trip Brief')}</button>
      </div>
      <div className="lg:col-span-7 flex flex-col gap-6">{error && <div role="alert" className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">{error}</div>}{estimate && <><div className="tonal-card p-6"><div className="flex justify-between text-xs font-bold uppercase text-forest-primary mb-2"><span>{t('মোট বাজেট', 'Expected Total Budget')}</span><span className="flex gap-1"><ShieldCheck size={14} />{estimate.overallConfidence} confidence</span></div><div className="flex justify-between items-baseline"><span className="text-3xl font-bold">{money(estimate.totalExpected)}</span><span className="text-xl font-bold">{money(estimate.perPersonExpected)} <small className="text-xs font-normal">/ person</small></span></div><div className="grid grid-cols-3 gap-2 mt-4 text-center text-xs"><div className="p-2 bg-surface-container">Low<br /><b>{money(estimate.items.reduce((s, i) => s + i.low, 0))}</b></div><div className="p-2 bg-forest-primary text-white">Expected<br /><b>{money(estimate.totalExpected)}</b></div><div className="p-2 bg-surface-container">High<br /><b>{money(estimate.items.reduce((s, i) => s + i.high, 0))}</b></div></div></div><div className="tonal-card p-6 overflow-x-auto"><h3 className="font-bold mb-4">{t('আইটেমাইজড খরচ বিভাজন', 'Itemized Cost Breakdown')}</h3><table className="w-full text-left text-xs"><thead><tr className="border-b"><th className="pb-2">{t('বিবরণ', 'Category')}</th><th className="pb-2">{t('পরিমাণ', 'Qty')}</th><th className="pb-2 text-right">BDT</th></tr></thead><tbody>{estimate.items.map((item, index) => <tr key={`${item.category}-${index}`} className="border-b"><td className="py-2.5"><b>{item.category}</b><span className="block text-[11px]">{item.unit}</span></td><td className="py-2.5">{item.quantity}</td><td className="py-2.5 text-right font-bold">{money(item.expected)}</td></tr>)}</tbody></table><div className="mt-4 flex justify-between text-xs font-bold"><span>Shared: {money(estimate.sharedTotal)}</span><span>Individual: {money(estimate.individualTotal)}</span></div></div></>}</div>
    </div>
  </div>;
};
