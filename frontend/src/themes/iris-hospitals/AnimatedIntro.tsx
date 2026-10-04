/**
 * iris-hospitals/AnimatedIntro.tsx
 *
 * Opening animation for the IRIS Ease Health theme.
 * Rebuilt per section G: layered-panel entrance, logo reveal, tagline fadeUp.
 * The old dark demo chat intro was removed entirely.
 *
 * Contract:
 *   export default AnimatedIntro
 *   props: { onComplete: () => void; hospitalName?: string }
 */

import React, { useEffect, useRef, useState } from 'react';
import { motion, useReducedMotion } from 'framer-motion';
import { EASE_IRIS, DUR } from './motion';
import irisLogo from './iris-logo.png';

interface AnimatedIntroProps {
  onComplete: () => void;
  hospitalName?: string;
}

// ---------------------------------------------------------------------------
// Decorative panel definitions — back-to-front order
// ---------------------------------------------------------------------------

/** Four tinted panels stacked with small offsets, aria-hidden, flat surfaces. */
const PANELS = [
  {
    key: 'slate',
    bg: 'bg-iris-slate',
    sizeClass: 'w-[86vw] h-[min(400px,56vh)] md:w-[min(520px,86vw)] md:h-[min(340px,56vh)]',
    delay: 0,
  },
  {
    key: 'sage',
    bg: 'bg-iris-sage',
    sizeClass: 'w-[calc(86vw-28px)] h-[min(372px,calc(56vh-28px))] md:w-[min(492px,calc(86vw-28px))] md:h-[min(312px,calc(56vh-28px))]',
    delay: 0.12,
  },
  {
    key: 'mint',
    bg: 'bg-iris-mint',
    sizeClass: 'w-[calc(86vw-56px)] h-[min(344px,calc(56vh-56px))] md:w-[min(464px,calc(86vw-56px))] md:h-[min(284px,calc(56vh-56px))]',
    delay: 0.24,
  },
  {
    key: 'keylime',
    bg: 'bg-iris-accent-surface',
    sizeClass: 'w-[calc(86vw-84px)] h-[min(316px,calc(56vh-84px))] md:w-[min(436px,calc(86vw-84px))] md:h-[min(256px,calc(56vh-84px))]',
    delay: 0.36,
  },
] as const;


// ---------------------------------------------------------------------------
// AnimatedIntro
// ---------------------------------------------------------------------------

const AnimatedIntro: React.FC<AnimatedIntroProps> = ({ onComplete, hospitalName }) => {
  const prefersReducedMotion = useReducedMotion();
  const completedRef = useRef(false);
  const skippedRef = useRef(false);
  const [logoError, setLogoError] = useState(false);
  const [exitPhase, setExitPhase] = useState(false);
  const [exitDuration, setExitDuration] = useState(0.5);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);

  // Guard: onComplete fires exactly once regardless of skip vs natural end.
  const fireOnComplete = () => {
    if (completedRef.current) return;
    completedRef.current = true;
    onComplete();
  };

  // ── Reduced motion: render nothing, call onComplete immediately ───────────
  useEffect(() => {
    if (prefersReducedMotion) {
      fireOnComplete();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefersReducedMotion]);

  // ── Main timeline ─────────────────────────────────────────────────────────
  useEffect(() => {
    if (prefersReducedMotion) return;

    const add = (fn: () => void, ms: number) => {
      const id = setTimeout(fn, ms);
      timersRef.current.push(id);
      return id;
    };

    // 1900ms: begin exit animation (500ms natural exit duration)
    add(() => {
      setExitDuration(0.5);
      setExitPhase(true);
    }, 1900);

    // 2400ms: call onComplete after exit animation (500ms exit duration)
    add(() => fireOnComplete(), 2400);

    return () => {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefersReducedMotion]);

  // ── Skip handler ──────────────────────────────────────────────────────────
  const skip = () => {
    if (skippedRef.current || completedRef.current) return;
    skippedRef.current = true;
    // Clear all pending timers so the natural end doesn't race.
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    // 200ms fade-out, then fire.
    setExitDuration(0.2);
    setExitPhase(true);
    const id = setTimeout(() => fireOnComplete(), 200);
    timersRef.current.push(id);
  };

  // Keyboard skip: Escape, Enter, Space
  useEffect(() => {
    if (prefersReducedMotion) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      if (e.key === 'Escape' || e.key === 'Enter' || e.key === ' ') {
        if (e.key === ' ') {
          e.preventDefault();
        }
        skip();
      }
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [prefersReducedMotion]);

  if (prefersReducedMotion) return null;

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <motion.div
      className="fixed inset-0 flex items-center justify-center z-50 bg-iris-surface bg-[image:var(--iris-bg-gradient)] touch-manipulation focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-iris-primary"
      animate={exitPhase ? { opacity: 0 } : { opacity: 1 }}
      transition={{ duration: exitPhase ? exitDuration : 0.01, ease: EASE_IRIS }}
      role="button"
      tabIndex={0}
      aria-label="Skip intro"
      onClick={skip}
    >
      {/* ── Decorative layered panels (aria-hidden, back-to-front) ─────── */}
      {PANELS.map((panel) => (
        <motion.div
          key={panel.key}
          aria-hidden="true"
          className={`absolute rounded-iris ${panel.bg} ${panel.sizeClass}`}
          initial={{ opacity: 0, y: 24 }}
          animate={exitPhase
            ? { opacity: 0, y: 8 }
            : { opacity: 1, y: 0 }
          }
          transition={{
            duration: exitPhase ? exitDuration : 0.4,
            delay: exitPhase ? 0 : panel.delay,
            ease: EASE_IRIS,
          }}
        />
      ))}

      {/* ── Centred content: logo + tagline ──────────────────────────────── */}
      <div className="relative flex flex-col items-center gap-6">

        {/* Logo panel */}
        <motion.div
          className="bg-iris-surface-raised rounded-iris flex items-center justify-center px-[18px] py-[16px]"
          initial={{ opacity: 0, scale: 0.98, filter: 'blur(6px)' }}
          animate={exitPhase
            ? { opacity: 0, scale: 0.98, filter: 'blur(6px)' }
            : { opacity: 1, scale: 1, filter: 'blur(0px)' }
          }
          transition={{
            duration: exitPhase ? exitDuration : DUR.intro,
            delay: exitPhase ? 0 : 0.4,
            ease: EASE_IRIS,
          }}
        >
          {logoError ? (
            /* Text fallback shown only if the image fails to load */
            <span className="font-[family-name:var(--font-iris-display)] font-light text-iris-primary text-[2rem] tracking-[0.1em] px-3 py-1">
              IRIS
            </span>
          ) : (
            <img
              src={irisLogo}
              alt={hospitalName || 'IRIS Hospitals'}
              width={256}
              height={75}
              fetchPriority="high"
              className="w-[200px] md:w-[240px] h-auto"
              onError={() => setLogoError(true)}
            />
          )}
        </motion.div>

        {/* Tagline */}
        <motion.p
          className="font-[family-name:var(--font-iris-display)] font-normal text-iris-primary text-center text-[22px] leading-[1.5] md:text-iris-display-ml"
          initial={{ opacity: 0, y: 8 }}
          animate={exitPhase
            ? { opacity: 0, y: 8 }
            : { opacity: 1, y: 0 }
          }
          transition={{
            duration: exitPhase ? exitDuration : DUR.base,
            delay: exitPhase ? 0 : 0.9,
            ease: EASE_IRIS,
          }}
        >
          കരുതലോടെ.<br /> ബുദ്ധിമാനായ AI-യോടൊപ്പം.
        </motion.p>
      </div>
    </motion.div>
  );
};

export default AnimatedIntro;
