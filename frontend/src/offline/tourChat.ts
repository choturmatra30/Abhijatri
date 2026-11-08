/** Device-local chat cache and idempotent outbox for Tours. */
import { postMessage, type ChatMessage } from '../api/tours';
import { withDb, type ChatOutboxRecord } from './db';

export async function cacheChat(tourId: string, messages: ChatMessage[]): Promise<void> {
  await withDb(async (db) => {
    const transaction = db.transaction('chat_messages', 'readwrite');
    await Promise.all(messages.map((message) => transaction.store.put({
      tour_id: tourId,
      seq: message.seq,
      message: message as unknown as Record<string, unknown>,
      cached_at: new Date().toISOString(),
    })));
    await transaction.done;
  });
}

export async function cachedChat(tourId: string): Promise<ChatMessage[]> {
  const result = await withDb((db) => db.getAllFromIndex('chat_messages', 'by_tour', tourId));
  if (!result.ok) return [];
  return result.value.sort((a, b) => a.seq - b.seq).map((row) => row.message as unknown as ChatMessage);
}

export async function queueChat(tourId: string, body: string, clientMsgId = crypto.randomUUID()): Promise<ChatOutboxRecord> {
  const row: ChatOutboxRecord = { client_msg_id: clientMsgId, tour_id: tourId, body, created_at: new Date().toISOString(), state: 'PENDING' };
  await withDb((db) => db.put('chat_outbox', row));
  return row;
}

export async function pendingChat(tourId: string): Promise<ChatOutboxRecord[]> {
  const result = await withDb((db) => db.getAllFromIndex('chat_outbox', 'by_tour', tourId));
  return result.ok ? result.value.sort((a, b) => a.created_at.localeCompare(b.created_at)) : [];
}

/** Reuses each stable client message id. A lost response therefore cannot create a duplicate. */
export async function flushChatOutbox(tourId: string): Promise<number> {
  const rows = await pendingChat(tourId);
  let sent = 0;
  for (const row of rows) {
    await withDb((db) => db.put('chat_outbox', { ...row, state: 'SENDING' }));
    try {
      const result = await postMessage(tourId, row.body, row.client_msg_id);
      await cacheChat(tourId, [result.message]);
      await withDb((db) => db.delete('chat_outbox', row.client_msg_id));
      sent += 1;
    } catch (error) {
      await withDb((db) => db.put('chat_outbox', { ...row, state: 'FAILED', error: error instanceof Error ? error.message : 'Send failed' }));
      break;
    }
  }
  return sent;
}
