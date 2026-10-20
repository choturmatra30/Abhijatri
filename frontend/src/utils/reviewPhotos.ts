/**
 * Client-side checks for Verified Member review photos (Review.md 8, amended 20 Oct 2026).
 *
 * These checks only give fast feedback. Browser metadata and MIME types are untrusted: the
 * server and the media worker re-validate the file signature, size and decoded resolution,
 * strip metadata and re-encode before anything is published (Security.md 8).
 */

export const MAX_PHOTOS_PER_REVIEW = 5;
export const MAX_PHOTO_BYTES = 8 * 1024 * 1024; // 8 MiB
export const MAX_PHOTO_PIXELS = 20_000_000; // 20 megapixels
export const ACCEPTED_PHOTO_TYPES = ['image/jpeg', 'image/png', 'image/webp'] as const;
export const ALT_TEXT_MAX = 250;
export const CAPTION_MAX = 300;

export type PhotoProblem = 'TYPE' | 'TOO_LARGE' | 'TOO_MANY' | 'TOO_MANY_PIXELS';

export interface PhotoCandidate {
  name: string;
  type: string;
  size: number;
}

export interface PhotoCheck<T extends PhotoCandidate> {
  accepted: T[];
  rejected: { file: T; problem: PhotoProblem }[];
}

/** Splits newly chosen files into accepted and rejected, respecting the per-review limit. */
export function checkPhotoFiles<T extends PhotoCandidate>(files: T[], alreadyAttached: number): PhotoCheck<T> {
  const result: PhotoCheck<T> = { accepted: [], rejected: [] };
  for (const file of files) {
    if (!(ACCEPTED_PHOTO_TYPES as readonly string[]).includes(file.type)) {
      result.rejected.push({ file, problem: 'TYPE' });
    } else if (file.size > MAX_PHOTO_BYTES) {
      result.rejected.push({ file, problem: 'TOO_LARGE' });
    } else if (alreadyAttached + result.accepted.length >= MAX_PHOTOS_PER_REVIEW) {
      result.rejected.push({ file, problem: 'TOO_MANY' });
    } else {
      result.accepted.push(file);
    }
  }
  return result;
}

export function exceedsPixelLimit(width: number, height: number): boolean {
  return width * height > MAX_PHOTO_PIXELS;
}

/** Every attached photo needs alt text (PF 20) and the uploader's ownership declaration. */
export function photoMetadataComplete(photo: { altText: string; ownershipDeclared: boolean }): boolean {
  const alt = photo.altText.trim();
  return alt.length > 0 && alt.length <= ALT_TEXT_MAX && photo.ownershipDeclared;
}
