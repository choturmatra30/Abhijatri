import { NETWORK_ERROR, TIMEOUT_ERROR } from '../../api/client';
import type { DraftError } from '../../offline/draftStore';
import { formatDateTime } from '../../utils/format';

type Translate = (bn: string, en: string) => string;

/**
 * What the reviewer reads after a send attempt that was not accepted (Offline-Frontend-Guideline 6.4).
 * Branches on `code` only; the server's own message (already in the interface language) is added
 * where it says what to change. Every text says what happens to the draft.
 */
export function sendFailureText(error: DraftError, t: Translate, language: 'bn' | 'en', retryAfter: string | null): string {
  const when = retryAfter ? formatDateTime(retryAfter, language) : null;
  switch (error.code) {
    case NETWORK_ERROR:
    case TIMEOUT_ERROR:
    case 'UNKNOWN':
      return t('পাঠানো যায়নি। আপনার খসড়া এই ডিভাইসে নিরাপদ আছে; সংযোগ দেখে আবার পাঠান।', 'Could not send. Your draft is safe on this device; check the connection and send again.');
    case 'RATE_LIMITED':
      return when
        ? t(`আজকের নতুন অতিথি রিভিউয়ের সীমা পূর্ণ। খসড়াটি রাখা আছে; ${when}-এর পরে পাঠানো যাবে।`, `Today's limit for new guest reviews is reached. The draft is kept; it can be sent after ${when}.`)
        : t('অনেকবার চেষ্টা হয়েছে। খসড়াটি রাখা আছে; একটু পরে আবার পাঠান।', 'Too many attempts. The draft is kept; send it again a little later.');
    case 'IDEMPOTENCY_REQUEST_IN_PROGRESS':
      return t('আগের চেষ্টাটি এখনও সার্ভারে চলছে। কয়েক সেকেন্ড পরে আবার পাঠান।', 'The previous attempt is still being handled. Send again in a few seconds.');
    case 'CHALLENGE_FAILED':
      return t('নিরাপত্তা যাচাই সফল হয়নি। যাচাইটি আবার করে পাঠান; খসড়াটি রাখা আছে।', 'The security check did not pass. Do the check again and send; the draft is kept.');
    case 'AUTH_REQUIRED':
      return t('আপনার সাইন-ইন শেষ হয়েছে। খসড়াটি রাখা আছে; আবার সাইন ইন করে পাঠান।', 'Your sign-in has ended. The draft is kept; sign in again and send it.');
    case 'GUEST_WRITES_PAUSED':
    case 'SERVICE_UNAVAILABLE':
      return `${error.message} ${t('খসড়াটি রাখা আছে; পরে আবার পাঠান।', 'The draft is kept; send it again later.')}`;
    case 'IDEMPOTENCY_KEY_REUSED':
      return t('একটি প্রযুক্তিগত সমস্যা হয়েছে। আবার পাঠান চাপুন।', 'A technical problem occurred. Press Submit again.');
    case 'DRAFT_ALREADY_SUBMITTED':
      return `${error.message} ${t('আপনার লেখা একটি নতুন খসড়া হিসেবে রাখা হয়েছে।', 'Your text is kept as a new draft.')}`;
    case 'NOT_FOUND':
      return t('এই গন্তব্যটি আর পাওয়া যাচ্ছে না। খসড়াটি আপনি না মোছা পর্যন্ত রাখা থাকবে।', 'This destination is no longer available. The draft is kept until you delete it.');
    case 'MEMBER_REVIEW_EXISTS':
      return `${error.message} ${t('ভ্রমণের মাস বদলে আবার পাঠান; খসড়াটি রাখা আছে।', 'Change the month of visit and send again; the draft is kept.')}`;
    default:
      return `${error.message} ${t('খসড়াটি রাখা আছে।', 'The draft is kept.')}`;
  }
}

/** True while the server's `Retry-After` has not passed yet. */
export const mustWait = (retryAfter: string | null, now: number = Date.now()): boolean =>
  retryAfter !== null && Date.parse(retryAfter) > now;
