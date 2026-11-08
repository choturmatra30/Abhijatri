/** Typed client for Verified Members' Tours and TourMates workspace. */
import { call } from './auth';

export interface TourAccess { access: boolean; reason: string | null; restricted?: boolean; features?: string[] }
export interface MatchScore { score: number | null; factors_used: number; factors_total: number; reasons: { part: string; bn: string; en: string }[] }
export interface TourCard {
  public_id: string; title: string; lifecycle: string; recruitment: string; is_at_risk: boolean; suspended: boolean;
  labels: string[]; policy: string; destinations: { id: string; name_bn: string; name_en: string }[];
  start_date: string; end_date: string; recruit_deadline: string;
  members: { approved: number; minimum: number; maximum: number };
  budget: { min: number | null; max: number | null }; style: string | null; pace: string | null;
  activities: string[]; departure_city: string | null; match?: MatchScore;
}
export interface TourMemberView { member_id: string | null; name: string; first_name: string; role: string; state: string; verified: boolean; seats: number; is_you: boolean }
export interface JoinRequestView { id: string; first_name: string; answer: string | null; message: string | null; seats: number; match: MatchScore; can_be_approved: boolean; problem: string | null; public_id?: string; title?: string }
export interface TourWorkspace extends TourCard {
  open_to_you: boolean; description: string | null; rules: string[]; custom_rules: string[]; join_question: string | null;
  transport: string | null; budget_includes: string[]; meeting_area: string | null; members_list: TourMemberView[];
  is_member: boolean; your_role: string | null; your_member_id: string; your_state: string; your_request: { id: string; state: string } | null;
  can_request: boolean; request_blocker: string | null; version: number; code: string | null; private_link: string | null;
  confirmed_at: string | null; modules: Record<'overview' | 'tourmates' | 'itinerary' | 'discussion' | 'budget' | 'safety', boolean>;
  permissions: string[]; pending_requests?: JoinRequestView[]; pending_invitations?: { id: string; name: string; expires_at: string }[];
}
export interface TourDashboard {
  alerts: { kind: string; public_id: string; title: string; count?: number }[]; my_tours: TourCard[]; drafts: TourCard[];
  requests: { sent: { id: string; state: string; public_id: string; title: string; created_at: string }[]; to_review: JoinRequestView[] };
  invitations: TourInvitation[]; suggested: TourCard[]; preferences_completion: number; discoverable: boolean;
}
export interface TourInvitation { id: string; expires_at: string; from: string; tour: TourCard }
export interface ChatMessage { seq: number; id: string; client_msg_id: string | null; kind: string; sender: string | null; is_you: boolean; body: string | null; status: string; edited: boolean; pinned: boolean; collapsed: boolean; seen_by: number; created_at: string }
export interface ChatView { items: ChatMessage[]; last_seq: number; writable: boolean; muted: boolean; last_read_seq: number }
export interface ItineraryView { days: number; start_date: string; can_edit: boolean; items: { id: string; day: number; position: number; kind: string; title: string; starts_at: string | null; notes: string | null }[] }
export interface BudgetView {
  planned: { min_bdt: number | null; max_bdt: number | null; includes: string[] }; total_paisa: number;
  expenses: { id: string; description: string; category: string; amount_paisa: number; paid_by_name: string; settled: boolean }[];
  balances: { user_id: string; name: string; net_paisa: number }[];
  transfers: { from: string; to: string; from_name: string; to_name: string; amount_paisa: number; is_from_you: boolean }[];
  notice: { bn: string; en: string };
}
export interface SafetyView {
  lifecycle: string; mine: { contact: { name: string; relationship: string; phone: string } | null; medical_notes: string | null; required_by: string };
  members: { member_id: string; name: string; role: string; has_contact: boolean }[]; reveal_open: boolean;
  meeting_points: { id: string; title: string; meet_at: string | null; map_url: string | null; notes: string | null }[];
  checkins: { id: string; message: string; created_at: string; you_answered: boolean; answered: number; total: number; not_answered: string[] }[];
  sos: { contacts: { name_bn: string; name_en: string; phone: string; kind: string }[]; active: boolean }; can_manage: boolean;
}

const query = (path: string, values: Record<string, string | number | null | undefined>) => {
  const params = new URLSearchParams();
  Object.entries(values).forEach(([key, value]) => { if (value !== null && value !== undefined && value !== '') params.set(key, String(value)); });
  return `${path}${params.size ? `?${params}` : ''}`;
};
const write = <T>(path: string, body: unknown = {}) => call<T>(path, { body, session: true, idempotencyKey: crypto.randomUUID() });

export const getTourAccess = () => call<TourAccess>('/api/v1/tours/access', { method: 'GET' });
export const getTourDashboard = () => call<TourDashboard>('/api/v1/me/tours', { method: 'GET' });
export const findTours = (filters: Record<string, string>) => call<{ items: TourCard[]; total: number; next_offset: number | null; preferences_completion: number }>(query('/api/v1/tours/search', filters), { method: 'GET' });
export const findPeople = (filters: Record<string, string>) => call<{ items: { user_id: string; first_name: string; age_band: string; division: string; languages: string[]; style: string | null; pace: string | null; destinations: string[]; completed_tours: number; match: MatchScore | null }[] }>(query('/api/v1/people/search', filters), { method: 'GET' });
export const getTourByCode = (code: string) => call<TourWorkspace>(`/api/v1/tours/by-code/${encodeURIComponent(code)}`, { method: 'GET' });
export const getTourSummary = (id: string) => call<TourWorkspace>(`/api/v1/tours/${encodeURIComponent(id)}/summary`, { method: 'GET' });
export const getTourWorkspace = (id: string) => call<TourWorkspace>(`/api/v1/tours/${encodeURIComponent(id)}`, { method: 'GET' });
export const createTour = (body: Record<string, unknown>) => write<TourWorkspace>('/api/v1/tours', body);
export const editTour = (id: string, version: number, body: Record<string, unknown>) => call<TourWorkspace>(`/api/v1/tours/${id}`, { method: 'PATCH', body, session: true, headers: { 'If-Match': String(version) } });
export const publishTour = (id: string) => write<TourWorkspace>(`/api/v1/tours/${id}/publish`, { accept_rules: true });
export const requestToJoin = (id: string, body: Record<string, unknown>) => write<{ id: string; state: string }>(`/api/v1/tours/${id}/requests`, body);
export const withdrawJoinRequest = (id: string) => call(`/api/v1/me/requests/${id}`, { method: 'DELETE', session: true });
export const approveJoinRequest = (tour: string, request: string) => write(`/api/v1/tours/${tour}/requests/${request}/approve`);
export const declineJoinRequest = (tour: string, request: string, reason_code = 'OTHER') => write(`/api/v1/tours/${tour}/requests/${request}/decline`, { reason_code });
export const leaveTour = (id: string, safe_checkout = false) => write(`/api/v1/tours/${id}/leave`, { safe_checkout });
export const setMemberRole = (tour: string, member: string, role: string) => write(`/api/v1/tours/${tour}/members/${member}/role`, { role });
export const removeTourMember = (tour: string, member: string) => write(`/api/v1/tours/${tour}/members/${member}/remove`, { reason_code: 'OTHER' });
export const regenerateTourCode = (id: string) => write<{ code: string; version: number }>(`/api/v1/tours/${id}/code/regenerate`);
export const cancelTour = (id: string, reason: string) => write(`/api/v1/tours/${id}/cancel`, { reason });

export const getTravelPreferences = () => call<Record<string, unknown>>('/api/v1/me/travel-preferences', { method: 'GET' });
export const saveTravelPreferences = (body: Record<string, unknown>) => call<Record<string, unknown>>('/api/v1/me/travel-preferences', { method: 'PUT', body, session: true });
export const saveDiscovery = (discoverable: boolean, audience: string) => call('/api/v1/me/discovery', { method: 'PUT', body: { discoverable, audience }, session: true });
export const invitePerson = (tour: string, invitee_id: string) => write(`/api/v1/tours/${tour}/invitations`, { invitee_id });
export const acceptInvitation = (id: string) => write(`/api/v1/me/invitations/${id}/accept`);
export const declineInvitation = (id: string, dont_invite_again = false) => write(`/api/v1/me/invitations/${id}/decline`, { dont_invite_again });

export const getItinerary = (id: string) => call<ItineraryView>(`/api/v1/tours/${id}/itinerary`, { method: 'GET' });
export const saveItinerary = (id: string, items: Record<string, unknown>[]) => call<ItineraryView>(`/api/v1/tours/${id}/itinerary`, { method: 'PUT', body: { items }, session: true });
export const getBudget = (id: string) => call<BudgetView>(`/api/v1/tours/${id}/budget`, { method: 'GET' });
export const addExpense = (id: string, body: Record<string, unknown>) => write<BudgetView>(`/api/v1/tours/${id}/expenses`, body);
export const settleExpense = (id: string, to_user: string, amount_paisa: number) => write<BudgetView>(`/api/v1/tours/${id}/settlements`, { to_user, amount_paisa });
export const getSafety = (id: string) => call<SafetyView>(`/api/v1/tours/${id}/safety`, { method: 'GET' });
export const saveSafety = (id: string, body: Record<string, unknown>) => call<SafetyView>(`/api/v1/tours/${id}/safety/me`, { method: 'PUT', body, session: true });
export const addMeetingPoint = (id: string, body: Record<string, unknown>) => write<SafetyView>(`/api/v1/tours/${id}/safety/meeting-points`, body);
export const requestCheckin = (id: string, message: string) => write<SafetyView>(`/api/v1/tours/${id}/checkins`, { message });
export const answerCheckin = (tour: string, id: string) => write<SafetyView>(`/api/v1/tours/${tour}/checkins/${id}/answer`);
export const raiseSos = (id: string, message: string) => write<SafetyView>(`/api/v1/tours/${id}/sos`, { message });
export const getMessages = (id: string, after = 0) => call<ChatView>(`/api/v1/tours/${id}/messages?after_seq=${after}`, { method: 'GET' });
export const postMessage = (id: string, body: string, client_msg_id: string = crypto.randomUUID()) => write<{ seq: number; duplicate: boolean; message: ChatMessage }>(`/api/v1/tours/${id}/messages`, { body, client_msg_id });
export const markMessagesRead = (id: string, seq: number) => write(`/api/v1/tours/${id}/messages/read`, { seq });
export const reportTour = (id: string, details: string) => write(`/api/v1/tours/${id}/reports`, { subject_kind: 'TOUR', reason_code: 'OTHER', details });
