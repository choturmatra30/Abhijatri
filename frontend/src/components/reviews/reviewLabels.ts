import type { ComfortTier, ReviewCategory, ReviewLanguage, ReviewStatus, TravellerType } from '../../types';

type Pair = [bn: string, en: string];

/** Review.md 3.1 categories with a one-line prompt so ratings mean the same thing to everyone. */
export const CATEGORY_LABEL: Record<ReviewCategory, { name: Pair; prompt: Pair }> = {
  CLEANLINESS: {
    name: ['পরিচ্ছন্নতা', 'Cleanliness'],
    prompt: ['এলাকা, থাকার জায়গা ও শৌচাগার কতটা পরিষ্কার ছিল?', 'How clean were the area, stay and toilets?'],
  },
  ACCESSIBILITY: {
    name: ['প্রবেশযোগ্যতা', 'Accessibility'],
    prompt: ['শিশু, বয়স্ক বা চলাচলে অসুবিধা আছে এমন মানুষের জন্য যাওয়া কতটা সহজ?', 'How easy is it for children, older people or people with limited mobility?'],
  },
  HOSPITALITY: {
    name: ['আতিথেয়তা', 'Hospitality'],
    prompt: ['স্থানীয় মানুষ ও সেবাদাতাদের আচরণ কেমন ছিল?', 'How were you treated by locals and service providers?'],
  },
  FOOD: {
    name: ['খাবার', 'Food'],
    prompt: ['খাবারের মান ও বিকল্প কেমন ছিল?', 'How good were the food quality and choices?'],
  },
  TRANSPORT: {
    name: ['যাতায়াত', 'Transport'],
    prompt: ['যাওয়া-আসা ও স্থানীয় যানবাহন কতটা সহজ ও নির্ভরযোগ্য?', 'How easy and reliable were getting there and getting around?'],
  },
  SAFETY_PERCEPTION: {
    name: ['নিরাপত্তার অনুভূতি', 'Feeling of safety'],
    prompt: ['সেখানে আপনি কতটা নিরাপদ বোধ করেছেন?', 'How safe did you feel there?'],
  },
  VALUE: {
    name: ['খরচের মূল্য', 'Value for money'],
    prompt: ['খরচের তুলনায় অভিজ্ঞতা কেমন ছিল?', 'Was the experience worth what you paid?'],
  },
};

export const TRAVELLER_TYPES: [TravellerType, Pair][] = [
  ['SOLO', ['একা', 'Solo']],
  ['STUDENT', ['শিক্ষার্থী', 'Student']],
  ['COUPLE', ['দম্পতি', 'Couple']],
  ['FAMILY', ['পরিবার', 'Family']],
  ['GROUP', ['দল', 'Group']],
];

export const COMFORT_TIERS: [ComfortTier, Pair][] = [
  ['ECONOMY', ['সাশ্রয়ী', 'Economy']],
  ['STANDARD', ['স্ট্যান্ডার্ড', 'Standard']],
  ['PREMIUM', ['প্রিমিয়াম', 'Premium']],
];

export const REVIEW_LANGUAGES: [ReviewLanguage, Pair][] = [
  ['BN', ['বাংলা', 'Bangla']],
  ['EN', ['ইংরেজি', 'English']],
  ['MIXED', ['বাংলা-ইংরেজি মিশ্র', 'Mixed Bangla and English']],
];

export const STATUS_LABEL: Record<ReviewStatus, Pair> = {
  PENDING: ['মডারেশনের অপেক্ষায়', 'Waiting for moderation'],
  UNDER_REVIEW: ['মডারেশন চলছে', 'Being moderated'],
  CHANGES_REQUESTED: ['সংশোধন প্রয়োজন', 'Changes requested'],
  PUBLISHED: ['প্রকাশিত', 'Published'],
  HIDDEN: ['সাময়িকভাবে লুকানো', 'Hidden'],
  REJECTED: ['প্রত্যাখ্যাত', 'Rejected'],
  WITHDRAWN: ['প্রত্যাহার করা হয়েছে', 'Withdrawn'],
  DELETED: ['মুছে ফেলা হয়েছে', 'Deleted'],
};

/** Field-error codes from the API (errors.py _FIELD_CODES) as user-facing text. */
export const FIELD_ERROR_LABEL: Record<string, Pair> = {
  REQUIRED: ['এই ঘরটি পূরণ করুন।', 'This field is required.'],
  TOO_SHORT: ['লেখাটি খুব ছোট।', 'This is too short.'],
  TOO_LONG: ['লেখাটি খুব বড়।', 'This is too long.'],
  TOO_SMALL: ['মানটি খুব কম।', 'This value is too small.'],
  TOO_LARGE: ['মানটি খুব বেশি।', 'This value is too large.'],
  INVALID_DATE: ['তারিখটি সঠিক নয়।', 'This date is not valid.'],
  INVALID_UUID: ['নির্বাচনটি সঠিক নয়।', 'This selection is not valid.'],
  INVALID_VALUE: ['মানটি গ্রহণযোগ্য নয়।', 'This value is not accepted.'],
  UNKNOWN_FIELD: ['অপ্রত্যাশিত তথ্য পাঠানো হয়েছে।', 'An unexpected field was sent.'],
};
