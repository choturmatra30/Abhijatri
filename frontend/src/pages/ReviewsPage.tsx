import React, { useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ArrowRight, CloudOff, MessageSquareText, ReceiptText } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { useDestinationCatalog } from '../hooks/useDestinationCatalog';
import { useDrafts } from '../hooks/useDrafts';
import { EmptyState, ErrorState, LoadingState } from '../components/common/StatusViews';
import { GuestReviewForm, type OpenDraftRequest, type SubmittedReview } from '../components/reviews/GuestReviewForm';
import { SavedDrafts } from '../components/reviews/SavedDrafts';
import type { StoredDraft } from '../offline/draftStore';
import { ReceiptPanel } from '../components/reviews/ReceiptPanel';
import { ReceiptStatusPanel } from '../components/reviews/ReceiptStatusPanel';
import { RemovalRequestForm } from '../components/reviews/RemovalRequestForm';

/** The review section has two pages; the sidebar shows them under "Reviews" (Frontend-Implemented 5h). */
export const REVIEW_WRITE_PATH = '/reviews/write';
export const REVIEW_RECEIPT_PATH = '/reviews/receipt';

const PageHeader: React.FC<{ icon: typeof MessageSquareText; eyebrow: [string, string]; title: [string, string]; summary: [string, string] }> = ({
  icon: Icon,
  eyebrow,
  title,
  summary,
}) => {
  const { t } = useLanguage();
  return (
    <div>
      <div className="flex items-center gap-2 text-forest-primary dark:text-neon-lime text-xs font-bold uppercase tracking-wider mb-1">
        <Icon size={16} aria-hidden="true" />
        <span>{t(...eyebrow)}</span>
      </div>
      <h1 className="text-2xl sm:text-3xl font-bold font-title text-on-surface dark:text-on-dark tracking-tight">{t(...title)}</h1>
      <p className="text-sm text-on-surface-variant dark:text-on-dark-muted font-body mt-1">{t(...summary)}</p>
    </div>
  );
};

/** A quiet link to the other review page. */
const SwitchLink: React.FC<{ to: string; text: [string, string] }> = ({ to, text }) => {
  const { t } = useLanguage();
  return (
    <Link to={to} className="self-start inline-flex items-center gap-1.5 min-h-11 text-sm font-semibold text-primary underline-offset-4 hover:underline">
      {t(...text)}
      <ArrowRight size={14} aria-hidden="true" />
    </Link>
  );
};

/** An acknowledged draft whose receipt was not confirmed yet, as the receipt panel shows it. */
const asSubmitted = (d: StoredDraft): SubmittedReview => ({
  review_id: d.review!.review_id,
  status: d.review!.status,
  version: d.review!.version,
  duplicate_recovered: d.review!.duplicate_recovered,
  receipt: d.receipt,
  destinationId: d.destination_id,
  clientDraftId: d.client_draft_id,
  member: d.author.kind === 'member',
});

/** Writing a guest review. `?destination=<id>` preselects the destination. */
export const WriteReviewPage: React.FC = () => {
  const { t } = useLanguage();
  const { session } = useSession();
  const [searchParams] = useSearchParams();
  const [submitted, setSubmitted] = useState<SubmittedReview | null>(null);
  // Offline the choice is the destinations saved on this device (packs and opened pages), so a draft
  // can be written without a connection (Offline-Frontend-Guideline 6.3).
  const { data: catalog, error, loading, reload } = useDestinationCatalog();
  const destinations = catalog?.items ?? null;
  const savedOnly = catalog?.saved ?? false;
  // Drafts and kept receipts on this device (R15): the list above the form, and any receipt whose
  // saving was not confirmed (closed before "Done"), shown again until confirmed or 7 days.
  const drafts = useDrafts();
  const [openRequest, setOpenRequest] = useState<OpenDraftRequest | null>(null);
  const unconfirmed = submitted ? null : (drafts.unconfirmed[0] ?? null);

  return (
    <div className="flex flex-col gap-6 pb-12 max-w-3xl mx-auto">
      <PageHeader
        icon={MessageSquareText}
        eyebrow={['রিভিউ লিখুন', 'Write a review']}
        title={['আপনার ভ্রমণ অভিজ্ঞতা লিখুন', 'Share your travel experience']}
        summary={[
          'অ্যাকাউন্ট ছাড়াই রিভিউ দিন। মডারেশনের পর প্রকাশিত হবে; জমা দেওয়ার পর একটি রিসিপ্ট পাবেন।',
          'No account needed. Reviews are published after moderation; you get a receipt when you submit.',
        ]}
      />

      {unconfirmed && (
        <ReceiptPanel key={unconfirmed.client_draft_id} review={asSubmitted(unconfirmed)} acknowledgedAt={unconfirmed.acknowledged_at} onDone={() => undefined} />
      )}

      {!submitted && destinations && (
        <SavedDrafts
          drafts={drafts.unsent}
          destinations={destinations}
          savedOnly={savedOnly}
          onOpen={(destinationId) => setOpenRequest((r) => ({ destinationId, nonce: (r?.nonce ?? 0) + 1 }))}
        />
      )}

      {submitted ? (
        <ReceiptPanel review={submitted} onDone={() => setSubmitted(null)} />
      ) : loading ? (
        <LoadingState />
      ) : error !== null ? (
        <ErrorState
          error={error}
          onRetry={reload}
          offlineHint={t(
            'রিভিউ পাঠাতে ইন্টারনেট সংযোগ লাগে। সংযোগ ফিরলে এখানে আবার আসুন।',
            'Sending a review needs a connection. Come back here when you are online.',
          )}
        />
      ) : savedOnly && destinations && destinations.length === 0 ? (
        <div role="status" className="tonal-card p-10 flex flex-col items-center gap-3 text-center">
          <CloudOff size={28} className="text-amber-700 dark:text-amber-300" aria-hidden="true" />
          <p className="text-base font-bold font-title text-foreground">
            {t('অফলাইনে রিভিউ লিখতে আগে একটি গন্তব্য সংরক্ষণ করুন', 'To write a review offline, save a destination first')}
          </p>
          <p className="text-xs text-muted-foreground max-w-md">
            {t(
              'অনলাইনে থাকার সময় গন্তব্য খুলুন বা "অফলাইনের জন্য সংরক্ষণ করুন" চাপুন; তারপর ইন্টারনেট ছাড়াই খসড়া লেখা যাবে।',
              'Open a destination or press "Save for offline use" while online; then you can write a draft without internet.',
            )}
          </p>
        </div>
      ) : destinations && destinations.length > 0 ? (
        <GuestReviewForm
          destinations={destinations}
          initialDestinationId={searchParams.get('destination')}
          onSubmitted={setSubmitted}
          openRequest={openRequest}
        />
      ) : (
        <EmptyState title={t('রিভিউ দেওয়ার মতো কোনো প্রকাশিত গন্তব্য নেই', 'No published destinations to review yet')} />
      )}

      {session.kind === 'member' ? (
        <SwitchLink to="/account/reviews" text={['আগে রিভিউ দিয়েছেন? আমার রিভিউ-তে দেখুন', 'Already reviewed? Find it in My reviews']} />
      ) : (
        <SwitchLink to={REVIEW_RECEIPT_PATH} text={['আগে রিভিউ দিয়েছেন? রিসিপ্ট দিয়ে অবস্থা দেখুন', 'Already reviewed? Check it with your receipt']} />
      )}
    </div>
  );
};

/** Checking, withdrawing or asking to remove an existing guest review with its receipt. */
export const ReviewReceiptPage: React.FC = () => (
  <div className="flex flex-col gap-6 pb-12 max-w-3xl mx-auto">
    <PageHeader
      icon={ReceiptText}
      eyebrow={['রিসিপ্ট দিয়ে দেখুন', 'Check with receipt']}
      title={['আপনার রিভিউয়ের অবস্থা', 'Your review status']}
      summary={[
        'রিভিউ জমার সময় পাওয়া রিসিপ্ট দিয়ে অবস্থা দেখুন, প্রত্যাহার করুন বা সরানোর অনুরোধ করুন।',
        'Use the receipt you got when you submitted to check the status, withdraw the review or ask for removal.',
      ]}
    />
    <ReceiptStatusPanel />
    <RemovalRequestForm />
    <SwitchLink to={REVIEW_WRITE_PATH} text={['নতুন রিভিউ লিখুন', 'Write a new review']} />
  </div>
);
