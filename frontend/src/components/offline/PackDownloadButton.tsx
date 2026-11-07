import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { CheckCircle2, DownloadCloud, Loader2, RefreshCw, X } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { useOfflinePacks } from '../../hooks/useOfflinePacks';
import { useOnlineStatus } from '../../hooks/useNetworkState';
import { getPackManifest } from '../../api/packs';
import { cancelDownload, download } from '../../offline/packManager';
import { isPackExpired } from '../../offline/packAdapter';
import { formatTimestamp } from '../../utils/format';
import { buttonVariants } from '@/components/ui/button';
import { FAILURE_TEXT, formatSize } from './packText';

/**
 * Save a destination for offline use (R13; Offline-Frontend-Guideline 5.6, 5.7). Shows the size before
 * downloading; the user chooses (Security 7.4: user-selected packs). States: not downloaded,
 * downloading (Cancel), failed (Retry; any old pack stays), ready, update available, out of date.
 */
export const PackDownloadButton: React.FC<{ destinationId: string }> = ({ destinationId }) => {
  const { language, t } = useLanguage();
  const online = useOnlineStatus();
  const { packs, jobs, storage } = useOfflinePacks();
  const stored = packs?.find((p) => p.destination_id === destinationId) ?? null;
  const job = jobs[destinationId];
  const [size, setSize] = useState<number | null>(null);

  // The size is shown before the first download; one small public request, only while online.
  useEffect(() => {
    if (!online || stored || packs === null) return undefined;
    const controller = new AbortController();
    getPackManifest(destinationId, controller.signal)
      .then((m) => setSize(m.size_bytes))
      .catch(() => undefined);
    return () => controller.abort();
  }, [destinationId, online, stored, packs]);

  if (packs === null) return null;

  const box = 'flex flex-col gap-2 rounded-xl border border-border bg-card p-4';

  if (job?.status === 'downloading') {
    return (
      <div className={box} role="status" aria-live="polite">
        <p className="inline-flex items-center gap-2 text-sm font-semibold text-foreground">
          <Loader2 size={16} className="motion-safe:animate-spin text-primary" aria-hidden="true" />
          {t('অফলাইনের জন্য সংরক্ষণ হচ্ছে…', 'Saving for offline use…')}
        </p>
        <button type="button" onClick={() => cancelDownload(destinationId)} className={buttonVariants({ variant: 'ghost', size: 'sm', className: 'self-start' })}>
          <X aria-hidden="true" />
          {t('বাতিল', 'Cancel')}
        </button>
      </div>
    );
  }

  const failed = job?.status === 'failed' ? job.reason : null;
  const expired = stored ? isPackExpired(stored) : false;

  if (stored) {
    const canUpdate = online && (stored.update_available || expired);
    return (
      <div className={box}>
        <p className="inline-flex items-start gap-2 text-sm font-semibold text-foreground">
          <CheckCircle2 size={16} className="shrink-0 mt-0.5 text-primary" aria-hidden="true" />
          <span>
            {expired
              ? t('অফলাইন কপি পুরনো হয়ে গেছে', 'Offline copy is out of date')
              : t('অফলাইনের জন্য সংরক্ষিত', 'Saved for offline use')}
            <span className="block text-xs font-normal text-muted-foreground">
              {t('তৈরি', 'Snapshot')}: {formatTimestamp(stored.pack.generated_at, language)} · {formatSize(stored.size_bytes, language)}
            </span>
          </span>
        </p>
        {failed && <p role="alert" className="text-xs text-destructive">{t(...FAILURE_TEXT[failed])}</p>}
        <div className="flex flex-wrap gap-2">
          {canUpdate && (
            <button type="button" onClick={() => void download(destinationId)} className={buttonVariants({ size: 'sm' })}>
              <RefreshCw aria-hidden="true" />
              {t('হালনাগাদ করুন', 'Update')}
            </button>
          )}
          <Link to="/offline-packs" className={buttonVariants({ variant: 'outline', size: 'sm' })}>
            {t('অফলাইন প্যাক', 'Offline packs')}
          </Link>
        </div>
      </div>
    );
  }

  if (!online) return null; // nothing saved and no connection: the page already says so
  if (storage !== 'ok') {
    return <p className="text-xs text-muted-foreground">{t(...FAILURE_TEXT[storage])}</p>;
  }

  return (
    <div className={box}>
      <p className="text-sm text-foreground">
        {t(
          'গাইড, সতর্কতা, জরুরি নম্বর ও সাম্প্রতিক রিভিউ এই ডিভাইসে রাখুন, যাতে ইন্টারনেট ছাড়াও দেখা যায়।',
          'Keep the guide, advisories, emergency numbers and recent reviews on this device, readable without internet.',
        )}
      </p>
      {failed && <p role="alert" className="text-xs text-destructive">{t(...FAILURE_TEXT[failed])}</p>}
      <button type="button" onClick={() => void download(destinationId)} className={buttonVariants({ className: 'self-start' })}>
        {failed ? <RefreshCw aria-hidden="true" /> : <DownloadCloud aria-hidden="true" />}
        {failed ? t('আবার চেষ্টা করুন', 'Try again') : t('অফলাইনের জন্য সংরক্ষণ করুন', 'Save for offline use')}
        {size !== null && ` (${formatSize(size, language)})`}
      </button>
    </div>
  );
};
