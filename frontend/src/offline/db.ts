import { openDB, type DBSchema, type IDBPDatabase } from 'idb';
import type { PackDocument } from '../types';

/*
 * The app's IndexedDB database (R13, R15; Offline-Frontend-Guideline 4.2). This is the only file that
 * touches IndexedDB directly. It holds public packs, the user's own drafts, and the Tours chat rows
 * and unsent messages explicitly allowed by the Tours offline design. Never sessions, tokens,
 * verification evidence, safety data, staff data, or arbitrary `no-store` responses.
 */

export const DB_NAME = 'abhijatri-offline';
export const DB_VERSION = 2;

/** A verified destination pack as stored on the device. */
export interface StoredPack {
  destination_id: string;
  pack: PackDocument;
  /** SHA-256 of the exact bytes the server sent; checked before the pack was stored. */
  sha256: string;
  size_bytes: number;
  downloaded_at: string;
  last_checked_at: string | null;
  update_available: boolean;
}

/**
 * R15 drafts. The store is created now so R15 needs no schema migration; its record type is defined
 * with the R15 work (Offline-Frontend-Guideline 4.2, `StoredDraft`).
 */
export interface DraftRecord {
  client_draft_id: string;
  state: string;
  [field: string]: unknown;
}

export interface StoredChatMessage {
  tour_id: string;
  seq: number;
  message: Record<string, unknown>;
  cached_at: string;
}

export interface ChatOutboxRecord {
  client_msg_id: string;
  tour_id: string;
  body: string;
  created_at: string;
  state: 'PENDING' | 'SENDING' | 'FAILED';
  error?: string;
}

interface OfflineDb extends DBSchema {
  packs: { key: string; value: StoredPack };
  drafts: { key: string; value: DraftRecord; indexes: { by_state: string } };
  meta: { key: string; value: unknown };
  chat_messages: { key: [string, number]; value: StoredChatMessage; indexes: { by_tour: string } };
  chat_outbox: { key: string; value: ChatOutboxRecord; indexes: { by_tour: string; by_state: string } };
}

export type OfflineDatabase = IDBPDatabase<OfflineDb>;

/** Why storage could not be used: `quota` means "storage is full", `unavailable` covers the rest. */
export type StorageFailure = 'quota' | 'unavailable';
export type StoreResult<T> = { ok: true; value: T } | { ok: false; reason: StorageFailure };

let opening: Promise<OfflineDatabase> | null = null;

function open(): Promise<OfflineDatabase> {
  if (typeof indexedDB === 'undefined') return Promise.reject(new Error('IndexedDB is not available'));
  if (!opening) {
    opening = openDB<OfflineDb>(DB_NAME, DB_VERSION, {
      upgrade(db, oldVersion) {
        // Version 1. A later version adds its own `if (oldVersion < N)` block. Never delete a store that
        // may hold unsent drafts (Offline-Frontend-Guideline 4.2).
        if (oldVersion < 1) {
          db.createObjectStore('packs', { keyPath: 'destination_id' });
          const drafts = db.createObjectStore('drafts', { keyPath: 'client_draft_id' });
          drafts.createIndex('by_state', 'state');
          db.createObjectStore('meta');
        }
        if (oldVersion < 2) {
          const messages = db.createObjectStore('chat_messages', { keyPath: ['tour_id', 'seq'] });
          messages.createIndex('by_tour', 'tour_id');
          const outbox = db.createObjectStore('chat_outbox', { keyPath: 'client_msg_id' });
          outbox.createIndex('by_tour', 'tour_id');
          outbox.createIndex('by_state', 'state');
        }
      },
      // Another tab opened a newer version: let it upgrade, and reopen on the next call.
      blocking(_current, _next, event) {
        (event.target as IDBDatabase | null)?.close();
        opening = null;
      },
      terminated() {
        opening = null;
      },
    }).catch((error: unknown) => {
      opening = null;
      throw error;
    });
  }
  return opening;
}

/** Maps a storage error to the reason shown to the user. */
export function storageFailure(error: unknown): StorageFailure {
  const name = (error as { name?: string } | null)?.name;
  return name === 'QuotaExceededError' ? 'quota' : 'unavailable';
}

/**
 * Runs `work` with the database and never throws: private mode, blocked storage, a full disk or a
 * browser that lost the database all become `{ ok: false, reason }`, so the app keeps working.
 */
export async function withDb<T>(work: (db: OfflineDatabase) => Promise<T>): Promise<StoreResult<T>> {
  try {
    return { ok: true, value: await work(await open()) };
  } catch (error) {
    return { ok: false, reason: storageFailure(error) };
  }
}

/** Tests only: forget the open connection so each test starts clean. */
export async function resetDbForTests(): Promise<void> {
  if (opening) {
    try {
      (await opening).close();
    } catch {
      /* already failed */
    }
  }
  opening = null;
}
