import { listAllDestinations } from '../api/destinations';
import { failureKind } from '../components/common/StatusViews';
import { savedDestinations } from '../offline/savedDestinations';
import type { DestinationSummary } from '../types';
import { useApiResource } from './useApiResource';
import { useOnlineStatus } from './useNetworkState';

export interface DestinationCatalog {
  items: DestinationSummary[];
  /** True when the list shows only destinations saved on this device (offline). */
  saved: boolean;
}

/**
 * The destination list for Overview, Destinations and the landing page (Frontend-Implemented 5i).
 * Online: the live list. Offline, or when the network fails: only destinations whose page this device
 * has saved, so every card shown can actually be opened. Reloads when the connection changes.
 */
export function useDestinationCatalog() {
  const online = useOnlineStatus();
  return useApiResource<DestinationCatalog>(
    async (signal) => {
      if (!online) return { items: (await savedDestinations()).map((s) => s.summary), saved: true };
      try {
        return { items: await listAllDestinations(signal), saved: false };
      } catch (error) {
        const kind = failureKind(error);
        if (kind === 'offline' || kind === 'timeout') {
          return { items: (await savedDestinations()).map((s) => s.summary), saved: true };
        }
        throw error;
      }
    },
    [online],
  );
}
