import React, { useEffect, useState } from 'react';
import { AlertTriangle, FileDown, FolderOpen, HardDrive, Trash2 } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { useOnlineStatus } from '../../hooks/useNetworkState';
import { useDraftViewer } from '../../hooks/useReviewDraft';
import { buildDraftExport, clearUnsentDrafts, deleteDraft, type StoredDraft } from '../../offline/draftStore';
import { readStorageStatus, type Persistence } from '../../offline/storageStatus';
import type { DestinationSummary } from '../../types';
import { formatDateTime, formatNumber, pick } from '../../utils/format';
import { mustWait, sendFailureText } from './draftText';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';

/** A confirmation dialog around one destructive action (guideline 6.6: each asks first). */
const Confirm: React.FC<{ trigger: React.ReactNode; title: string; body: string; action: string; onConfirm: () => void }> = ({
  trigger,
  title,
  body,
  action,
  onConfirm,
}) => {
  const { t } = useLanguage();
  return (
    <Dialog>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{body}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">{t('বাতিল', 'Cancel')}</Button>
          </DialogClose>
          <DialogClose asChild>
            <Button type="button" variant="destructive" onClick={onConfirm}>
              <Trash2 aria-hidden="true" />
              {action}
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

/**
 * "Saved drafts on this device" on the Write page (R15 task 11; owner decision 9 Nov 2026): Open puts
 * a draft into the form, where Submit sends it; Delete and Clear all ask first; Export downloads the
 * unsent drafts as JSON, with receipts only after explicit confirmation (PF 18.2, guideline 6.6).
 */
export const SavedDrafts: React.FC<{
  drafts: StoredDraft[];
  destinations: DestinationSummary[];
  /** True when the destination list is only what is saved on this device (offline). */
  savedOnly: boolean;
  onOpen: (destinationId: string) => void;
}> = ({ drafts, destinations, savedOnly, onOpen }) => {
  const { language, t } = useLanguage();
  const online = useOnlineStatus();
  const viewer = useDraftViewer();
  const [persistence, setPersistence] = useState<Persistence>('unknown');
  const [includeReceipts, setIncludeReceipts] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void readStorageStatus().then((s) => {
      if (!cancelled) setPersistence(s.persistence);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  if (drafts.length === 0) return null;

  const nameOf = (id: string): string | null => {
    const found = destinations.find((d) => d.id === id);
    return found ? pick(language, found.name_bn, found.name_en) : null;
  };

  const download = () => {
    const file = buildDraftExport(drafts, { includeReceipts, destinationName: nameOf });
    const url = URL.createObjectURL(new Blob([JSON.stringify(file, null, 2)], { type: 'application/json;charset=utf-8' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `abhijatri-review-drafts-${file.exported_at.slice(0, 10)}.json`;
    link.click();
    URL.revokeObjectURL(url);
    setIncludeReceipts(false);
  };

  const count = formatNumber(drafts.length, language);

  return (
    <section aria-labelledby="saved-drafts-heading" className="tonal-card p-5 flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <HardDrive size={18} className="text-primary shrink-0" aria-hidden="true" />
        <h2 id="saved-drafts-heading" className="text-base font-bold font-title text-foreground">
          {t(`এই ডিভাইসে সংরক্ষিত খসড়া (${count})`, `Saved drafts on this device (${count})`)}
        </h2>
      </div>
      <p className="text-xs text-muted-foreground">
        {online
          ? t('কিছুই নিজে থেকে পাঠানো হয় না। একটি খসড়া খুলুন, দেখে নিন, তারপর "রিভিউ জমা দিন" চাপুন।', 'Nothing is sent by itself. Open a draft, check it, then press "Submit review".')
          : t('অফলাইনে খসড়া লেখা ও রাখা যায়; সংযোগ ফিরলে খুলে পাঠান।', 'Offline you can write and keep drafts; open and send them when you are back online.')}{' '}
        {t('খসড়া এনক্রিপ্ট করা নয়।', 'Drafts are not encrypted.')}
      </p>
      {persistence === 'refused' && (
        <p role="status" className="flex items-start gap-2 rounded-xl border border-amber-300 dark:border-amber-900 bg-amber-50 dark:bg-amber-950/40 px-3 py-2 text-xs text-amber-900 dark:text-amber-100">
          <AlertTriangle size={14} className="shrink-0 mt-0.5" aria-hidden="true" />
          {t(
            'এই ব্রাউজার জায়গা কম পড়লে সংরক্ষিত ডেটা মুছে ফেলতে পারে, তাই খসড়া হারাতে পারে। দরকারি খসড়া এক্সপোর্ট করে রাখুন।',
            'This browser may delete saved data when space runs low, so drafts can be lost. Export the drafts you need.',
          )}
        </p>
      )}

      <ul className="flex flex-col divide-y divide-border">
        {drafts.map((d) => {
          const name = d.destination_id ? nameOf(d.destination_id) : null;
          const openable = d.destination_id === '' || name !== null;
          const waiting = mustWait(d.retry_after);
          return (
            <li key={d.client_draft_id} className="py-2.5 flex flex-wrap items-center gap-x-3 gap-y-1.5">
              <div className="flex-1 min-w-48 flex flex-col gap-0.5">
                <span className="text-sm font-semibold text-foreground">
                  {d.destination_id === ''
                    ? t('গন্তব্য বাছা হয়নি', 'No destination chosen')
                    : (name ?? (savedOnly
                        ? t('এই ডিভাইসে সংরক্ষিত নয় এমন গন্তব্য', 'A destination not saved on this device')
                        : t('গন্তব্যটি আর পাওয়া যাচ্ছে না', 'Destination no longer available')))}
                  {' · '}
                  <span className="font-normal">{d.fields.title.trim() || t('(শিরোনাম নেই)', '(no title)')}</span>
                </span>
                <span className="text-[11px] text-muted-foreground">{formatDateTime(d.updated_at, language)}</span>
                {d.last_error && (
                  <span className={`text-[11px] ${d.state === 'NEEDS_ATTENTION' ? 'text-destructive' : 'text-amber-800 dark:text-amber-300'}`}>
                    {sendFailureText(d.last_error, t, language, d.retry_after)}
                  </span>
                )}
              </div>
              {d.state === 'NEEDS_ATTENTION' && <Badge variant="destructive">{t('বদলাতে হবে', 'Needs a change')}</Badge>}
              {d.state === 'SUBMITTING' && <Badge variant="secondary">{t('পাঠানো হচ্ছে…', 'Sending…')}</Badge>}
              {d.state === 'DRAFT' && waiting && <Badge variant="outline">{t('অপেক্ষায়', 'Waiting')}</Badge>}
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={!openable}
                title={openable ? undefined : t('সংযোগ ফিরলে খোলা যাবে', 'Can be opened when this destination is available')}
                onClick={() => onOpen(d.destination_id)}
              >
                <FolderOpen aria-hidden="true" />
                {t('খুলুন', 'Open')}
              </Button>
              <Confirm
                trigger={
                  <Button type="button" variant="ghost" size="sm" className="text-destructive hover:text-destructive">
                    <Trash2 aria-hidden="true" />
                    {t('মুছুন', 'Delete')}
                  </Button>
                }
                title={t('খসড়াটি মুছবেন?', 'Delete this draft?')}
                body={t('খসড়াটি এই ডিভাইস থেকে মুছে যাবে। এটি ফেরানো যাবে না।', 'The draft is removed from this device. This cannot be undone.')}
                action={t('মুছুন', 'Delete')}
                onConfirm={() => void deleteDraft(d.client_draft_id)}
              />
            </li>
          );
        })}
      </ul>

      <div className="flex flex-wrap gap-2 pt-1">
        <Dialog onOpenChange={(open) => !open && setIncludeReceipts(false)}>
          <DialogTrigger asChild>
            <Button type="button" variant="outline" size="sm">
              <FileDown aria-hidden="true" />
              {t('এক্সপোর্ট', 'Export')}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t('খসড়া এক্সপোর্ট করুন', 'Export drafts')}</DialogTitle>
              <DialogDescription>
                {t(
                  'না পাঠানো খসড়াগুলো একটি JSON ফাইলে নামানো হবে। ফাইলটি এনক্রিপ্ট করা নয়; নিরাপদে রাখুন। জমা হওয়া রিভিউয়ের রিসিপ্ট কখনো থাকে না।',
                  'Your unsent drafts are downloaded as a JSON file. The file is not encrypted; keep it safe. Receipts of submitted reviews are never included.',
                )}
              </DialogDescription>
            </DialogHeader>
            <label className="flex items-start gap-2 min-h-11 cursor-pointer text-sm text-foreground">
              <input
                type="checkbox"
                checked={includeReceipts}
                onChange={(e) => setIncludeReceipts(e.target.checked)}
                className="mt-0.5 h-5 w-5 accent-forest-primary dark:accent-neon-lime"
              />
              <span>
                {t(
                  'খসড়াগুলোর রিসিপ্টও যোগ করুন। রিসিপ্ট দিয়ে রিভিউ দেখা ও প্রত্যাহার করা যায়, তাই ফাইলটি কাউকে দেবেন না।',
                  'Also include the drafts’ receipts. A receipt lets anyone check and withdraw the review, so do not share the file.',
                )}
              </span>
            </label>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">{t('বাতিল', 'Cancel')}</Button>
              </DialogClose>
              <DialogClose asChild>
                <Button type="button" onClick={download}>
                  <FileDown aria-hidden="true" />
                  {t('ডাউনলোড', 'Download')}
                </Button>
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
        {drafts.length > 1 && viewer && (
          <Confirm
            trigger={
              <Button type="button" variant="ghost" size="sm" className="text-destructive hover:text-destructive">
                <Trash2 aria-hidden="true" />
                {t('সব মুছুন', 'Clear all')}
              </Button>
            }
            title={t(`${count}টি খসড়াই মুছবেন?`, `Delete all ${count} drafts?`)}
            body={t('এই ডিভাইসের সব না পাঠানো খসড়া মুছে যাবে। এটি ফেরানো যাবে না।', 'Every unsent draft on this device is removed. This cannot be undone.')}
            action={t('সব মুছুন', 'Clear all')}
            onConfirm={() => void clearUnsentDrafts(viewer)}
          />
        )}
      </div>
    </section>
  );
};
