import React, { Suspense, useState } from 'react';
import { LoadingState } from '../common/StatusViews';
import { Outlet } from 'react-router-dom';
import { Navbar } from './Navbar';
import { Sidebar } from './Sidebar';
import { NetworkBanner, SessionExpiredBanner } from '../common/StatusBanners';
import { PackNotices } from '../offline/PackNotices';
import { PendingDraftsBanner } from '../offline/PendingDraftsBanner';
import { useDrafts } from '../../hooks/useDrafts';

export const AppLayout: React.FC = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  // Unsent review drafts on this device (R15): the sidebar count and the reconnect banner.
  const { unsent } = useDrafts();

  return (
    <div className="min-h-screen text-on-surface dark:text-on-dark flex">
      {/* Sidebar Navigation */}
      <Sidebar 
        isOpen={isSidebarOpen} 
        onClose={() => setIsSidebarOpen(false)} 
        unsentDrafts={unsent.length}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col lg:pl-72 min-w-0">
        <Navbar 
          onToggleSidebar={() => setIsSidebarOpen((prev) => !prev)}
          isSidebarOpen={isSidebarOpen}
        />
        <NetworkBanner />
        <SessionExpiredBanner />
        <PackNotices />
        <PendingDraftsBanner count={unsent.length} />
        <main className="flex-1 p-4 sm:p-6 lg:p-8 max-w-7xl w-full mx-auto">
          <Suspense fallback={<LoadingState />}>
            <Outlet />
          </Suspense>
        </main>
      </div>
    </div>
  );
};
