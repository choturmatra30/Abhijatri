import React from 'react';
import { ExternalLink } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import type { Provenance } from '../../types';
import { formatCalendarDate } from '../../utils/format';

/** Source, publisher and verification date for one record (Platform Foundation 17). */
export const ProvenanceNote: React.FC<{ provenance: Provenance }> = ({ provenance }) => {
  const { language, t } = useLanguage();
  return (
    <p className="text-[11px] text-on-surface-variant dark:text-on-dark-muted flex flex-wrap items-center gap-x-2 gap-y-1">
      <a
        href={provenance.source_ref}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 underline underline-offset-2 hover:text-forest-primary dark:hover:text-neon-lime"
      >
        {t('সূত্র', 'Source')}: {provenance.publisher}
        <ExternalLink size={11} aria-hidden="true" />
      </a>
      <span aria-hidden="true">•</span>
      <span>
        {t('যাচাই', 'Verified')}: {formatCalendarDate(provenance.verified_on, language)}
      </span>
    </p>
  );
};
