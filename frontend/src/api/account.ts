/** Member verification, appeals and notification API. */

import type {
  AppNotification,
  AppealView,
  AppealableDecision,
  NotificationPreferences,
  VerificationCaseView,
  VerificationEvidenceKind,
  VerificationMine,
  VerificationStep,
} from '../types';
import { API_BASE_URL } from './client';
import { call } from './auth';

export const getMyVerification = () => call<VerificationMine>('/api/v1/verifications/mine', { method: 'GET' });
export const getVerificationDistricts = () =>
  call<{ divisions: { division: string; districts: string[] }[] }>('/api/v1/verifications/districts', { method: 'GET' });
export const getVerificationInstitutions = (query = '') =>
  call<{ items: { id: string; name_en: string; name_bn: string | null; kind: string }[] }>(
    `/api/v1/verifications/institutions${query ? `?q=${encodeURIComponent(query)}` : ''}`,
    { method: 'GET' },
  );

export const requestVerification = (purpose: 'initial' | 'renewal' | 'student_update' = 'initial') =>
  call<VerificationCaseView>('/api/v1/verifications', { body: { purpose }, session: true });
export const saveVerificationStep = (caseId: string, step: VerificationStep, body: Record<string, unknown>) =>
  call<VerificationCaseView>(`/api/v1/verifications/${caseId}/steps/${step}`, { method: 'PATCH', body, session: true });
export const sendVerificationPhoneCode = (caseId: string, phone: string) =>
  call<{ sent_to: string; expires_in: number; verified?: boolean }>(`/api/v1/verifications/${caseId}/phone/send-code`, { body: { phone }, session: true });
export const verifyVerificationPhoneCode = (caseId: string, code: string) =>
  call<VerificationCaseView>(`/api/v1/verifications/${caseId}/phone/verify`, { body: { code }, session: true });
export const sendStudentEmailCode = (caseId: string, email: string) =>
  call<{ sent: boolean; expires_in: number }>(`/api/v1/verifications/${caseId}/student-email/send-code`, { body: { email }, session: true });
export const verifyStudentEmailCode = (caseId: string, code: string) =>
  call<VerificationCaseView>(`/api/v1/verifications/${caseId}/student-email/verify`, { body: { code }, session: true });
export const issueLivenessChallenge = (caseId: string) =>
  call<NonNullable<VerificationCaseView['liveness']>>(`/api/v1/verifications/${caseId}/liveness-challenge`, { session: true });
export const submitVerification = (caseId: string, declaration: boolean, turnstileToken?: string) =>
  call<VerificationCaseView>(`/api/v1/verifications/${caseId}/submit`, {
    body: { declaration, turnstile_token: turnstileToken }, session: true, idempotencyKey: crypto.randomUUID(),
  });
export const respondToVerification = (caseId: string) =>
  call<VerificationCaseView>(`/api/v1/verifications/${caseId}/respond`, { body: {}, session: true, idempotencyKey: crypto.randomUUID() });
export const withdrawVerification = (caseId: string) =>
  call<VerificationCaseView>(`/api/v1/verifications/${caseId}/withdraw`, { body: {}, session: true, idempotencyKey: crypto.randomUUID() });

export const EVIDENCE_TYPES = ['image/jpeg', 'image/png'];
export const EVIDENCE_MAX_BYTES = 8 * 1024 * 1024;

/** Uploads to quarantine, then asks the API to validate, normalise and seal the image. */
export async function uploadEvidence(caseId: string, kind: VerificationEvidenceKind, file: File | Blob): Promise<void> {
  const contentType = file.type || 'image/jpeg';
  const intent = await call<{ evidence_id: string; upload_url: string }>(`/api/v1/verifications/${caseId}/evidence`, {
    body: { kind, content_type: contentType, size_bytes: file.size }, session: true,
  });
  const put = await fetch(intent.upload_url, { method: 'PUT', body: file, headers: { 'Content-Type': contentType } });
  if (!put.ok) throw new Error(`upload failed (${put.status})`);
  await call(`/api/v1/verifications/${caseId}/evidence/${intent.evidence_id}/complete`, { body: {}, session: true });
}

export const getMyAppeals = () => call<{ appeals: AppealView[]; appealable: AppealableDecision[] }>('/api/v1/appeals/mine', { method: 'GET' });
export const submitAppeal = (targetType: AppealableDecision['target_type'], targetId: string, reason: string) =>
  call<AppealView>('/api/v1/appeals', { body: { target_type: targetType, target_id: targetId, reason }, session: true });
export const withdrawAppeal = (appealId: string) => call<AppealView>(`/api/v1/appeals/${appealId}/withdraw`, { session: true });

export interface NotificationPage { items: AppNotification[]; next_cursor: string | null; unread: number }
export function notificationsQuery(options: { cursor?: string | null; archived?: boolean; unreadOnly?: boolean; limit?: number } = {}): string {
  const params = new URLSearchParams({ limit: String(options.limit ?? 20) });
  if (options.cursor) params.set('cursor', options.cursor);
  if (options.archived) params.set('archived', 'true');
  if (options.unreadOnly) params.set('unread_only', 'true');
  return `/api/v1/notifications?${params.toString()}`;
}
export const getNotifications = (options: Parameters<typeof notificationsQuery>[0] = {}) => call<NotificationPage>(notificationsQuery(options), { method: 'GET' });
export const getUnreadCount = () => call<{ unread: number }>('/api/v1/notifications/unread-count', { method: 'GET' });
export const updateNotification = (id: string, change: { read?: boolean; archived?: boolean }) =>
  call<AppNotification & { unread: number }>(`/api/v1/notifications/${encodeURIComponent(id)}`, { method: 'PATCH', body: change, session: true });
export const markRead = (id: string) => updateNotification(id, { read: true });
export const markAllRead = () => call<{ unread: number }>('/api/v1/notifications/mark-all-read', { session: true });
export const getNotificationPreferences = () => call<NotificationPreferences>('/api/v1/notification-preferences', { method: 'GET' });
export const saveNotificationPreferences = (prefs: Pick<NotificationPreferences, 'standard_email_mode' | 'digest_timezone' | 'digest_local_time'>) =>
  call<NotificationPreferences>('/api/v1/notification-preferences', {
    method: 'PUT',
    body: {
      standard_email_mode: prefs.standard_email_mode,
      digest_timezone: prefs.digest_timezone,
      digest_local_time: prefs.digest_local_time,
    },
    session: true,
  });

export interface StreamHandlers {
  onUnread: (unread: number) => void;
  onNotification: (item: AppNotification, unread: number) => void;
  onDisconnect?: () => void;
  onReconnect?: () => void;
}
export function subscribeToNotifications(handlers: StreamHandlers): () => void {
  if (typeof EventSource === 'undefined') return () => undefined;
  const source = new EventSource(`${API_BASE_URL}/api/v1/notifications/stream`, { withCredentials: true });
  let dropped = false;
  source.addEventListener('open', () => { if (dropped) handlers.onReconnect?.(); dropped = false; });
  source.addEventListener('error', () => { if (!dropped) handlers.onDisconnect?.(); dropped = true; });
  source.addEventListener('unread', (event) => handlers.onUnread((JSON.parse((event as MessageEvent).data) as { unread: number }).unread));
  source.addEventListener('notification', (event) => {
    const data = JSON.parse((event as MessageEvent).data) as { notification: AppNotification; unread: number };
    handlers.onNotification(data.notification, data.unread);
  });
  return () => source.close();
}
