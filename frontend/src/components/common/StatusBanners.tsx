import React, { useEffect, useRef, useState } from 'react';
import { CheckCircle2, LogIn, WifiOff, X } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { useSession } from '../../context/SessionContext';
import { useOnlineStatus } from '../../hooks/useNetworkState';
import { SignInLink } from './SignInLink';

/**
 * App-wide connection notice. While offline it stays visible and says what still works; when the
 * connection returns it confirms for a few seconds. Pages keep their own retry buttons.
 */
export const NetworkBanner: React.FC = () => {
  const { t } = useLanguage();
  const online = useOnlineStatus();
  const [backOnline, setBackOnline] = useState(false);
  const wasOffline = useRef(!online);

  useEffect(() => {
    if (!online) {
      wasOffline.current = true;
      setBackOnline(false);
      return undefined;
    }
    if (!wasOffline.current) return undefined;
    wasOffline.current = false;
    setBackOnline(true);
    const timer = window.setTimeout(() => setBackOnline(false), 4000);
    return () => window.clearTimeout(timer);
  }, [online]);

  if (!online) {
    return (
      <div role="status" aria-live="polite" className="w-full bg-amber-100 dark:bg-amber-950/60 text-amber-900 dark:text-amber-100 border-b border-amber-300 dark:border-amber-900">
        <p className="max-w-7xl mx-auto px-4 py-2.5 flex items-start gap-2 text-sm">
          <WifiOff size={16} className="shrink-0 mt-0.5" aria-hidden="true" />
          <span>
            <strong>{t('আপনি অফলাইনে আছেন।', 'You are offline.')}</strong>{' '}
            {t(
              'আগে খোলা পাতা দেখা যেতে পারে, কিন্তু নতুন তথ্য আসবে না এবং কিছু জমা দেওয়া যাবে না। সংযোগ ফিরলে আবার চেষ্টা করুন।',
              'Pages already open may still show, but nothing new can load or be sent. Try again when the connection is back.',
            )}
          </span>
        </p>
      </div>
    );
  }
  if (backOnline) {
    return (
      <div role="status" aria-live="polite" className="w-full bg-emerald-50 dark:bg-emerald-950/50 text-emerald-900 dark:text-emerald-100 border-b border-emerald-200 dark:border-emerald-900">
        <p className="max-w-7xl mx-auto px-4 py-2 flex items-center gap-2 text-sm">
          <CheckCircle2 size={16} aria-hidden="true" />
          {t('আবার অনলাইনে। প্রয়োজনে পাতাটি আবার লোড করুন।', 'Back online. Reload the page if something is missing.')}
        </p>
      </div>
    );
  }
  return null;
};

/** Shown once after the server ends a member's session; the app has already switched to the guest view. */
export const SessionExpiredBanner: React.FC = () => {
  const { t } = useLanguage();
  const { sessionExpired, dismissSessionExpired } = useSession();
  if (!sessionExpired) return null;
  return (
    <div role="alert" className="w-full bg-sky-50 dark:bg-sky-950/50 text-sky-900 dark:text-sky-100 border-b border-sky-200 dark:border-sky-900">
      <div className="max-w-7xl mx-auto px-4 py-2.5 flex flex-wrap items-center gap-x-3 gap-y-2 text-sm">
        <LogIn size={16} className="shrink-0" aria-hidden="true" />
        <span className="flex-1 min-w-[12rem]">
          <strong>{t('আপনার সেশনের মেয়াদ শেষ হয়েছে।', 'Your session has expired.')}</strong>{' '}
          {t('নিরাপত্তার জন্য আপনাকে সাইন আউট করা হয়েছে। চালিয়ে যেতে আবার সাইন ইন করুন।', 'You were signed out for security. Sign in again to continue.')}
        </span>
        <SignInLink className="inline-flex items-center min-h-[40px] px-4 rounded-full bg-sky-800 text-white dark:bg-sky-300 dark:text-sky-950 text-xs font-bold">
          {t('আবার সাইন ইন', 'Sign in again')}
        </SignInLink>
        <button
          type="button"
          onClick={dismissSessionExpired}
          aria-label={t('বার্তাটি বন্ধ করুন', 'Dismiss')}
          className="min-w-[40px] min-h-[40px] flex items-center justify-center rounded-full hover:bg-sky-100 dark:hover:bg-sky-900"
        >
          <X size={16} aria-hidden="true" />
        </button>
      </div>
    </div>
  );
};
