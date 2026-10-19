import React from 'react';
import { AlertCircle, Inbox, Loader2, RefreshCw, WifiOff } from 'lucide-react';
import { ApiError, NETWORK_ERROR } from '../../api/client';
import { useLanguage } from '../../context/LanguageContext';

type Translate = (bn: string, en: string) => string;

/**
 * A user-facing message for any failure. Server messages already follow Accept-Language;
 * network failures and unknown errors get a local bilingual message. Never shows stack traces.
 */
export function describeError(error: unknown, t: Translate): string {
  if (error instanceof ApiError) {
    if (error.code === NETWORK_ERROR) {
      return t(
        'সার্ভারের সাথে সংযোগ করা যায়নি। ইন্টারনেট সংযোগ দেখে আবার চেষ্টা করুন।',
        'Could not reach the server. Check your connection and try again.',
      );
    }
    if (error.code.startsWith('HTTP_')) {
      return t('সার্ভার একটি অপ্রত্যাশিত উত্তর দিয়েছে।', 'The server sent an unexpected response.');
    }
    return error.message;
  }
  return t('একটি অপ্রত্যাশিত ত্রুটি ঘটেছে।', 'An unexpected error occurred.');
}

export const LoadingState: React.FC<{ label?: string }> = ({ label }) => {
  const { t } = useLanguage();
  return (
    <div role="status" aria-live="polite" className="tonal-card p-10 flex flex-col items-center gap-3 text-on-surface-variant dark:text-on-dark-muted">
      <Loader2 size={28} className="animate-spin text-forest-primary dark:text-neon-lime" aria-hidden="true" />
      <span className="text-sm font-title">{label ?? t('লোড হচ্ছে…', 'Loading…')}</span>
    </div>
  );
};

export const ErrorState: React.FC<{ error: unknown; onRetry?: () => void }> = ({ error, onRetry }) => {
  const { t } = useLanguage();
  const offline = error instanceof ApiError && error.code === NETWORK_ERROR;
  const Icon = offline ? WifiOff : AlertCircle;
  return (
    <div role="alert" className="tonal-card p-8 flex flex-col items-center gap-3 text-center">
      <Icon size={28} className="text-error-alert dark:text-red-400" aria-hidden="true" />
      <p className="text-sm font-body text-on-surface dark:text-on-dark max-w-md">{describeError(error, t)}</p>
      {error instanceof ApiError && error.requestId && (
        <p className="text-[11px] font-en text-on-surface-variant dark:text-on-dark-muted">
          {t('রেফারেন্স', 'Reference')}: {error.requestId}
        </p>
      )}
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 inline-flex items-center gap-2 px-5 min-h-[44px] rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-xs font-bold font-title"
        >
          <RefreshCw size={14} aria-hidden="true" />
          {t('আবার চেষ্টা করুন', 'Try again')}
        </button>
      )}
    </div>
  );
};

export const EmptyState: React.FC<{ title: string; hint?: string; action?: React.ReactNode }> = ({
  title,
  hint,
  action,
}) => (
  <div className="tonal-card p-10 flex flex-col items-center gap-3 text-center">
    <Inbox size={28} className="text-forest-primary dark:text-neon-lime" aria-hidden="true" />
    <p className="text-base font-bold font-title text-on-surface dark:text-on-dark">{title}</p>
    {hint && <p className="text-xs font-body text-on-surface-variant dark:text-on-dark-muted max-w-md">{hint}</p>}
    {action}
  </div>
);
