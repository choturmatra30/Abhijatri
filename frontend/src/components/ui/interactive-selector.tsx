import React, { useId, useRef, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import { useImagePolicy } from '../../hooks/useNetworkState';

/**
 * Expanding image panels: one panel is open and shows its text, the others are slim tabs.
 * Adapted from the 21st.dev "interactive-selector" for this app:
 * - data comes in as props (no hard-coded content, no stock images);
 * - lucide icons instead of react-icons; Tailwind keyframes instead of Next.js styled-jsx;
 * - real buttons with arrow-key, Home and End navigation, and focus activates a panel;
 * - panels stack vertically on phones (the original needed 600 px of width);
 * - motion is skipped when the user asks for reduced motion.
 */
export interface SelectorOption {
  id: string;
  title: string;
  description?: string;
  icon: LucideIcon;
  /** `srcSmall` is a ~480 px variant used for closed panels and on low-data connections. */
  image?: { src: string; srcSmall?: string; alt: string; width: number; height: number };
  /** Language of title and description when it differs from the page (e.g. a fallback). */
  lang?: string;
  /** Shown only on the open panel, e.g. a link to the destination guide. */
  action?: React.ReactNode;
  /** Image attribution, shown on the open panel. Required by CC BY / BY-SA images. */
  credit?: React.ReactNode;
}

interface InteractiveSelectorProps {
  options: SelectorOption[];
  /** Accessible name for the whole group, e.g. "Destinations". */
  label: string;
  initialIndex?: number;
  className?: string;
}

export const InteractiveSelector: React.FC<InteractiveSelectorProps> = ({ options, label, initialIndex = 0, className = '' }) => {
  const [active, setActive] = useState(Math.min(initialIndex, Math.max(options.length - 1, 0)));
  // Offline, or a photo that fails to load, leaves the panel's dark background and icon.
  const imagePolicy = useImagePolicy();
  const [failed, setFailed] = useState<ReadonlySet<string>>(() => new Set());
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const baseId = useId();

  const focusPanel = (index: number) => {
    const next = (index + options.length) % options.length;
    setActive(next);
    buttons.current[next]?.focus();
  };

  const onKeyDown = (event: React.KeyboardEvent, index: number) => {
    const keys: Record<string, number> = {
      ArrowRight: index + 1,
      ArrowDown: index + 1,
      ArrowLeft: index - 1,
      ArrowUp: index - 1,
      Home: 0,
      End: options.length - 1,
    };
    if (event.key in keys) {
      event.preventDefault();
      focusPanel(keys[event.key]);
    }
  };

  if (options.length === 0) return null;

  return (
    <div
      role="group"
      aria-label={label}
      className={`flex flex-col md:flex-row gap-2 w-full h-136 md:h-104 ${className}`}
    >
      {options.map((option, index) => {
        const isActive = index === active;
        const Icon = option.icon;
        const panelId = `${baseId}-panel-${index}`;
        return (
          <div
            key={option.id}
            className={`relative min-h-14 md:min-w-16 overflow-hidden rounded-2xl border-2 bg-dark-surface-1 shadow-lg
              transition-[flex-grow,border-color,box-shadow] duration-700 ease-out motion-reduce:transition-none
              motion-safe:animate-[selector-in_0.6s_ease-out_both]
              ${isActive ? 'flex-[7_1_0%] border-white/90 dark:border-neon-lime shadow-2xl' : 'flex-[1_1_0%] border-transparent'}`}
            style={{ animationDelay: `${index * 120}ms` }}
          >
            {option.image && imagePolicy !== 'none' && !failed.has(option.id) && (
              <img
                // Closed panels are slim strips: the small variant is enough. The open panel lets the
                // browser pick by width, unless the connection is constrained.
                src={isActive && imagePolicy === 'full' ? option.image.src : (option.image.srcSmall ?? option.image.src)}
                srcSet={
                  isActive && imagePolicy === 'full' && option.image.srcSmall
                    ? `${option.image.srcSmall} 480w, ${option.image.src} ${option.image.width}w`
                    : undefined
                }
                sizes={isActive && imagePolicy === 'full' ? '(min-width: 768px) 60vw, 100vw' : undefined}
                onError={() => setFailed((prev) => new Set(prev).add(option.id))}
                alt={isActive ? option.image.alt : ''}
                width={option.image.width}
                height={option.image.height}
                loading={index === active ? 'eager' : 'lazy'}
                decoding="async"
                className={`absolute inset-0 h-full w-full object-cover transition-transform duration-700 ease-out motion-reduce:transition-none
                  ${isActive ? 'scale-100' : 'scale-110'}`}
              />
            )}
            {/* Bottom shade so white text stays readable on any photo. */}
            <div
              aria-hidden="true"
              className={`pointer-events-none absolute inset-0 bg-linear-to-t from-black/85 via-black/30 to-black/10 transition-opacity duration-700
                ${isActive ? 'opacity-100' : 'opacity-70'}`}
            />

            {/* The whole panel is the selector button; the open panel's link sits above it. */}
            <button
              ref={(el) => {
                buttons.current[index] = el;
              }}
              type="button"
              id={`${panelId}-button`}
              aria-expanded={isActive}
              aria-controls={panelId}
              onClick={() => setActive(index)}
              onFocus={() => setActive(index)}
              onKeyDown={(event) => onKeyDown(event, index)}
              className="absolute inset-0 z-10 w-full cursor-pointer rounded-2xl text-left focus-visible:outline-solid focus-visible:outline-4 focus-visible:-outline-offset-4 focus-visible:outline-neon-lime"
            >
              <span className="sr-only">{option.title}</span>
            </button>

            <div className="pointer-events-none absolute inset-x-0 bottom-0 z-20 flex items-end gap-3 p-3 md:p-4">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full border-2 border-white/30 bg-black/50 text-white">
                <Icon size={20} aria-hidden="true" />
              </span>
              <div
                id={panelId}
                lang={option.lang}
                className={`min-w-0 flex-1 text-white transition-all duration-700 ease-out motion-reduce:transition-none
                  ${isActive ? 'translate-x-0 opacity-100' : 'translate-x-6 opacity-0 md:opacity-0 max-md:translate-x-0 max-md:opacity-100'}`}
              >
                <p className="text-base md:text-lg font-bold font-title leading-tight wrap-anywhere">{option.title}</p>
                {isActive && option.description && (
                  <p className="mt-1 hidden sm:block text-sm text-white/85 leading-snug line-clamp-2">{option.description}</p>
                )}
                {isActive && option.action && <div className="pointer-events-auto mt-3">{option.action}</div>}
              </div>
            </div>

            {isActive && option.credit && (
              <div className="pointer-events-auto absolute right-2 top-2 z-20 max-w-[85%] rounded-full bg-black/55 px-2.5 py-1 text-[10px] leading-tight text-white/90">
                {option.credit}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default InteractiveSelector;
