import React from 'react';
import { NavLink } from 'react-router-dom';
import { 
  LayoutDashboard, 
  MapPin, 
  Calculator, 
  DownloadCloud, 
  Bookmark, 
  MessageSquareText, 
  HeartPulse, 
  Compass,
  Database
} from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ isOpen, onClose }) => {
  const { t } = useLanguage();

  const navItems = [
    {
      to: '/',
      labelBn: 'সারসংক্ষেপ',
      labelEn: 'Overview',
      icon: LayoutDashboard,
    },
    {
      to: '/destinations',
      labelBn: 'গন্তব্য ও গাইড',
      labelEn: 'Destinations',
      icon: MapPin,
    },
    {
      to: '/planner',
      labelBn: 'খরচ ক্যালকুলেটর',
      labelEn: 'Cost Planner',
      icon: Calculator,
    },
    {
      to: '/offline-packs',
      labelBn: 'অফলাইন প্যাক',
      labelEn: 'Offline Packs',
      icon: DownloadCloud,
    },
    {
      to: '/trips',
      labelBn: 'সংরক্ষিত ট্রিপ',
      labelEn: 'Saved Trips',
      icon: Bookmark,
    },
    {
      to: '/reviews',
      labelBn: 'রিভিউ ও ফিডব্যাক',
      labelEn: 'Reviews',
      icon: MessageSquareText,
    },
    {
      to: '/health',
      labelBn: 'সিস্টেম স্ট্যাটাস',
      labelEn: 'API Health',
      icon: HeartPulse,
    },
  ];

  return (
    <>
      {/* Mobile Backdrop */}
      {isOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-sm lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar Container */}
      <aside
        className={`fixed top-0 bottom-0 left-0 z-50 w-72 bg-surface-sage/70 dark:bg-dark-surface-1 border-r border-surface-muted/30 dark:border-dark-surface-2 flex flex-col justify-between py-6 px-4 transition-transform duration-300 ease-in-out lg:translate-x-0 ${
          isOpen ? 'translate-x-0' : '-translate-x-full'
        }`}
      >
        <div className="flex flex-col gap-6">
          {/* Logo Brand Header */}
          <div className="flex items-center gap-3 px-3 py-1">
            <div className="w-10 h-10 rounded-2xl bg-forest-primary dark:bg-neon-lime flex items-center justify-center text-white dark:text-dark-bg-base shadow-sm">
              <Compass size={24} />
            </div>
            <div className="flex flex-col">
              <span className="font-title font-bold text-xl text-forest-primary dark:text-neon-lime leading-tight">
                অভিযাত্রী
              </span>
              <span className="font-en text-[11px] font-semibold tracking-wider text-on-surface-variant dark:text-on-dark-muted uppercase">
                Abhijatri Companion
              </span>
            </div>
          </div>

          {/* Navigation Menu */}
          <nav className="flex flex-col gap-1.5">
            {navItems.map((item) => {
              const Icon = item.icon;
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  onClick={onClose}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3.5 py-2.5 rounded-xl font-medium text-sm transition-all ${
                      isActive
                        ? 'bg-forest-primary text-white dark:bg-neon-lime dark:text-dark-bg-base font-semibold shadow-sm'
                        : 'text-on-surface-variant dark:text-on-dark hover:bg-surface-container dark:hover:bg-dark-surface-2'
                    }`
                  }
                >
                  <Icon size={18} />
                  <span className="font-title text-[15px]">
                    {t(item.labelBn, item.labelEn)}
                  </span>
                </NavLink>
              );
            })}
          </nav>
        </div>

        {/* Bottom PWA & Cache Card */}
        <div className="p-3.5 rounded-xl bg-surface-container/80 dark:bg-dark-surface-2 border border-surface-muted/30 dark:border-dark-surface-2 flex flex-col gap-2">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Database size={15} className="text-forest-primary dark:text-emerald-accent" />
              <span className="font-en text-xs font-semibold text-on-surface dark:text-on-dark">
                IndexedDB Cache
              </span>
            </div>
            <span className="w-2 h-2 rounded-full bg-emerald-accent"></span>
          </div>
          <p className="text-[12px] text-on-surface-variant dark:text-on-dark-muted leading-tight">
            {t(
              'অফলাইন ট্রাভেল প্যাক ও ড্রাফট সংরক্ষিত রয়েছে।',
              'Offline packs & review drafts stored locally.'
            )}
          </p>
        </div>
      </aside>
    </>
  );
};
