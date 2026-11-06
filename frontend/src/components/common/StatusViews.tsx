import React from 'react';
import { AlertCircle, Clock, CloudOff, Inbox, Loader2, LogIn, RefreshCw, SearchX, ShieldX, WifiOff, type LucideIcon } from 'lucide-react';
import { ApiError, NETWORK_ERROR, TIMEOUT_ERROR } from '../../api/client';
import { useLanguage } from '../../context/LanguageContext';
import { useSlowFlag } from '../../hooks/useNetworkState';
import { SignInLink } from './SignInLink';
import { Button, buttonVariants } from '@/components/ui/button';

type Translate = (bn: string, en: string) => string;

/** The kind of failure, so each one gets its own look, wording and next step. */
export type FailureKind = 'offline' | 'timeout' | 'signin' | 'forbidden' | 'other';

const FORBIDDEN_CODES = new Set(['FORBIDDEN', 'ACCOUNT_RESTRICTED', 'ACCOUNT_DISABLED', 'EMAIL_NOT_VERIFIED']);

export function failureKind(error: unknown): FailureKind {
  // With no connection every failure is "offline", whatever the error says (a dev proxy, for one,
  // answers 502 instead of failing). 502/503/504 mean the server could not be reached.
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return 'offline';
  if (!(error instanceof ApiError)) return 'other';
  if (error.status === 502 || error.status === 503 || error.status === 504) return 'offline';
  if (error.code === NETWORK_ERROR) return 'offline';
  if (error.code === TIMEOUT_ERROR) return 'timeout';
  if (error.code === 'AUTH_REQUIRED') return 'signin';
  if (FORBIDDEN_CODES.has(error.code) || error.status === 403) return 'forbidden';
  return 'other';
}

/**
 * A user-facing message for any failure. Server messages already follow Accept-Language;
 * network failures and unknown errors get a local bilingual message. Never shows stack traces.
 */
export function describeError(error: unknown, t: Translate): string {
  if (error instanceof ApiError) {
    if (error.code === NETWORK_ERROR) {
      return navigator.onLine === false
        ? t('আপনি অফলাইনে আছেন। ইন্টারনেট সংযোগ ফিরলে আবার চেষ্টা করুন।', 'You are offline. Try again when your connection is back.')
        : t(
            'সার্ভারের সাথে সংযোগ করা যায়নি। ইন্টারনেট সংযোগ দেখে আবার চেষ্টা করুন।',
            'Could not reach the server. Check your connection and try again.',
          );
    }
    if (error.code === TIMEOUT_ERROR) {
      return t(
        'সার্ভার সময়মতো উত্তর দেয়নি। সংযোগ ধীর হতে পারে; একটু পরে আবার চেষ্টা করুন।',
        'The server did not answer in time. Your connection may be slow; try again in a moment.',
      );
    }
    if (error.code.startsWith('HTTP_')) {
      return t('সার্ভার একটি অপ্রত্যাশিত উত্তর দিয়েছে।', 'The server sent an unexpected response.');
    }
    return error.message;
  }
  return t('একটি অপ্রত্যাশিত ত্রুটি ঘটেছে।', 'An unexpected error occurred.');
}

/** Shown under a spinner or a busy button once an operation has run for 8 s. */
export const SlowNetworkHint: React.FC<{ active: boolean; className?: string }> = ({ active, className = '' }) => {
  const { t } = useLanguage();
  const slow = useSlowFlag(active);
  if (!slow) return null;
  return (
    <p role="status" className={`inline-flex items-center gap-1.5 text-xs text-amber-800 dark:text-amber-300 ${className}`}>
      <Clock size={13} aria-hidden="true" />
      {t('স্বাভাবিকের চেয়ে বেশি সময় লাগছে। সংযোগ ধীর হতে পারে, অপেক্ষা করুন।', 'This is taking longer than usual. Your connection may be slow; please wait.')}
    </p>
  );
};

export const LoadingState: React.FC<{ label?: string }> = ({ label }) => {
  const { t } = useLanguage();
  return (
    <div role="status" aria-live="polite" aria-busy="true" className="tonal-card p-10 flex flex-col items-center gap-3 text-on-surface-variant dark:text-on-dark-muted">
      <Loader2 size={28} className="motion-safe:animate-spin text-forest-primary dark:text-neon-lime" aria-hidden="true" />
      <span className="text-sm font-title">{label ?? t('লোড হচ্ছে…', 'Loading…')}</span>
      <SlowNetworkHint active />
    </div>
  );
};

const KIND_LOOK: Record<FailureKind, { icon: LucideIcon; title: [string, string] }> = {
  offline: { icon: WifiOff, title: ['ইন্টারনেট সংযোগ নেই', 'No connection'] },
  timeout: { icon: Clock, title: ['সংযোগ খুব ধীর', 'The connection is too slow'] },
  signin: { icon: LogIn, title: ['সাইন ইন প্রয়োজন', 'Sign in required'] },
  forbidden: { icon: ShieldX, title: ['অনুমতি নেই', 'No permission'] },
  other: { icon: AlertCircle, title: ['কিছু একটা ভুল হয়েছে', 'Something went wrong'] },
};

export const ErrorState: React.FC<{
  error: unknown;
  onRetry?: () => void;
  /** Replaces the message when the failure is a lost connection, e.g. "this page is not saved". */
  offlineHint?: string;
  offlineAction?: React.ReactNode;
}> = ({ error, onRetry, offlineHint, offlineAction }) => {
  const { t } = useLanguage();
  const kind = failureKind(error);
  const { icon: Icon, title } = KIND_LOOK[kind];
  // Retrying cannot fix a missing sign-in or a permission; offer the step that can.
  const canRetry = onRetry && kind !== 'signin' && kind !== 'forbidden';
  return (
    <div role="alert" className="tonal-card p-8 flex flex-col items-center gap-3 text-center">
      <Icon
        size={28}
        className={kind === 'signin' || kind === 'forbidden' ? 'text-amber-700 dark:text-amber-300' : 'text-error-alert dark:text-red-400'}
        aria-hidden="true"
      />
      <p className="text-base font-bold font-title text-on-surface dark:text-on-dark">{t(...title)}</p>
      <p className="text-sm font-body text-on-surface dark:text-on-dark max-w-md">
        {kind === 'offline' && offlineHint ? offlineHint : describeError(error, t)}
      </p>
      {kind === 'offline' && offlineAction}
      {error instanceof ApiError && error.requestId && (
        <p className="text-[11px] font-en text-on-surface-variant dark:text-on-dark-muted">
          {t('রেফারেন্স', 'Reference')}: {error.requestId}
        </p>
      )}
      {kind === 'signin' && (
        <SignInLink className={buttonVariants({ className: 'mt-1' })}>
          <LogIn size={14} aria-hidden="true" />
          {t('সাইন ইন', 'Sign in')}
        </SignInLink>
      )}
      {canRetry && (
        <Button type="button" onClick={onRetry} className="mt-1">
          <RefreshCw aria-hidden="true" />
          {t('আবার চেষ্টা করুন', 'Try again')}
        </Button>
      )}
    </div>
  );
};

export const EmptyState: React.FC<{ title: string; hint?: string; action?: React.ReactNode; variant?: 'empty' | 'no-results' }> = ({
  title,
  hint,
  action,
  variant = 'empty',
}) => {
  const Icon = variant === 'no-results' ? SearchX : Inbox;
  return (
    <div role="status" className="tonal-card p-10 flex flex-col items-center gap-3 text-center">
      <Icon size={28} className="text-forest-primary dark:text-neon-lime" aria-hidden="true" />
      <p className="text-base font-bold font-title text-on-surface dark:text-on-dark">{title}</p>
      {hint && <p className="text-xs font-body text-on-surface-variant dark:text-on-dark-muted max-w-md">{hint}</p>}
      {action}
    </div>
  );
};

/** Shown above lists that, offline, contain only what this device has saved (Frontend-Implemented 5i). */
export const OfflineSavedNotice: React.FC<{ count: number }> = ({ count }) => {
  const { t } = useLanguage();
  return (
    <p
      role="status"
      className="flex items-start gap-2 rounded-xl border border-amber-300 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 px-4 py-3 text-sm text-amber-900 dark:text-amber-100"
    >
      <CloudOff size={16} className="shrink-0 mt-0.5" aria-hidden="true" />
      <span>
        {t(
          `আপনি অফলাইনে আছেন। এই ডিভাইসে সংরক্ষিত ${count}টি গন্তব্য দেখানো হচ্ছে; সংযোগ ফিরলে সব দেখা যাবে।`,
          `You are offline. Showing the ${count} destination(s) saved on this device; the full list returns when you are back online.`,
        )}
      </span>
    </p>
  );
};

/** Offline with nothing saved yet: says how saving works instead of a generic error. */
export const OfflineEmptyState: React.FC = () => {
  const { t } = useLanguage();
  return (
    <div role="status" className="tonal-card p-10 flex flex-col items-center gap-3 text-center">
      <CloudOff size={28} className="text-amber-700 dark:text-amber-300" aria-hidden="true" />
      <p className="text-base font-bold font-title text-on-surface dark:text-on-dark">
        {t('এই ডিভাইসে কোনো গন্তব্য সংরক্ষিত নেই', 'No destinations saved on this device')}
      </p>
      <p className="text-xs font-body text-on-surface-variant dark:text-on-dark-muted max-w-md">
        {t(
          'অনলাইনে থাকার সময় যে গন্তব্য খুলবেন, তা ৭ দিন পর্যন্ত অফলাইনে দেখা যাবে।',
          'Destinations you open while online stay readable offline for up to 7 days.',
        )}
      </p>
    </div>
  );
};
