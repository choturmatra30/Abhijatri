import { useCallback, useEffect, useRef, useState } from 'react';
import { StaffError, getSession, logout } from './api';
import { Audit } from './screens/Audit';
import { Decided } from './screens/Decided';
import { Enforcement } from './screens/Enforcement';
import { Inbox } from './screens/Inbox';
import { Media } from './screens/Media';
import { Notifications } from './screens/Notifications';
import { Monitor } from './screens/Monitor';
import { Queue } from './screens/Queue';
import { SignIn } from './screens/SignIn';
import { StaffRoles } from './screens/Staff';
import { Tours } from './screens/Tours';
import type { Lang, Session } from './types';
import { Notice, makeT } from './ui';

/** From this width the side menu sits beside the page; below it, it slides over the page. */
const WIDE = '(min-width: 960px)';

type View = 'queue' | 'inbox' | 'media' | 'decided' | 'enforcement' | 'tours' | 'audit' | 'staff' | 'monitor' | 'notifications';

/**
 * The staff shell. It shows only what the signed-in role may use, but that is a convenience: every
 * request is authorised again on the server (Moderation spec 2.1).
 */
export function App() {
  const [lang, setLang] = useState<Lang>('en');
  const [session, setSession] = useState<Session | null>(null);
  const [startupError, setStartupError] = useState<string | null>(null);
  const [view, setView] = useState<View>('queue');
  const t = makeT(lang);
  // The sections live in a side menu behind a hamburger button (owner request, 11 Nov 2026).
  // Wide screens start with it open beside the page; narrow screens start with it closed.
  const [wide, setWide] = useState(() => window.matchMedia(WIDE).matches);
  const [menuOpen, setMenuOpen] = useState(() => window.matchMedia(WIDE).matches);
  const menuButton = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLElement>(null);
  const overlay = menuOpen && !wide;

  useEffect(() => {
    const query = window.matchMedia(WIDE);
    const changed = () => {
      setWide(query.matches);
      setMenuOpen(query.matches);
    };
    query.addEventListener('change', changed);
    return () => query.removeEventListener('change', changed);
  }, []);

  const closeMenu = useCallback(() => setMenuOpen(false), []);

  // When the overlay closes, focus returns to the button that opened it. This runs after the page
  // behind the overlay is usable again; focusing earlier would fail while it is still inert.
  const wasOverlay = useRef(false);
  useEffect(() => {
    if (wasOverlay.current && !overlay) menuButton.current?.focus();
    wasOverlay.current = overlay;
  }, [overlay]);

  // As an overlay the menu takes the focus, and Escape closes it.
  useEffect(() => {
    if (!overlay) return;
    menu.current?.querySelector<HTMLElement>('[aria-current="page"]')?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeMenu();
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, [overlay, closeMenu]);

  useEffect(() => {
    getSession()
      .then(setSession)
      .catch((failure) => {
        setSession({ authenticated: false });
        setStartupError(failure instanceof StaffError && failure.code === 'NETWORK_ERROR' ? 'NETWORK' : null);
      });
  }, []);

  const signOut = useCallback(async () => {
    await logout().catch(() => undefined);
    setSession({ authenticated: false });
    setView('queue');
  }, []);

  if (session === null) return <p className="muted shell">{t('লোড হচ্ছে…', 'Loading…')}</p>;

  const ready = session.authenticated && session.role !== null && session.aal === 'aal2';
  if (!session.authenticated || !ready || session.role === null) {
    return (
      <>
        {startupError && (
          <div className="shell">
            <Notice tone="error">{t('API-তে পৌঁছানো যায়নি।', 'Could not reach the API.')}</Notice>
          </div>
        )}
        <SignIn lang={lang} session={session} onSession={setSession} />
        <div className="lang-corner">
          <button type="button" className="ghost" onClick={() => setLang(lang === 'en' ? 'bn' : 'en')}>
            {lang === 'en' ? 'বাংলা' : 'English'}
          </button>
        </div>
      </>
    );
  }

  const role = session.role;
  const tabs: { id: View; label: string; show: boolean }[] = [
    { id: 'queue', label: t('কাজের সারি', 'Queue'), show: true },
    { id: 'inbox', label: t('ইনবক্স', 'Inbox'), show: true },
    { id: 'media', label: t('ছবি ও ভিডিও', 'Media'), show: true },
    { id: 'decided', label: t('বাতিল ও লুকানো', 'Rejected & hidden'), show: true },
    { id: 'enforcement', label: t('এনফোর্সমেন্ট', 'Enforcement'), show: true },
    { id: 'tours', label: t('ট্যুর অপারেশনস', 'Tour Operations'), show: true },
    { id: 'audit', label: t('অডিট', 'Audit'), show: true },
    { id: 'monitor', label: t('পর্যবেক্ষণ', 'Monitoring'), show: true },
    { id: 'staff', label: t('স্টাফ', 'Staff'), show: role === 'superadmin' },
    { id: 'notifications', label: t('বিজ্ঞপ্তি ব্যবস্থা', 'Notifications'), show: role === 'superadmin' },
  ];
  const current = tabs.find((tab) => tab.id === view);
  const choose = (id: View) => {
    setView(id);
    if (!wide) closeMenu();
  };

  return (
    <div className={`layout${menuOpen && wide ? ' with-menu' : ''}`}>
      {menuOpen && (
        <>
          {overlay && <div className="menu-backdrop" onClick={closeMenu} aria-hidden="true" />}
          <nav id="staff-menu" ref={menu} className={`sidemenu${overlay ? ' overlay' : ''}`} aria-label={t('বিভাগ', 'Sections')}>
            <p className="sidemenu-title">{t('বিভাগ', 'Sections')}</p>
            <ul>
              {tabs
                .filter((tab) => tab.show)
                .map((tab) => (
                  <li key={tab.id}>
                    <button type="button" aria-current={view === tab.id ? 'page' : undefined} onClick={() => choose(tab.id)}>
                      {tab.label}
                    </button>
                  </li>
                ))}
            </ul>
          </nav>
        </>
      )}
      {/* Behind the overlay menu the page cannot be clicked or reached with Tab. */}
      <div className="shell" {...(overlay ? ({ inert: '' } as object) : {})}>
      <header className="topbar">
        <div className="row topbar-lead">
          <button
            type="button"
            ref={menuButton}
            className="ghost menu-button"
            aria-expanded={menuOpen}
            aria-controls="staff-menu"
            aria-label={menuOpen ? t('মেনু বন্ধ করুন', 'Close menu') : t('মেনু খুলুন', 'Open menu')}
            onClick={() => setMenuOpen((open) => !open)}
          >
            <span className="menu-icon" aria-hidden="true">
              <span />
              <span />
              <span />
            </span>
          </button>
          <div>
            <h1>
              {t('মডারেশন ড্যাশবোর্ড', 'Moderation dashboard')}
              {current && <span className="muted current-section"> · {current.label}</span>}
            </h1>
            <p className="muted small">
              {session.user.display_name} · <strong>{role}</strong> · {t('সব সিদ্ধান্ত অডিট লগে যায়।', 'every decision is audited.')}
            </p>
          </div>
        </div>
        <div className="row">
          <button type="button" className="ghost" onClick={() => setLang(lang === 'en' ? 'bn' : 'en')}>
            {lang === 'en' ? 'বাংলা' : 'English'}
          </button>
          <button type="button" className="ghost" onClick={() => void signOut()}>
            {t('সাইন আউট', 'Sign out')}
          </button>
        </div>
      </header>
      {view === 'queue' && <Queue lang={lang} role={role} userId={session.user.id} />}
      {view === 'inbox' && <Inbox lang={lang} />}
      {view === 'media' && <Media lang={lang} />}
      {view === 'notifications' && role === 'superadmin' && <Notifications lang={lang} />}
      {view === 'enforcement' && <Enforcement lang={lang} role={role} />}
      {view === 'tours' && <Tours lang={lang} role={role} />}
      {view === 'decided' && <Decided lang={lang} role={role} />}
      {view === 'audit' && <Audit lang={lang} role={role} />}
      {view === 'monitor' && <Monitor lang={lang} />}
      {view === 'staff' && role === 'superadmin' && <StaffRoles lang={lang} hasAuthenticator={session.mfa_factors.length > 0} />}
      </div>
    </div>
  );
}
