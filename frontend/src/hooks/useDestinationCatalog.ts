import { listAllDestinations } from '../api/destinations';
import { failureKind } from '../components/common/StatusViews';
import { savedDestinations } from '../offline/savedDestinations';
import { listPacks } from '../offline/packStore';
import { packToSummary } from '../offline/packAdapter';
import { dhakaToday } from '../offline/advisoryState';
import type { DestinationSummary } from '../types';
import { useApiResource } from './useApiResource';
import { useOnlineStatus } from './useNetworkState';

export interface DestinationCatalog {
  items: DestinationSummary[];
  /** True when the list shows only destinations saved on this device (offline). */
  saved: boolean;
}

/** Downloaded packs and opened pages, one entry per destination; when both exist the pack wins (guideline 3). */
async function offlineCatalog(): Promise<DestinationSummary[]> {
  const today = dhakaToday();
  const [opened, packs] = await Promise.all([savedDestinations(), listPacks()]);
  const byId = new Map(opened.map((s) => [s.summary.id, s.summary]));
  if (packs.ok) for (const stored of packs.value) byId.set(stored.destination_id, packToSummary(stored, today));
  return [...byId.values()].sort((a, b) => a.name_en.localeCompare(b.name_en));
}

/**
 * The destination list for Overview, Destinations and the landing page (Frontend-Implemented 5i).
 * Online: the live list. Offline, or when the network fails: only destinations this device has saved
 * (downloaded packs and opened pages), so every card shown can actually be opened. Reloads when the
 * connection changes.
 */
export function useDestinationCatalog() {
  const online = useOnlineStatus();
  return useApiResource<DestinationCatalog>(
    async (signal) => {
      if (!online) return { items: await offlineCatalog(), saved: true };
      try {
        return { items: await listAllDestinations(signal), saved: false };
      } catch (error) {
        const kind = failureKind(error);
        if (kind === 'offline' || kind === 'timeout') {
          return { items: await offlineCatalog(), saved: true };
        }
        throw error;
      }
    },
    [online],
  );
}
