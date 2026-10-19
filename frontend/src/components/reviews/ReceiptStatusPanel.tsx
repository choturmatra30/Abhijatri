import React, { useState } from 'react';
import { Search, Undo2 } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { getReceiptStatus, isReceiptFormat, withdrawGuestReview } from '../../api/reviews';
import type { ReceiptStatus } from '../../types';
import { formatTimestamp } from '../../utils/format';
import { describeError } from '../common/StatusViews';
import { STATUS_LABEL } from './reviewLabels';

const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const FINAL_STATES = new Set(['WITHDRAWN', 'DELETED']);

/** Receipt-scoped status check and withdrawal (API.md 5.3, 5.4). Inputs are never persisted. */
export const ReceiptStatusPanel: React.FC = () => {
  const { language, t } = useLanguage();
  const [reviewId, setReviewId] = useState('');
  const [receipt, setReceipt] = useState('');
  const [status, setStatus] = useState<ReceiptStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmWithdraw, setConfirmWithdraw] = useState(false);

  const inputClass =
    'w-full px-3.5 min-h-[44px] rounded-xl bg-surface-sage/40 dark:bg-dark-surface-2 border border-surface-muted/50 dark:border-dark-surface-2 text-sm font-mono text-on-surface dark:text-on-dark';

  const check = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setStatus(null);
    setConfirmWithdraw(false);
    if (!UUID_PATTERN.test(reviewId.trim()) || !isReceiptFormat(receipt)) {
      setError(t('রিভিউ আইডি বা রিসিপ্টের ফরম্যাট সঠিক নয়।', 'The review ID or receipt format is not valid.'));
      return;
    }
    setBusy(true);
    try {
      setStatus(await getReceiptStatus(reviewId.trim(), receipt.trim()));
    } catch (err: unknown) {
      setError(describeError(err, t));
    } finally {
      setBusy(false);
    }
  };

  const withdraw = async () => {
    if (!status) return;
    setBusy(true);
    setError(null);
    try {
      setStatus(await withdrawGuestReview(status.review_id, receipt.trim(), status.version));
      setConfirmWithdraw(false);
    } catch (err: unknown) {
      setError(describeError(err, t));
    } finally {
      setBusy(false);
    }
  };

  return (
    <section aria-labelledby="status-heading" className="tonal-card p-6 flex flex-col gap-4">
      <h2 id="status-heading" className="text-lg font-bold font-title text-on-surface dark:text-on-dark">
        {t('রিসিপ্ট দিয়ে অবস্থা দেখুন', 'Check a review with its receipt')}
      </h2>
      <form onSubmit={check} className="flex flex-col gap-3">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="status-review-id" className="text-xs font-bold text-on-surface-variant dark:text-on-dark-muted">
            {t('রিভিউ আইডি', 'Review ID')}
          </label>
          <input id="status-review-id" value={reviewId} onChange={(e) => setReviewId(e.target.value)} autoComplete="off" spellCheck={false} className={inputClass} />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="status-receipt" className="text-xs font-bold text-on-surface-variant dark:text-on-dark-muted">
            {t('রিসিপ্ট', 'Receipt')}
          </label>
          <input
            id="status-receipt"
            type="password"
            value={receipt}
            onChange={(e) => setReceipt(e.target.value)}
            autoComplete="off"
            spellCheck={false}
            placeholder="abr1_…"
            className={inputClass}
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="self-start inline-flex items-center gap-2 min-h-[44px] px-5 rounded-full bg-surface-sage dark:bg-dark-surface-2 text-forest-primary dark:text-neon-lime text-xs font-bold font-title disabled:opacity-60"
        >
          <Search size={14} aria-hidden="true" />
          {t('অবস্থা দেখুন', 'Check status')}
        </button>
      </form>

      {error && (
        <p role="alert" className="text-sm text-error-alert dark:text-red-400">
          {error}
        </p>
      )}

      {status && (
        <div role="status" className="p-4 rounded-xl bg-surface-container/60 dark:bg-dark-surface-2 flex flex-col gap-2 text-sm">
          <p className="font-bold font-title text-on-surface dark:text-on-dark">{t(...STATUS_LABEL[status.status])}</p>
          {status.published_at && (
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted">
              {t('প্রকাশ', 'Published')}: {formatTimestamp(status.published_at, language)}
            </p>
          )}
          {status.decision_reason && (
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted">
              {t('কারণ', 'Reason')}: <span className="font-en">{status.decision_reason}</span>
            </p>
          )}
          {status.appeal_deadline && (
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted">
              {t('আপিলের শেষ সময়', 'Appeal deadline')}: {formatTimestamp(status.appeal_deadline, language)}
            </p>
          )}

          {!FINAL_STATES.has(status.status) &&
            (confirmWithdraw ? (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <span className="text-xs text-on-surface dark:text-on-dark">
                  {t('প্রত্যাহার করলে রিভিউটি সঙ্গে সঙ্গে সরিয়ে নেওয়া হবে। নিশ্চিত?', 'Withdrawing removes the review immediately. Are you sure?')}
                </span>
                <button type="button" onClick={withdraw} disabled={busy} className="min-h-[44px] px-4 rounded-full bg-red-700 text-white text-xs font-bold disabled:opacity-60">
                  {t('হ্যাঁ, প্রত্যাহার করুন', 'Yes, withdraw')}
                </button>
                <button type="button" onClick={() => setConfirmWithdraw(false)} className="min-h-[44px] px-4 rounded-full border text-xs font-bold">
                  {t('বাতিল', 'Cancel')}
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={() => setConfirmWithdraw(true)}
                className="self-start inline-flex items-center gap-2 min-h-[44px] px-4 rounded-full border border-red-300 text-red-700 dark:text-red-300 dark:border-red-900 text-xs font-bold"
              >
                <Undo2 size={14} aria-hidden="true" />
                {t('রিভিউ প্রত্যাহার করুন', 'Withdraw review')}
              </button>
            ))}
        </div>
      )}
    </section>
  );
};
