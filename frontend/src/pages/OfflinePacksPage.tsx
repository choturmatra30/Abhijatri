import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, CheckCircle2, DownloadCloud, HardDrive, Loader2, RefreshCw, Trash2 } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { useOfflinePacks } from '../hooks/useOfflinePacks';
import { useOnlineStatus } from '../hooks/useNetworkState';
import { download, removePack } from '../offline/packManager';
import { isPackExpired } from '../offline/packAdapter';
import { readStorageStatus, type StorageStatus } from '../offline/storageStatus';
import type { StoredPack } from '../offline/db';
import { LoadingState } from '../components/common/StatusViews';
import { FAILURE_TEXT, formatSize } from '../components/offline/packText';
import { formatNumber, formatTimestamp, pick } from '../utils/format';
import { Button, buttonVariants } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';

/** Persistence and space used (PF 18.2; Offline-Frontend-Guideline 4.4). Never claims durability that was refused. */
const StorageCard: React.FC<{ packCount: number }> = ({ packCount }) => {
  const { language, t } = useLanguage();
  const [status, setStatus] = useState<StorageStatus | null>(null);
  useEffect(() => {
    void readStorageStatus().then(setStatus);
  }, [packCount]);
  if (!status) return null;
  return (
    <section aria-labelledby="storage-heading" className="tonal-card p-5 flex flex-col gap-2">
      <h2 id="storage-heading" className="inline-flex items-center gap-2 text-sm font-bold font-title text-foreground">
        <HardDrive size={16} aria-hidden="true" />
        {t('এই ডিভাইসের সংরক্ষণ', 'Storage on this device')}
      </h2>
      <p className="text-sm text-foreground">
        {status.persistence === 'granted'
          ? t('ব্রাউজার সংরক্ষিত প্যাক স্থায়ীভাবে রাখার অনুমতি দিয়েছে।', 'The browser has agreed to keep saved packs.')
          : status.persistence === 'refused'
            ? t(
                'ব্রাউজার স্থায়ী সংরক্ষণের অনুমতি দেয়নি: জায়গা কম পড়লে সংরক্ষিত প্যাক মুছে যেতে পারে। যাত্রার আগে প্যাকগুলো এখানে আছে কি না দেখে নিন।',
                'The browser has not agreed to keep saved data: if space runs low, saved packs may be deleted. Check they are still here before you travel.',
              )
            : t('ব্রাউজার জানায়নি সংরক্ষিত প্যাক কতদিন থাকবে।', 'The browser does not say how long saved packs are kept.')}
      </p>
      {status.usageBytes !== null && (
        <p className="text-xs text-muted-foreground">
          {t('এই সাইটের ব্যবহৃত জায়গা', 'Space used by this site')}: {formatSize(status.usageBytes, language)}
        </p>
      )}
    </section>
  );
};

const PackRow: React.FC<{ stored: StoredPack }> = ({ stored }) => {
  const { language, t } = useLanguage();
  const online = useOnlineStatus();
  const { jobs } = useOfflinePacks();
  const job = jobs[stored.destination_id];
  const { pack } = stored;
  const name = pick(language, pack.destination.name_bn, pack.destination.name_en);
  const expired = isPackExpired(stored);
  const busy = job?.status === 'downloading';

  const state = busy
    ? { icon: Loader2, spin: true, tone: 'text-primary', text: t('হালনাগাদ হচ্ছে…', 'Updating…') }
    : expired
      ? { icon: AlertTriangle, spin: false, tone: 'text-red-700 dark:text-red-300', text: t('পুরনো: সংযোগ ফিরলে হালনাগাদ করুন', 'Out of date: update when online') }
      : stored.update_available
        ? { icon: RefreshCw, spin: false, tone: 'text-amber-700 dark:text-amber-300', text: t('নতুন তথ্য আছে', 'Update available') }
        : { icon: CheckCircle2, spin: false, tone: 'text-primary', text: t('প্রস্তুত', 'Ready') };
  const StateIcon = state.icon;

  return (
    <li className="tonal-card p-5 flex flex-col gap-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <Link to={`/destinations/${stored.destination_id}`} className="text-lg font-bold font-title text-foreground hover:text-primary [overflow-wrap:anywhere]">
            {name}
          </Link>
          <p className="text-xs text-muted-foreground">
            {t('তৈরি', 'Snapshot')}: {formatTimestamp(pack.generated_at, language)} · {formatSize(stored.size_bytes, language)} ·{' '}
            {t(`${formatNumber(pack.reviews.count, 'bn')}টি রিভিউ`, `${pack.reviews.count} review${pack.reviews.count === 1 ? '' : 's'}`)}
          </p>
          <p className="text-xs text-muted-foreground">
            {t('মেয়াদ', 'Valid until')}: {formatTimestamp(pack.expires_at, language)}
          </p>
        </div>
        <p className={`inline-flex items-center gap-1.5 text-xs font-semibold ${state.tone}`}>
          <StateIcon size={14} className={state.spin ? 'motion-safe:animate-spin' : ''} aria-hidden="true" />
          {state.text}
        </p>
      </div>
      {job?.status === 'failed' && <p role="alert" className="text-xs text-destructive">{t(...FAILURE_TEXT[job.reason])}</p>}
      <div className="flex flex-wrap gap-2">
        <Link to={`/destinations/${stored.destination_id}`} className={buttonVariants({ variant: 'outline', size: 'sm' })}>
          {t('খুলুন', 'Open')}
        </Link>
        {online && (
          <Button type="button" size="sm" variant="secondary" disabled={busy} onClick={() => void download(stored.destination_id)}>
            <RefreshCw aria-hidden="true" />
            {t('হালনাগাদ', 'Update')}
          </Button>
        )}
        <Dialog>
          <DialogTrigger asChild>
            <Button type="button" size="sm" variant="ghost" disabled={busy} className="text-destructive hover:text-destructive">
              <Trash2 aria-hidden="true" />
              {t('মুছুন', 'Delete')}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t(`${name}-এর অফলাইন প্যাক মুছবেন?`, `Delete the offline pack for ${name}?`)}</DialogTitle>
              <DialogDescription>
                {t(
                  'শুধু এই প্যাকটি এই ডিভাইস থেকে মুছে যাবে। ইন্টারনেট ছাড়া গাইডটি আর খোলা যাবে না, যদি না আবার সংরক্ষণ করেন।',
                  'Only this pack is removed from this device. Without internet the guide will not open unless you save it again.',
                )}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">{t('বাতিল', 'Cancel')}</Button>
              </DialogClose>
              <DialogClose asChild>
                <Button type="button" variant="destructive" onClick={() => void removePack(stored.destination_id)}>
                  <Trash2 aria-hidden="true" />
                  {t('মুছুন', 'Delete')}
                </Button>
              </DialogClose>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </li>
  );
};

/** Offline packs (R13; Offline-Frontend-Guideline 5.6, 5.7): what is saved, its state, delete, storage. */
export const OfflinePacksPage: React.FC = () => {
  const { t } = useLanguage();
  const { packs, storage } = useOfflinePacks();

  return (
    <div className="flex flex-col gap-6 pb-12 max-w-3xl mx-auto">
      <div>
        <h1 className="flex items-center gap-2 text-2xl sm:text-3xl font-bold font-title text-foreground tracking-tight">
          <DownloadCloud size={26} className="text-primary shrink-0" aria-hidden="true" />
          {t('অফলাইন প্যাক', 'Offline packs')}
        </h1>
        <p className="text-sm text-muted-foreground mt-1">
          {t(
            'সংরক্ষিত গন্তব্য গাইড ইন্টারনেট ছাড়াই খোলা যায়: সতর্কতা, জরুরি নম্বর ও সাম্প্রতিক রিভিউসহ। প্রতিটি প্যাক ৭ দিন বৈধ; সংযোগ ফিরলে নিজে থেকেই হালনাগাদ হয়।',
            'Saved destination guides open without internet, with advisories, emergency numbers and recent reviews. Each pack is valid for 7 days and updates itself when you are back online.',
          )}
        </p>
      </div>

      {packs === null && <LoadingState />}

      {packs !== null && storage !== 'ok' && (
        <p role="alert" className="tonal-card p-5 text-sm text-foreground">{t(...FAILURE_TEXT[storage])}</p>
      )}

      {packs !== null && storage === 'ok' && packs.length === 0 && (
        <div role="status" className="tonal-card p-10 flex flex-col items-center gap-3 text-center">
          <DownloadCloud size={28} className="text-primary" aria-hidden="true" />
          <p className="text-base font-bold font-title text-foreground">{t('এখনো কোনো প্যাক সংরক্ষিত নেই', 'No packs saved yet')}</p>
          <p className="text-xs text-muted-foreground max-w-md">
            {t(
              'একটি গন্তব্য খুলে "অফলাইনের জন্য সংরক্ষণ করুন" চাপুন।',
              'Open a destination and press "Save for offline use".',
            )}
          </p>
          <Link to="/destinations" className={buttonVariants()}>
            {t('গন্তব্য দেখুন', 'Browse destinations')}
          </Link>
        </div>
      )}

      {packs !== null && packs.length > 0 && (
        <ul className="flex flex-col gap-3">
          {[...packs]
            .sort((a, b) => a.pack.destination.name_en.localeCompare(b.pack.destination.name_en))
            .map((stored) => (
              <PackRow key={stored.destination_id} stored={stored} />
            ))}
        </ul>
      )}

      {packs !== null && <StorageCard packCount={packs.length} />}
    </div>
  );
};
