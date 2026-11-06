import React, { useEffect } from 'react';
import { useRegisterSW } from 'virtual:pwa-register/react';
import { CloudOff, RefreshCw, X } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { buttonVariants } from '@/components/ui/button';
import { requestPersistentStorage } from '../../offline/savedDestinations';

const HOUR = 60 * 60 * 1000;

/**
 * Registers the service worker (after the page has loaded, so it never competes with first render)
 * and tells the reader about it (Gantt R12; Frontend-Implemented 5i):
 * - first install: a short note that opened pages now work offline;
 * - a new deploy: "a new version is available" with Reload. Nothing changes until the reader agrees,
 *   so a form being filled in is never lost to a surprise reload.
 */
export const UpdatePrompt: React.FC = () => {
  const { t } = useLanguage();
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      // Long-open tabs still learn about new deploys.
      if (registration) window.setInterval(() => void registration.update(), HOUR);
      // Saved destinations should survive storage pressure; a refusal is fine (PF 18.2).
      void requestPersistentStorage();
    },
  });

  useEffect(() => {
    if (!offlineReady) return undefined;
    const timer = window.setTimeout(() => setOfflineReady(false), 6000);
    return () => window.clearTimeout(timer);
  }, [offlineReady, setOfflineReady]);

  if (!needRefresh && !offlineReady) return null;

  return (
    <div role="status" aria-live="polite" className="fixed bottom-4 left-4 right-4 sm:right-auto sm:max-w-sm z-[60] tonal-card p-4 shadow-lg flex flex-col gap-3">
      <p className="flex items-start gap-2 text-sm text-foreground">
        {needRefresh ? <RefreshCw size={16} className="shrink-0 mt-0.5 text-primary" aria-hidden="true" /> : <CloudOff size={16} className="shrink-0 mt-0.5 text-primary" aria-hidden="true" />}
        <span>
          {needRefresh
            ? t('অভিযাত্রীর নতুন সংস্করণ এসেছে। নতুন করে লোড করলে চালু হবে।', 'A new version of Abhijatri is available. Reload to use it.')
            : t('অফলাইনের জন্য প্রস্তুত: যে গন্তব্য পাতা খুলবেন, সংযোগ ছাড়াও ৭ দিন পর্যন্ত দেখা যাবে।', 'Ready for offline use: destination pages you open stay readable without a connection for up to 7 days.')}
        </span>
      </p>
      <div className="flex flex-wrap gap-2 justify-end">
        {needRefresh && (
          <button type="button" onClick={() => void updateServiceWorker(true)} className={buttonVariants({ size: 'sm' })}>
            <RefreshCw aria-hidden="true" />
            {t('নতুন করে লোড', 'Reload')}
          </button>
        )}
        <button
          type="button"
          onClick={() => {
            setNeedRefresh(false);
            setOfflineReady(false);
          }}
          className={buttonVariants({ variant: 'ghost', size: 'sm' })}
        >
          <X aria-hidden="true" />
          {needRefresh ? t('পরে', 'Later') : t('ঠিক আছে', 'OK')}
        </button>
      </div>
    </div>
  );
};
