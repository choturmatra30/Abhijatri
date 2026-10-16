export type Language = 'bn' | 'en';
export type Theme = 'light' | 'dark';

export interface Destination {
  id: string;
  nameBn: string;
  nameEn: string;
  regionBn: string;
  regionEn: string;
  coverImage: string;
  rating: number;
  reviewCount: number;
  descriptionBn: string;
  descriptionEn: string;
  seasonalityBn: string;
  seasonalityEn: string;
  activeAdvisoriesCount: number;
  offlinePackSizeMb: number;
  highlightsBn: string[];
  highlightsEn: string[];
}

export interface CostEstimateItem {
  category: string;
  unit: string;
  quantity: number;
  low: number;
  expected: number;
  high: number;
  confidence: number;
}

export interface CostEstimateResult {
  destination: string;
  partySize: number;
  durationDays: number;
  durationNights: number;
  comfortTier: 'economy' | 'standard' | 'premium';
  items: CostEstimateItem[];
  totalExpected: number;
  perPersonExpected: number;
  sharedTotal: number;
  individualTotal: number;
  overallConfidence: 'High' | 'Medium' | 'Low';
}

export interface HealthStatus {
  status: string;
  database?: string;
  latencyMs?: number;
  timestamp?: string;
  urlChecked?: string;
  error?: string;
}
