import React from 'react';
import { Languages, Moon, Sun } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { useTheme } from '../../context/ThemeContext';
import { buttonVariants } from '@/components/ui/button';

/**
 * Language (Bangla default) and theme switches, shared by the app navbar and public pages.
 * The language button's accessible name is its visible word ("English" / "বাংলা"), tagged with that
 * word's language, so speech and screen readers match what is on screen (WCAG 2.5.3; U11).
 */
export const PreferenceToggles: React.FC = () => {
  const { language, toggleLanguage, t } = useLanguage();
  const { theme, toggleTheme } = useTheme();

  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={toggleLanguage}
        lang={language === 'bn' ? 'en' : 'bn'}
        className={buttonVariants({ variant: 'secondary', size: 'sm', className: 'min-h-11 gap-1.5' })}
      >
        <Languages size={14} aria-hidden="true" />
        <span>{language === 'bn' ? 'English' : 'বাংলা'}</span>
      </button>
      <button
        type="button"
        onClick={toggleTheme}
        className={buttonVariants({ variant: 'secondary', size: 'icon' })}
        aria-label={theme === 'light' ? t('রাতের থিম', 'Switch to night theme') : t('দিনের থিম', 'Switch to day theme')}
      >
        {theme === 'light' ? <Moon size={16} aria-hidden="true" /> : <Sun size={16} aria-hidden="true" />}
      </button>
    </div>
  );
};
