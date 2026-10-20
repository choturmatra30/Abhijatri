import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowRight, Clock, LogIn } from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';

/**
 * Member sign-in screen (Gantt R05). The account service (R04) does not exist yet, so the form
 * is shown but disabled and nothing is sent anywhere. When R04 lands, this form posts to
 * `POST /api/v1/auth/login` with credentialed fetch and the CSRF flow of PF 16.2.
 */
export const SignInPage: React.FC = () => {
  const { t } = useLanguage();
  const inputClass =
    'w-full px-3.5 min-h-[44px] rounded-xl bg-surface-sage/40 dark:bg-dark-surface-2 border border-surface-muted/50 dark:border-dark-surface-2 text-sm text-on-surface dark:text-on-dark disabled:opacity-60 disabled:cursor-not-allowed';

  return (
    <div className="max-w-md mx-auto px-4 sm:px-6 py-10 sm:py-16 flex flex-col gap-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-2xl sm:text-3xl font-bold font-title text-on-surface dark:text-on-dark">{t('সাইন ইন', 'Sign in')}</h1>
        <p className="text-sm text-on-surface-variant dark:text-on-dark-muted">
          {t('আপনার অভিযাত্রী সদস্য অ্যাকাউন্টে প্রবেশ করুন।', 'Sign in to your Abhijatri member account.')}
        </p>
      </div>

      <div role="status" className="p-4 rounded-xl bg-amber-50 border border-amber-200 dark:bg-amber-950/30 dark:border-amber-900/50 flex gap-3 text-sm text-amber-900 dark:text-amber-200">
        <Clock size={18} className="shrink-0 mt-0.5" aria-hidden="true" />
        <p>
          {t(
            'সদস্য অ্যাকাউন্ট এখনো চালু হয়নি। চালু না হওয়া পর্যন্ত অতিথি হিসেবে সব গাইড দেখতে ও লেখায় রিভিউ দিতে পারবেন।',
            'Member accounts are not open yet. Until they are, you can read every guide and write text reviews as a guest.',
          )}
        </p>
      </div>

      <form className="tonal-card p-6 flex flex-col gap-4" onSubmit={(e) => e.preventDefault()} aria-describedby="signin-unavailable">
        <fieldset disabled className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signin-email" className="text-xs font-bold text-on-surface-variant dark:text-on-dark-muted">
              {t('ইমেইল', 'Email')}
            </label>
            <input id="signin-email" type="email" autoComplete="email" inputMode="email" className={inputClass} />
          </div>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signin-password" className="text-xs font-bold text-on-surface-variant dark:text-on-dark-muted">
              {t('পাসওয়ার্ড', 'Password')}
            </label>
            <input id="signin-password" type="password" autoComplete="current-password" className={inputClass} />
          </div>
          <button
            type="submit"
            className="inline-flex items-center justify-center gap-2 min-h-[48px] rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-sm font-bold font-title disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <LogIn size={16} aria-hidden="true" />
            {t('সাইন ইন', 'Sign in')}
          </button>
        </fieldset>
        <p id="signin-unavailable" className="text-xs text-on-surface-variant dark:text-on-dark-muted">
          {t(
            'সাইন আপের পর "যাচাইকৃত সদস্য" হতে আলাদা একটি অনুমোদিত যাচাই লাগবে; ইমেইল যাচাই একা যথেষ্ট নয়।',
            'After signing up, becoming a Verified Member needs a separate approved verification; email verification alone is not enough.',
          )}
        </p>
      </form>

      <Link
        to="/overview"
        className="self-center inline-flex items-center gap-2 min-h-[44px] px-5 rounded-full bg-surface-sage dark:bg-dark-surface-1 text-forest-primary dark:text-neon-lime text-sm font-bold font-title"
      >
        {t('অতিথি হিসেবে চালিয়ে যান', 'Continue as guest')}
        <ArrowRight size={16} aria-hidden="true" />
      </Link>
    </div>
  );
};
