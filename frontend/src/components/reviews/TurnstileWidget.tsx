import React, { useEffect, useRef, useState } from 'react';
import { useLanguage } from '../../context/LanguageContext';

/**
 * Cloudflare Turnstile for Guest writes (PF 14.1). The API checks the token's hostname and
 * action server-side; a token is single use, so the form remounts this widget (new `key`) after
 * every submission attempt.
 *
 * Without `VITE_TURNSTILE_SITE_KEY` nothing renders and no token is sent. That matches local
 * development, where the API runs with TURNSTILE_ENABLED=false.
 */
export const TURNSTILE_SITE_KEY = import.meta.env.VITE_TURNSTILE_SITE_KEY || '';
const SCRIPT_SRC = 'https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';

let scriptPromise: Promise<void> | null = null;

function loadScript(): Promise<void> {
  if (window.turnstile) return Promise.resolve();
  if (!scriptPromise) {
    scriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = SCRIPT_SRC;
      script.async = true;
      script.onload = () => resolve();
      script.onerror = () => {
        scriptPromise = null;
        reject(new Error('Turnstile failed to load'));
      };
      document.head.appendChild(script);
    });
  }
  return scriptPromise;
}

export const TurnstileWidget: React.FC<{ action: string; onToken: (token: string | null) => void }> = ({
  action,
  onToken,
}) => {
  const { language, t } = useLanguage();
  const container = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!TURNSTILE_SITE_KEY) return;
    let widgetId: string | null = null;
    let cancelled = false;
    onToken(null);
    loadScript()
      .then(() => {
        if (cancelled || !container.current || !window.turnstile) return;
        widgetId = window.turnstile.render(container.current, {
          sitekey: TURNSTILE_SITE_KEY,
          action,
          language: language === 'bn' ? 'bn' : 'en',
          callback: (token) => onToken(token),
          'expired-callback': () => onToken(null),
          'error-callback': () => onToken(null),
        });
      })
      .catch(() => setFailed(true));
    return () => {
      cancelled = true;
      if (widgetId && window.turnstile) window.turnstile.remove(widgetId);
    };
    // Re-render only when the action or language changes; onToken is a state setter.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [action, language]);

  if (!TURNSTILE_SITE_KEY) return null;
  return (
    <div className="flex flex-col gap-1">
      <div ref={container} />
      {failed && (
        <p role="alert" className="text-xs text-error-alert dark:text-red-400">
          {t(
            'নিরাপত্তা যাচাই লোড হয়নি। সংযোগ দেখে পাতাটি আবার খুলুন।',
            'The security check did not load. Check your connection and reload the page.',
          )}
        </p>
      )}
    </div>
  );
};
