import { Destination } from '../types';

/**
 * PROTOTYPE DATA ONLY. Not sourced, not real ratings. Used by screens whose backend does not exist yet
 * (cost planner E08, saved trips E09, offline packs R13). Real destination content comes from
 * GET /api/v1/destinations (see api/destinations.ts). Delete this file once those screens migrate.
 */
export const PROTOTYPE_DESTINATIONS: Destination[] = [
  {
    id: 'coxs-bazar',
    nameBn: "কক্সবাজার",
    nameEn: "Cox's Bazar",
    regionBn: "চট্টগ্রাম বিভাগ",
    regionEn: "Chattogram Division",
    coverImage: "https://images.unsplash.com/photo-1588668214407-6ea9a6d8c272?auto=format&fit=crop&w=1200&q=80",
    rating: 4.8,
    reviewCount: 342,
    descriptionBn: "বিশ্বের দীর্ঘতম প্রাকৃতিক বালুকাময় সমুদ্র সৈকত, মেরিন ড্রাইভ এবং ঐতিহ্যবাহী হিমছড়ি জলপ্রপাত।",
    descriptionEn: "The world's longest natural unbroken sea beach, scenic Marine Drive, and Himchari water trails.",
    seasonalityBn: "নভেম্বর - মার্চ (সেরা সময়), বর্ষায় উত্তাল সমুদ্রের রূপ",
    seasonalityEn: "November - March (Peak winter), Monsoon brings dramatic waves",
    activeAdvisoriesCount: 1,
    offlinePackSizeMb: 14.2,
    highlightsBn: ["সুগন্ধা ও লাবণী বিচ", "মেরিন ড্রাইভ রোড", "ইনানী প্রবাল দ্বীপ", "হিমছড়ি ঝরনা"],
    highlightsEn: ["Sugandha & Laboni Beach", "Marine Drive Road", "Inani Coral Beach", "Himchari National Park"]
  },
  {
    id: 'sajek-valley',
    nameBn: "সাজেক ভ্যালি",
    nameEn: "Sajek Valley",
    regionBn: "রাঙ্গামাটি (খাগড়াছড়ি প্রবেশদ্বার)",
    regionEn: "Rangamati (Gateway: Khagrachhari)",
    coverImage: "https://images.unsplash.com/photo-1544735716-392fe2489ffa?auto=format&fit=crop&w=1200&q=80",
    rating: 4.9,
    reviewCount: 428,
    descriptionBn: "মেঘের উপত্যকা নামে পরিচিত সাজেক, যেখানে পাহাড়ের চূড়া মেঘ ছুঁয়ে যায়। চান্দের গাড়িতে রোমাঞ্চকর পাহাড়ি যাত্রা।",
    descriptionEn: "The kingdom of clouds where mountain peaks meet mist. Scenic Chander Gari military escort convoys.",
    seasonalityBn: "সেপ্টেম্বর - ফেব্রুয়ারি (মেঘের মেলা), বর্ষাকালে সতেজ সবুজ পাহাড়",
    seasonalityEn: "September - February (Cloud sea season), lush greenery in monsoons",
    activeAdvisoriesCount: 2,
    offlinePackSizeMb: 18.5,
    highlightsBn: ["কংলাক পাহাড় চূড়া", "রুইলুই পাড়া", "হেলিপ্যাড সূর্যাস্ত", "আলুটিলা গুহা ও রিসাং ঝরনা"],
    highlightsEn: ["Konglak Peak", "Ruilui Para Cultural Trail", "Helipad Sunset Point", "Alutila Cave & Risang Falls"]
  },
  {
    id: 'sylhet',
    nameBn: "সিলেট ও শ্রীমঙ্গল",
    nameEn: "Sylhet & Sreemangal",
    regionBn: "সিলেট বিভাগ",
    regionEn: "Sylhet Division",
    coverImage: "https://images.unsplash.com/photo-1506744038136-46273834b3fb?auto=format&fit=crop&w=1200&q=80",
    rating: 4.7,
    reviewCount: 275,
    descriptionBn: "দুটি পাতা একটি কুঁড়ির সবুজ শ্যামল চা বাগান, স্বচ্ছ পানির বিছনাকান্দি এবং রত্নগর্ভা জাফলং ও রাতারগুল জলাবন।",
    descriptionEn: "Verdant rolling tea estates, freshwater crystal lagoons at Bisnakandi, Jaflong, and Ratargul swamp forest.",
    seasonalityBn: "বর্ষায় জলপ্রপাত ও হাওড় পূর্ণযৌবনা, শীতে আরামদায়ক আবহাওয়া",
    seasonalityEn: "Monsoon for active waterfalls & swamps, Winter for cool weather",
    activeAdvisoriesCount: 0,
    offlinePackSizeMb: 16.0,
    highlightsBn: ["রাতারগুল সোয়াম্প ফরেস্ট", "বিছনাকান্দি", "লাউয়াছড়া জাতীয় উদ্যান", "সাতরঙা চা"],
    highlightsEn: ["Ratargul Swamp Forest", "Bisnakandi Stream", "Lawachara Rain Forest", "Seven Layer Tea"]
  },
  {
    id: 'sundarbans',
    nameBn: "সুন্দরবন ম্যানগ্রোভ",
    nameEn: "Sundarbans Mangrove Forest",
    regionBn: "খুলনা ও বাগেরহাট",
    regionEn: "Khulna & Bagerhat",
    coverImage: "https://images.unsplash.com/photo-1518457607834-6e8d80c183c5?auto=format&fit=crop&w=1200&q=80",
    rating: 4.95,
    reviewCount: 198,
    descriptionBn: "ইউনেস্কো বিশ্ব ঐতিহ্য, রয়েল বেঙ্গল টাইগারের প্রাকৃতিক আবাসভূমি ও পৃথিবীর বৃহত্তম একক ম্যানগ্রোভ অরণ্য।",
    descriptionEn: "UNESCO World Heritage site, realm of the Royal Bengal Tiger, and world's largest mangrove wilderness.",
    seasonalityBn: "নভেম্বর - ফেব্রুয়ারি (নৌ-ভ্রমণ ও হরিণ-বাঘ দেখার সর্বোত্তম সময়)",
    seasonalityEn: "November - February (Safe river tides & prime wildlife viewing)",
    activeAdvisoriesCount: 1,
    offlinePackSizeMb: 22.0,
    highlightsBn: ["কটকা অভয়ারণ্য", "করমজল কুমির প্রজনন কেন্দ্র", "হিরণ পয়েন্ট", "দুর্লভ ম্যানগ্রোভ খাল ট্রিপ"],
    highlightsEn: ["Kotka Wildlife Sanctuary", "Karamjal Conservation Centre", "Hiron Point", "Tidal Creek Boat Cruises"]
  },
  {
    id: 'bandarban',
    nameBn: "বান্দরবান পার্বত্য জেলা",
    nameEn: "Bandarban Hill District",
    regionBn: "চট্টগ্রাম বিভাগ",
    regionEn: "Chattogram Division",
    coverImage: "https://images.unsplash.com/photo-1464822759023-fed622ff2c3b?auto=format&fit=crop&w=1200&q=80",
    rating: 4.85,
    reviewCount: 310,
    descriptionBn: "বাংলাদেশের উচ্চতম পর্বতশৃঙ্গ তাজিংডং ও কেওক্রাডং, নীলগিরির কুয়াশা এবং আদিবাসী সংস্কৃতির অপরূপ মিলনমেলা।",
    descriptionEn: "Highest peaks including Keokradong, clouds at Nilgiri, remote waterfalls, and indigenous cultural heritage.",
    seasonalityBn: "অক্টোবর - মার্চ ট্র্যাকিংয়ের উপযুক্ত, বর্ষায় রূপবতী শৈলপ্রপাত",
    seasonalityEn: "October - March prime for trekking, Monsoon for gushing falls",
    activeAdvisoriesCount: 2,
    offlinePackSizeMb: 19.8,
    highlightsBn: ["নীলগিরি হিল রিসোর্ট", "নাফাখুম জলপ্রপাত", "কেওক্রাডং ট্রেইল", "বগা লেক"],
    highlightsEn: ["Nilgiri Clouds Resort", "Nafakhum Waterfalls", "Keokradong Trekking Peak", "Boga Lake Enclave"]
  }
];
