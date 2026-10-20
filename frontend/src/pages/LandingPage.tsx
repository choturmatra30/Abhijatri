import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BadgeCheck,
  Check,
  Clock,
  ImagePlus,
  LogIn,
  MapPin,
  MessageSquareText,
  Phone,
  ShieldAlert,
  UserRound,
} from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { listAllDestinations } from '../api/destinations';
import { useApiResource } from '../hooks/useApiResource';
import { pick } from '../utils/format';

type Capability = { icon: typeof Check; bn: string; en: string; planned?: boolean };

/** What a Guest can do today (Execution.md rules 1 to 4; Review.md 2.1). */
const GUEST: Capability[] = [
  { icon: MapPin, bn: 'গন্তব্য গাইড, মৌসুম ও বিধিনিষেধ দেখুন', en: 'Read destination guides, seasons and restrictions' },
  { icon: ShieldAlert, bn: 'সূত্র ও তারিখসহ নিরাপত্তা সতর্কতা', en: 'See dated safety advisories with sources' },
  { icon: Phone, bn: 'জরুরি যোগাযোগের নম্বর', en: 'Find emergency contact numbers' },
  { icon: MessageSquareText, bn: 'শুধু লেখায় রিভিউ দিন (মডারেশনের পর প্রকাশ)', en: 'Write text-only reviews, published after moderation' },
];

/** What an account adds (Review.md 2.1, 6.1, 8). Not available until accounts open (R04). */
const MEMBER: Capability[] = [
  { icon: UserRound, bn: 'নিজের অ্যাকাউন্টে রিভিউ রাখুন ও পরিচালনা করুন', en: 'Keep and manage reviews in your own account', planned: true },
  { icon: BadgeCheck, bn: 'যাচাইকৃত সদস্যের রেটিং কমিউনিটি রেটিংয়ে গণনা হয়', en: 'Verified Member ratings count towards Community Rating', planned: true },
  { icon: ImagePlus, bn: 'যাচাইকৃত সদস্যরা রিভিউতে ছবি যোগ করতে পারবেন', en: 'Verified Members can add photos to reviews', planned: true },
];

const CapabilityList: React.FC<{ items: Capability[] }> = ({ items }) => {
  const { t } = useLanguage();
  return (
    <ul className="flex flex-col gap-3">
      {items.map(({ icon: Icon, bn, en, planned }) => (
        <li key={en} className="flex items-start gap-3 text-sm">
          <span className="mt-0.5 w-7 h-7 shrink-0 rounded-full bg-surface-sage dark:bg-dark-surface-2 text-forest-primary dark:text-neon-lime flex items-center justify-center">
            <Icon size={15} aria-hidden="true" />
          </span>
          <span className="text-on-surface dark:text-on-dark">
            {t(bn, en)}
            {planned && (
              <span className="ml-2 inline-flex items-center gap-1 align-middle px-2 py-0.5 rounded-full bg-amber-100 dark:bg-amber-950/50 text-amber-800 dark:text-amber-300 text-[10px] font-bold">
                <Clock size={10} aria-hidden="true" />
                {t('শীঘ্রই', 'Coming soon')}
              </span>
            )}
          </span>
        </li>
      ))}
    </ul>
  );
};

export const LandingPage: React.FC = () => {
  const { language, t } = useLanguage();
  // Optional teaser: the page is fully usable even if this request fails.
  const { data: destinations } = useApiResource((signal) => listAllDestinations(signal), []);

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 sm:py-16 flex flex-col gap-12">
      <section className="flex flex-col gap-4 max-w-3xl">
        <p className="text-xs font-bold uppercase tracking-wider text-forest-primary dark:text-neon-lime">
          {t('বাংলাদেশ ভ্রমণের সঙ্গী', 'Your travel companion for Bangladesh')}
        </p>
        <h1 className="text-3xl sm:text-5xl font-bold font-title tracking-tight text-on-surface dark:text-on-dark leading-tight">
          {t('যাওয়ার আগে জানুন, ফিরে এসে জানান', 'Know before you go. Share when you are back.')}
        </h1>
        <p className="text-base sm:text-lg font-body leading-relaxed text-on-surface-variant dark:text-on-dark-muted">
          {t(
            'সূত্র ও তারিখসহ গন্তব্য গাইড, নিরাপত্তা সতর্কতা, জরুরি নম্বর আর মডারেশন করা ভ্রমণকারীর রিভিউ, বাংলায় ও ইংরেজিতে।',
            'Source-dated destination guides, safety advisories, emergency numbers and moderated traveller reviews, in Bangla and English.',
          )}
        </p>
      </section>

      <section aria-label={t('কীভাবে শুরু করবেন', 'How to start')} className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <article className="tonal-card p-6 sm:p-8 flex flex-col gap-5 border-forest-primary/30 dark:border-neon-lime/30">
          <div className="flex flex-col gap-1">
            <h2 className="text-xl font-bold font-title text-on-surface dark:text-on-dark">{t('অতিথি হিসেবে দেখুন', 'Explore as a guest')}</h2>
            <p className="text-sm text-on-surface-variant dark:text-on-dark-muted">
              {t('কোনো অ্যাকাউন্ট বা ব্যক্তিগত তথ্য লাগবে না।', 'No account and no personal details needed.')}
            </p>
          </div>
          <CapabilityList items={GUEST} />
          <Link
            to="/overview"
            className="mt-auto inline-flex items-center justify-center gap-2 min-h-[48px] px-6 rounded-full bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base text-sm font-bold font-title hover:opacity-95"
          >
            {t('অতিথি হিসেবে চালিয়ে যান', 'Continue as guest')}
            <ArrowRight size={16} aria-hidden="true" />
          </Link>
        </article>

        <article className="tonal-card p-6 sm:p-8 flex flex-col gap-5">
          <div className="flex flex-col gap-1">
            <h2 className="text-xl font-bold font-title text-on-surface dark:text-on-dark">{t('সদস্য হিসেবে সাইন ইন', 'Sign in as a member')}</h2>
            <p className="text-sm text-on-surface-variant dark:text-on-dark-muted">
              {t('অতিথির সব সুবিধা, সাথে আরও কিছু।', 'Everything a guest can do, and more.')}
            </p>
          </div>
          <CapabilityList items={MEMBER} />
          <Link
            to="/login"
            className="mt-auto inline-flex items-center justify-center gap-2 min-h-[48px] px-6 rounded-full border border-forest-primary/40 dark:border-neon-lime/40 text-forest-primary dark:text-neon-lime text-sm font-bold font-title hover:bg-surface-sage dark:hover:bg-dark-surface-2"
          >
            <LogIn size={16} aria-hidden="true" />
            {t('সাইন ইন', 'Sign in')}
          </Link>
        </article>
      </section>

      {destinations && destinations.length > 0 && (
        <section aria-labelledby="landing-destinations" className="flex flex-col gap-3">
          <h2 id="landing-destinations" className="text-sm font-bold text-on-surface-variant dark:text-on-dark-muted">
            {t('এখনই দেখুন', 'Start exploring')}
          </h2>
          <ul className="flex flex-wrap gap-2">
            {destinations.map((d) => (
              <li key={d.id}>
                <Link
                  to={`/destinations/${d.id}`}
                  className="inline-flex items-center gap-1.5 min-h-[44px] px-4 rounded-full bg-surface-sage dark:bg-dark-surface-1 text-forest-primary dark:text-neon-lime text-sm font-semibold hover:bg-surface-container dark:hover:bg-dark-surface-2"
                >
                  <MapPin size={14} aria-hidden="true" />
                  {pick(language, d.name_bn, d.name_en)}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
};
