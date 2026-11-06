import React from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight,
  BadgeCheck,
  Check,
  Clock,
  Cloudy,
  ImagePlus,
  Leaf,
  LogIn,
  MapPin,
  MessageSquareText,
  Mountain,
  Phone,
  ShieldAlert,
  Trees,
  UserRound,
  Waves,
} from 'lucide-react';
import { useLanguage } from '../context/LanguageContext';
import { useSession } from '../context/SessionContext';
import { useDestinationCatalog } from '../hooks/useDestinationCatalog';
import { ErrorState } from '../components/common/StatusViews';
import { pick } from '../utils/format';
import { InteractiveSelector, type SelectorOption } from '../components/ui/interactive-selector';
import { ImageCredit } from '../components/common/ImageCredit';
import { destinationImage } from '../data/destinationImages';
import { buttonVariants } from '@/components/ui/button';

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

/** One icon per seeded destination; anything new falls back to a map pin. */
const DESTINATION_ICON: Record<string, typeof MapPin> = {
  "Cox's Bazar": Waves,
  'Sajek Valley': Cloudy,
  Sylhet: Leaf,
  Sundarbans: Trees,
  Bandarban: Mountain,
};

export const LandingPage: React.FC = () => {
  const { language, t } = useLanguage();
  const { session } = useSession();
  // Optional teaser: the page is fully usable even if this request fails.
  // Offline, the selector shows only destinations saved on this device (Frontend-Implemented 5i).
  const { data: catalog, loading: destinationsLoading, error: destinationsError, reload: reloadDestinations } = useDestinationCatalog();
  const destinations = catalog?.items ?? null;

  return (
    <div className="max-w-6xl mx-auto px-4 sm:px-6 py-10 sm:py-16 flex flex-col gap-12">
      <section className="flex flex-col gap-4 max-w-3xl">
        <p className="text-xs font-bold uppercase tracking-wider text-primary">
          {t('বাংলাদেশ ভ্রমণের সঙ্গী', 'Your travel companion for Bangladesh')}
        </p>
        <h1 className="text-3xl sm:text-5xl font-bold font-title tracking-tight text-foreground leading-tight">
          {t('যাওয়ার আগে জানুন, ফিরে এসে জানান', 'Know before you go. Share when you are back.')}
        </h1>
        <p className="text-base sm:text-lg font-body leading-relaxed text-muted-foreground">
          {t(
            'সূত্র ও তারিখসহ গন্তব্য গাইড, নিরাপত্তা সতর্কতা, জরুরি নম্বর আর মডারেশন করা ভ্রমণকারীর রিভিউ, বাংলায় ও ইংরেজিতে।',
            'Source-dated destination guides, safety advisories, emergency numbers and moderated traveller reviews, in Bangla and English.',
          )}
        </p>
      </section>

      {/* Reserve the selector's height while loading, so the page does not jump when it arrives. */}
      {destinationsLoading && (
        <div role="status" aria-busy="true" className="flex flex-col gap-3">
          <span className="text-sm font-bold text-on-surface-variant">{t('গন্তব্য লোড হচ্ছে…', 'Loading destinations…')}</span>
          <div className="h-[34rem] md:h-[26rem] rounded-2xl bg-muted motion-safe:animate-pulse" />
        </div>
      )}
      {!destinationsLoading && destinationsError != null && (
        <ErrorState error={destinationsError} onRetry={reloadDestinations} />
      )}
      {destinations && destinations.length > 0 && (
        <section aria-labelledby="landing-destinations" className="flex flex-col gap-3">
          <h2 id="landing-destinations" className="text-sm font-bold text-on-surface-variant dark:text-on-dark-muted">
            {t('গন্তব্য বেছে নিন', 'Pick a destination')}
          </h2>
          <InteractiveSelector
            label={t('গন্তব্যসমূহ', 'Destinations')}
            options={destinations.map((d): SelectorOption => {
              const image = destinationImage(d.name_en);
              return {
                id: d.id,
                title: pick(language, d.name_bn, d.name_en),
                description: pick(language, d.summary_bn, d.summary_en),
                icon: DESTINATION_ICON[d.name_en] ?? MapPin,
                image: image && { src: image.src, srcSmall: image.srcSmall, width: image.width, height: image.height, alt: image.alt[language] },
                action: (
                  <Link
                    to={`/destinations/${d.id}`}
                    className={buttonVariants({ variant: 'secondary', className: 'bg-white text-stone-900 hover:bg-white/90' })}
                  >
                    {t('গাইড দেখুন', 'Open guide')}
                    <ArrowRight size={16} aria-hidden="true" />
                  </Link>
                ),
                credit: image && <ImageCredit credit={image.credit} />,
              };
            })}
          />
        </section>
      )}

      <section aria-label={t('কীভাবে শুরু করবেন', 'How to start')} className="grid grid-cols-1 md:grid-cols-2 gap-5">
        <article className="tonal-card p-6 sm:p-8 flex flex-col gap-5 border-forest-primary/30 dark:border-neon-lime/30">
          <div className="flex flex-col gap-1">
            <h2 className="text-xl font-bold font-title text-on-surface dark:text-on-dark">{t('অতিথি হিসেবে দেখুন', 'Explore as a guest')}</h2>
            <p className="text-sm text-on-surface-variant dark:text-on-dark-muted">
              {t('কোনো অ্যাকাউন্ট বা ব্যক্তিগত তথ্য লাগবে না।', 'No account and no personal details needed.')}
            </p>
          </div>
          <CapabilityList items={GUEST} />
          {session.kind === 'member' && (
            <p className="text-xs text-on-surface-variant dark:text-on-dark-muted wrap-anywhere">
              {t(`আপনি ${session.displayName} হিসেবে সাইন ইন আছেন; অতিথি হতে আগে সাইন আউট করতে হবে।`, `You are signed in as ${session.displayName}; guest mode needs you to sign out first.`)}
            </p>
          )}
          <Link
            to="/guest"
            className={buttonVariants({ size: 'lg', className: 'mt-auto' })}
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
            className={buttonVariants({ variant: 'outline', size: 'lg', className: 'mt-auto' })}
          >
            <LogIn size={16} aria-hidden="true" />
            {t('সাইন ইন', 'Sign in')}
          </Link>
        </article>
      </section>

    </div>
  );
};
