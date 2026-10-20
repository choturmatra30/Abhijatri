import { describe, expect, it } from 'vitest';
import {
  MAX_PHOTO_BYTES,
  checkPhotoFiles,
  exceedsPixelLimit,
  photoMetadataComplete,
} from './reviewPhotos';

const file = (name: string, type: string, size = 1024) => ({ name, type, size });

describe('checkPhotoFiles (Review.md 8)', () => {
  it('accepts JPEG, PNG and WebP', () => {
    const { accepted, rejected } = checkPhotoFiles(
      [file('a.jpg', 'image/jpeg'), file('b.png', 'image/png'), file('c.webp', 'image/webp')],
      0,
    );
    expect(accepted.map((f) => f.name)).toEqual(['a.jpg', 'b.png', 'c.webp']);
    expect(rejected).toEqual([]);
  });

  it('rejects SVG, GIF, video and archives', () => {
    const { accepted, rejected } = checkPhotoFiles(
      [file('x.svg', 'image/svg+xml'), file('y.gif', 'image/gif'), file('z.mp4', 'video/mp4'), file('w.zip', 'application/zip')],
      0,
    );
    expect(accepted).toEqual([]);
    expect(rejected.map((r) => r.problem)).toEqual(['TYPE', 'TYPE', 'TYPE', 'TYPE']);
  });

  it('rejects files over 8 MiB and accepts exactly 8 MiB', () => {
    const { accepted, rejected } = checkPhotoFiles(
      [file('ok.jpg', 'image/jpeg', MAX_PHOTO_BYTES), file('big.jpg', 'image/jpeg', MAX_PHOTO_BYTES + 1)],
      0,
    );
    expect(accepted.map((f) => f.name)).toEqual(['ok.jpg']);
    expect(rejected).toEqual([{ file: expect.objectContaining({ name: 'big.jpg' }), problem: 'TOO_LARGE' }]);
  });

  it('caps a review at five photos, counting ones already attached', () => {
    const many = Array.from({ length: 4 }, (_, i) => file(`${i}.jpg`, 'image/jpeg'));
    const { accepted, rejected } = checkPhotoFiles(many, 2);
    expect(accepted).toHaveLength(3);
    expect(rejected.map((r) => r.problem)).toEqual(['TOO_MANY']);
  });
});

describe('pixel limit', () => {
  it('allows 20 megapixels and rejects more', () => {
    expect(exceedsPixelLimit(5000, 4000)).toBe(false);
    expect(exceedsPixelLimit(5001, 4000)).toBe(true);
  });
});

describe('photo metadata', () => {
  it('needs alt text and the ownership declaration', () => {
    expect(photoMetadataComplete({ altText: 'Clouds over Konglak', ownershipDeclared: true })).toBe(true);
    expect(photoMetadataComplete({ altText: '   ', ownershipDeclared: true })).toBe(false);
    expect(photoMetadataComplete({ altText: 'Clouds', ownershipDeclared: false })).toBe(false);
  });
});
