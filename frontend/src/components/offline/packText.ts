import type { Language } from '../../types';
import type { DownloadFailure } from '../../offline/packs';
import { formatNumber } from '../../utils/format';

type Pair = [bn: string, en: string];

/** Why a download failed, in words the traveller can act on (Offline-Frontend-Guideline 5.7). */
export const FAILURE_TEXT: Record<DownloadFailure, Pair> = {
  network: ['সংযোগ নেই। সংযোগ ফিরলে আবার চেষ্টা করুন।', 'No connection. Try again when you are back online.'],
  timeout: ['সার্ভার সময়মতো উত্তর দেয়নি। একটু পরে আবার চেষ্টা করুন।', 'The server did not answer in time. Try again in a moment.'],
  integrity: ['ডাউনলোড করা ফাইল যাচাইয়ে মেলেনি, তাই সংরক্ষণ করা হয়নি।', 'The downloaded file failed its check, so it was not saved.'],
  format: ['প্যাকটি এই অ্যাপের সংস্করণে খোলা যায় না। অ্যাপ হালনাগাদ করুন।', 'This pack cannot be opened by this version of the app. Update the app.'],
  superseded: ['এইমাত্র নতুন সংস্করণ তৈরি হচ্ছে। এক মিনিট পরে আবার চেষ্টা করুন।', 'A new version is being prepared. Try again in a minute.'],
  not_found: ['গন্তব্যটি আর প্রকাশিত নেই।', 'This destination is no longer published.'],
  withdrawn: ['গন্তব্যটি প্রত্যাহার করা হয়েছে।', 'This destination has been withdrawn.'],
  rate_limited: ['অনেকবার চেষ্টা হয়েছে। একটু পরে আবার চেষ্টা করুন।', 'Too many attempts. Try again a little later.'],
  server: ['সার্ভারে সমস্যা হয়েছে। পরে আবার চেষ্টা করুন।', 'The server had a problem. Try again later.'],
  quota: ['ডিভাইসের জায়গা পূর্ণ। কিছু জায়গা খালি করে আবার চেষ্টা করুন।', 'Storage is full. Free some space and try again.'],
  unavailable: ['এই ব্রাউজারে সংরক্ষণ করা যাচ্ছে না (যেমন প্রাইভেট উইন্ডো)।', 'Saving is not available in this browser (for example a private window).'],
  cancelled: ['বাতিল করা হয়েছে।', 'Cancelled.'],
};

/** "12 KB" / "১২ কেবি"; never below 1. */
export function formatSize(bytes: number, language: Language): string {
  const kb = Math.max(1, Math.round(bytes / 1024));
  if (kb >= 1024) return language === 'bn' ? `${formatNumber(kb / 1024, 'bn', 1)} এমবি` : `${formatNumber(kb / 1024, 'en', 1)} MB`;
  return language === 'bn' ? `${formatNumber(kb, 'bn')} কেবি` : `${kb} KB`;
}
