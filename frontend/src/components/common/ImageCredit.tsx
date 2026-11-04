import React from 'react';
import { useLanguage } from '../../context/LanguageContext';
import type { DestinationImage } from '../../data/destinationImages';

/**
 * Attribution for a Creative Commons photo: author (linked to the source), licence (linked) and
 * the change we made. CC BY and BY-SA require all of these wherever the photo is shown.
 */
export const ImageCredit: React.FC<{ credit: DestinationImage['credit'] }> = ({ credit }) => {
  const { t } = useLanguage();
  return (
    <span>
      {t('ছবি', 'Photo')}:{' '}
      <a lang="en" href={credit.source} target="_blank" rel="noopener noreferrer" className="underline underline-offset-2 hover:text-white">
        {credit.author}
      </a>
      {' · '}
      <a lang="en" href={credit.licenceUrl} target="_blank" rel="noopener noreferrer license" className="underline underline-offset-2 hover:text-white">
        {credit.licence}
      </a>
      {' · '}
      {t('আকার পরিবর্তিত', 'resized')}
    </span>
  );
};
