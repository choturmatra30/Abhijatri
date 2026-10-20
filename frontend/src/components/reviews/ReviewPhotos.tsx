import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { ImagePlus, Lock, Trash2 } from 'lucide-react';
import { useLanguage } from '../../context/LanguageContext';
import { useSession } from '../../context/SessionContext';
import {
  ACCEPTED_PHOTO_TYPES,
  ALT_TEXT_MAX,
  CAPTION_MAX,
  MAX_PHOTOS_PER_REVIEW,
  checkPhotoFiles,
  exceedsPixelLimit,
  type PhotoProblem,
} from '../../utils/reviewPhotos';

export interface ReviewPhoto {
  id: string;
  file: File;
  previewUrl: string;
  altText: string;
  caption: string;
  ownershipDeclared: boolean;
}

const PROBLEM_TEXT: Record<PhotoProblem, [string, string]> = {
  TYPE: ['শুধু JPEG, PNG বা WebP ছবি দেওয়া যাবে।', 'Only JPEG, PNG or WebP images are allowed.'],
  TOO_LARGE: ['প্রতিটি ছবি সর্বোচ্চ ৮ MiB হতে পারে।', 'Each photo can be at most 8 MiB.'],
  TOO_MANY: ['একটি রিভিউতে সর্বোচ্চ ৫টি ছবি।', 'A review can have at most 5 photos.'],
  TOO_MANY_PIXELS: ['ছবির রেজোলিউশন সর্বোচ্চ ২০ মেগাপিক্সেল।', 'Photo resolution can be at most 20 megapixels.'],
};

async function pixelCount(file: File): Promise<{ width: number; height: number } | null> {
  try {
    const bitmap = await createImageBitmap(file);
    const size = { width: bitmap.width, height: bitmap.height };
    bitmap.close();
    return size;
  } catch {
    return null; // undecodable here; the server decides
  }
}

/**
 * Photo attachment for reviews (Review.md 8, core scope since 20 Oct 2026). Guests write
 * text-only reviews, so they see why photos are unavailable. The upload itself goes through
 * `POST /reviews/{id}/media-intents` after the review is created (planned, R07).
 */
export const ReviewPhotos: React.FC<{
  photos: ReviewPhoto[];
  onChange: (next: ReviewPhoto[]) => void;
}> = ({ photos, onChange }) => {
  const { t } = useLanguage();
  const { isVerifiedMember } = useSession();
  const [problems, setProblems] = useState<string[]>([]);
  const latest = useRef(photos);
  latest.current = photos;

  // Release preview URLs when the component goes away.
  useEffect(() => () => latest.current.forEach((p) => URL.revokeObjectURL(p.previewUrl)), []);

  if (!isVerifiedMember) {
    return (
      <div className="p-4 rounded-xl border border-dashed border-surface-muted dark:border-dark-surface-2 flex gap-3 text-sm">
        <Lock size={18} className="shrink-0 mt-0.5 text-on-surface-variant dark:text-on-dark-muted" aria-hidden="true" />
        <div className="flex flex-col gap-1">
          <p className="font-semibold text-on-surface dark:text-on-dark">{t('ছবি শুধু যাচাইকৃত সদস্যদের জন্য', 'Photos are for Verified Members')}</p>
          <p className="text-xs text-on-surface-variant dark:text-on-dark-muted">
            {t(
              'অতিথি রিভিউ শুধু লেখায় হয়। ছবি যোগ করতে সাইন ইন করে যাচাইকৃত সদস্য হতে হবে।',
              'Guest reviews are text only. To add photos, sign in and become a Verified Member.',
            )}{' '}
            <Link to="/login" className="underline underline-offset-2 text-forest-primary dark:text-neon-lime">
              {t('সাইন ইন', 'Sign in')}
            </Link>
          </p>
        </div>
      </div>
    );
  }

  const addFiles = async (list: FileList | null) => {
    if (!list) return;
    const { accepted, rejected } = checkPhotoFiles(Array.from(list), photos.length);
    const messages = rejected.map(({ file, problem }) => `${file.name}: ${t(...PROBLEM_TEXT[problem])}`);
    const added: ReviewPhoto[] = [];
    for (const file of accepted) {
      const size = await pixelCount(file);
      if (size && exceedsPixelLimit(size.width, size.height)) {
        messages.push(`${file.name}: ${t(...PROBLEM_TEXT.TOO_MANY_PIXELS)}`);
        continue;
      }
      added.push({ id: crypto.randomUUID(), file, previewUrl: URL.createObjectURL(file), altText: '', caption: '', ownershipDeclared: false });
    }
    setProblems(messages);
    onChange([...photos, ...added]);
  };

  const update = (id: string, patch: Partial<ReviewPhoto>) =>
    onChange(photos.map((p) => (p.id === id ? { ...p, ...patch } : p)));
  const remove = (id: string) => {
    const photo = photos.find((p) => p.id === id);
    if (photo) URL.revokeObjectURL(photo.previewUrl);
    onChange(photos.filter((p) => p.id !== id));
  };

  return (
    <fieldset className="flex flex-col gap-3">
      <legend className="text-xs font-bold text-on-surface-variant dark:text-on-dark-muted">
        {t(`ছবি (ঐচ্ছিক, সর্বোচ্চ ${MAX_PHOTOS_PER_REVIEW}টি)`, `Photos (optional, up to ${MAX_PHOTOS_PER_REVIEW})`)}
      </legend>
      <p className="text-xs text-on-surface-variant dark:text-on-dark-muted -mt-1">
        {t(
          'ছবি থেকে অবস্থান ও ক্যামেরার তথ্য সরিয়ে ফেলা হয় এবং মডারেটর অনুমোদনের পর প্রকাশিত হয়। অন্যের মুখ বা ব্যক্তিগত তথ্য থাকলে ছবি দেবেন না।',
          'Location and camera data are removed and photos are published only after a moderator approves them. Do not upload photos showing other people’s faces or personal details.',
        )}
      </p>

      {photos.length < MAX_PHOTOS_PER_REVIEW && (
        <label className="self-start inline-flex items-center gap-2 min-h-[44px] px-4 rounded-full bg-surface-sage dark:bg-dark-surface-2 text-forest-primary dark:text-neon-lime text-xs font-bold font-title cursor-pointer">
          <ImagePlus size={16} aria-hidden="true" />
          {t('ছবি যোগ করুন', 'Add photos')}
          <input
            type="file"
            accept={ACCEPTED_PHOTO_TYPES.join(',')}
            multiple
            className="sr-only"
            onChange={(e) => {
              void addFiles(e.target.files);
              e.target.value = '';
            }}
          />
        </label>
      )}

      {problems.length > 0 && (
        <ul role="alert" className="text-xs text-error-alert dark:text-red-400 list-disc pl-5">
          {problems.map((message) => (
            <li key={message}>{message}</li>
          ))}
        </ul>
      )}

      <ul className="flex flex-col gap-3">
        {photos.map((photo, index) => (
          <li key={photo.id} className="flex gap-3 p-3 rounded-xl bg-surface-container/50 dark:bg-dark-surface-2">
            <img src={photo.previewUrl} alt="" className="w-24 h-24 object-cover rounded-lg shrink-0" />
            <div className="flex-1 flex flex-col gap-2">
              <label className="flex flex-col gap-1 text-xs font-bold text-on-surface-variant dark:text-on-dark-muted">
                {t(`ছবি ${index + 1}-এর বিবরণ (দৃষ্টিপ্রতিবন্ধীদের জন্য, আবশ্যক)`, `Describe photo ${index + 1} (for screen readers, required)`)}
                <input
                  value={photo.altText}
                  maxLength={ALT_TEXT_MAX}
                  onChange={(e) => update(photo.id, { altText: e.target.value })}
                  className="px-3 min-h-[40px] rounded-lg border border-surface-muted/50 dark:border-dark-surface-1 bg-white dark:bg-dark-surface-1 text-sm font-normal text-on-surface dark:text-on-dark"
                />
              </label>
              <label className="flex flex-col gap-1 text-xs font-bold text-on-surface-variant dark:text-on-dark-muted">
                {t('ক্যাপশন (ঐচ্ছিক)', 'Caption (optional)')}
                <input
                  value={photo.caption}
                  maxLength={CAPTION_MAX}
                  onChange={(e) => update(photo.id, { caption: e.target.value })}
                  className="px-3 min-h-[40px] rounded-lg border border-surface-muted/50 dark:border-dark-surface-1 bg-white dark:bg-dark-surface-1 text-sm font-normal text-on-surface dark:text-on-dark"
                />
              </label>
              <label className="flex items-start gap-2 text-xs text-on-surface dark:text-on-dark">
                <input
                  type="checkbox"
                  checked={photo.ownershipDeclared}
                  onChange={(e) => update(photo.id, { ownershipDeclared: e.target.checked })}
                  className="mt-0.5 h-4 w-4 accent-forest-primary dark:accent-neon-lime"
                />
                {t('ছবিটি আমি নিজে তুলেছি এবং প্রকাশের অধিকার আমার আছে।', 'I took this photo and have the right to publish it.')}
              </label>
            </div>
            <button
              type="button"
              onClick={() => remove(photo.id)}
              aria-label={t(`ছবি ${index + 1} সরান`, `Remove photo ${index + 1}`)}
              className="self-start min-w-[40px] min-h-[40px] flex items-center justify-center rounded-full text-red-700 dark:text-red-300 hover:bg-red-50 dark:hover:bg-red-950/40"
            >
              <Trash2 size={16} aria-hidden="true" />
            </button>
          </li>
        ))}
      </ul>
    </fieldset>
  );
};
