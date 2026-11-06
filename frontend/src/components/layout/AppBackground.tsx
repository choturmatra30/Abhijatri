import React from 'react';
import Velaris from '@/components/ui/velaris';
import { useTheme } from '../../context/ThemeContext';

/*
 * The app-wide animated background (Frontend-Implemented 5f), mounted once at the app root so it
 * keeps running across page changes. Text sits directly on it, so the palettes stay close to the
 * page colour: pale mint on white in the light theme, deep green on near-black in the dark theme.
 * Body text (stone-600 / stone-400) and the primary green keep at least 4.5:1 on the brightest mix.
 * Grain is kept minimal: the canvas renders at half resolution, so each grain dot is upscaled to
 * 2x2 pixels and changes every frame; a trace remains only to prevent colour banding.
 */
const LIGHT = { bg: '#ffffff', colors: ['#dcfce7', '#f0fdf4', '#d1fae5', '#ffffff'] };
const DARK = { bg: '#0c0a09', colors: ['#052e16', '#0f3d22', '#022c22', '#0c0a09'] };

/** Low memory, few cores or Data Saver: one still frame instead of 30 frames a second. */
function lowEndDevice(): boolean {
  if (typeof navigator === 'undefined') return false;
  const nav = navigator as Navigator & { deviceMemory?: number; connection?: { saveData?: boolean } };
  return (nav.deviceMemory !== undefined && nav.deviceMemory < 4) || (nav.hardwareConcurrency || 8) <= 4 || nav.connection?.saveData === true;
}
const STILL = lowEndDevice();

export const AppBackground: React.FC = () => {
  const { theme } = useTheme();
  const palette = theme === 'dark' ? DARK : LIGHT;
  return (
    <div aria-hidden="true" className="fixed inset-0 -z-10">
      <Velaris bg={palette.bg} colors={palette.colors} speed={3.5} grain={0.04} animate={!STILL} className="h-full" />
    </div>
  );
};
