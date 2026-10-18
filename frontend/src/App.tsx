import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { LanguageProvider } from './context/LanguageContext';
import { ThemeProvider } from './context/ThemeContext';
import { AppLayout } from './components/layout/AppLayout';
import { OverviewPage } from './pages/OverviewPage';
import { DestinationsPage } from './pages/DestinationsPage';
import { DestinationDetailPage } from './pages/DestinationDetailPage';
import { PlannerPage } from './pages/PlannerPage';
import { OfflinePacksPage } from './pages/OfflinePacksPage';
import { SavedTripsPage } from './pages/SavedTripsPage';
import { ReviewsPage } from './pages/ReviewsPage';
import { HealthCheckPage } from './pages/HealthCheckPage';

export const App: React.FC = () => {
  return (
    <ThemeProvider>
      <LanguageProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/" element={<AppLayout />}>
              <Route index element={<OverviewPage />} />
              <Route path="overview" element={<Navigate to="/" replace />} />
              <Route path="destinations" element={<DestinationsPage />} />
              <Route path="destinations/:id" element={<DestinationDetailPage />} />
              <Route path="planner" element={<PlannerPage />} />
              <Route path="offline-packs" element={<OfflinePacksPage />} />
              <Route path="trips" element={<SavedTripsPage />} />
              <Route path="reviews" element={<ReviewsPage />} />
              <Route path="health" element={<HealthCheckPage />} />
              {/* Fallback to home */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </LanguageProvider>
    </ThemeProvider>
  );
};

export default App;
