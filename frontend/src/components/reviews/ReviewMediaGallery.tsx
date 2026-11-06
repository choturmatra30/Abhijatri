import React, { useState } from 'react';
import { ImageOff, Images, PlayCircle } from 'lucide-react';
import { useImagePolicy } from '../../hooks/useNetworkState';
import { useLanguage } from '../../context/LanguageContext';
import type { PublicMedia } from '../../types';

function duration(ms: number | null): string | null {
  if (ms === null) return null;
  const seconds = Math.round(ms / 1000);
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
}

/**
 * Approved photos and video of a published review (Review.md 7.4 and 8). Photos load lazily; the
 * video never autoplays and downloads nothing until the reader presses play.
 * Offline, media is replaced by a note: the links are short-lived signed URLs and the service worker
 * never caches user media (PF 18.1). With Data Saver or a 2G/3G connection, media loads only when the
 * reader asks for it (PF 19.3, no eager user media).
 */
export const ReviewMediaGallery: React.FC<{ media?: PublicMedia[] }> = ({ media }) => {
  const { t } = useLanguage();
  const policy = useImagePolicy();
  const [requested, setRequested] = useState(false);
  if (!media || media.length === 0) return null;
  const photos = media.filter((m) => m.kind === 'image');
  const videos = media.filter((m) => m.kind === 'video');

  if (policy === 'none') {
    return (
      <p className="inline-flex items-center gap-1.5 text-xs text-on-surface-variant dark:text-on-dark-muted">
        <ImageOff size={14} aria-hidden="true" />
        {t(`${media.length}টি ছবি বা ভিডিও ইন্টারনেট সংযোগ ফিরলে দেখা যাবে`, `${media.length} photo or video item(s) will show when you are back online`)}
      </p>
    );
  }
  if (policy === 'small' && !requested) {
    return (
      <button
        type="button"
        onClick={() => setRequested(true)}
        className="self-start inline-flex items-center gap-1.5 min-h-11 px-3 rounded-full border border-border text-xs font-semibold text-on-surface dark:text-on-dark hover:bg-muted"
      >
        <Images size={14} aria-hidden="true" />
        {t(`${media.length}টি ছবি বা ভিডিও দেখুন (ডেটা লাগবে)`, `Show ${media.length} photo or video item(s) (uses data)`)}
      </button>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      {photos.length > 0 && (
        <ul className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {photos.map((photo) => (
            <li key={photo.id}>
              <figure className="flex flex-col gap-1">
                <a href={photo.url} target="_blank" rel="noopener noreferrer" className="block rounded-lg overflow-hidden bg-surface-container dark:bg-dark-surface-2">
                  <img
                    src={photo.url}
                    alt={photo.alt_text}
                    loading="lazy"
                    decoding="async"
                    width={photo.width ?? undefined}
                    height={photo.height ?? undefined}
                    className="w-full aspect-4/3 object-cover"
                  />
                </a>
                {photo.caption && <figcaption className="text-[11px] text-on-surface-variant dark:text-on-dark-muted">{photo.caption}</figcaption>}
              </figure>
            </li>
          ))}
        </ul>
      )}
      {videos.map((video) => (
        <figure key={video.id} className="flex flex-col gap-1">
          <video
            src={video.url}
            controls
            preload="none"
            playsInline
            aria-label={video.alt_text}
            className="w-full max-h-80 rounded-lg bg-black"
          />
          <figcaption className="inline-flex items-center gap-1 text-[11px] text-on-surface-variant dark:text-on-dark-muted">
            <PlayCircle size={12} aria-hidden="true" />
            {t('ভিডিও', 'Video')}
            {duration(video.duration_ms) && ` · ${duration(video.duration_ms)}`}
            {video.caption && ` · ${video.caption}`}
          </figcaption>
        </figure>
      ))}
    </div>
  );
};
