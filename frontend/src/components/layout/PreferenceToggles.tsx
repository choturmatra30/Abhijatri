import React from 'react';
import { Languages, Moon, Sun } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { useTheme } from '../../context/ThemeContext';

/** Language (Bangla default) and theme switches, shared by the app navbar and public pages. */
export const PreferenceToggles: React.FC = () => {
  const { language, toggleLanguage, t } = useLanguage();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={toggleLanguage}
        lang={language === 'bn' ? 'en' : 'bn'}
        className="flex items-center gap-1 px-3 min-h-[36px] rounded-full bg-surface-sage dark:bg-dark-surface-1 text-forest-primary dark:text-neon-lime text-xs font-semibold hover:bg-surface-container dark:hover:bg-dark-surface-2 transition-colors"
        aria-label={t('ইংরেজিতে দেখুন', 'Switch to Bangla')}
      >
        <Languages size={14} aria-hidden="true" />
        <span>{language === 'bn' ? 'English' : 'বাংলা'}</span>
      </button>
      <button
        type="button"
        onClick={toggleTheme}
        className="p-2 rounded-full bg-surface-sage dark:bg-dark-surface-1 text-forest-primary dark:text-neon-lime hover:bg-surface-container dark:hover:bg-dark-surface-2 transition-colors"
        aria-label={theme === 'light' ? t('রাতের থিম', 'Switch to night theme') : t('দিনের থিম', 'Switch to day theme')}
      >
        {theme === 'light' ? <Moon size={16} aria-hidden="true" /> : <Sun size={16} aria-hidden="true" />}
      </button>
    </div>
  );
};
