/**
 * IRIS Hospitals — Ease Health theme: shared motion constants.
 *
 * Import these in every theme component instead of defining local durations or easings.
 * No springs, no bounce — every transition uses EASE_IRIS (ease-out cubic).
 * Under reduced motion framer-motion disables transform animations; opacity fades still play.
 */

import type { Variants } from 'framer-motion';

// ---------------------------------------------------------------------------
// Easing
// ---------------------------------------------------------------------------

/** Ease-out cubic — the only easing used in the IRIS Ease Health theme. */
export const EASE_IRIS = [0.22, 1, 0.36, 1] as const;

// ---------------------------------------------------------------------------
// Durations (seconds)
// ---------------------------------------------------------------------------

export const DUR = {
  /** 150 ms — instant feedback: toggle, chip press, focus ring. */
  fast: 0.15,
  /** 320 ms — standard UI transition: fade, slide. */
  base: 0.32,
  /** 500 ms — slower reveal: widget entrance. */
  slow: 0.5,
  /** 700 ms — opening animation beats. */
  intro: 0.7,
} as const;

// ---------------------------------------------------------------------------
// Variants
// ---------------------------------------------------------------------------

/**
 * fadeUp — fade in from 8 px below.
 * Usage: initial="hidden" animate="show" (or whileInView="show")
 */
export const fadeUp: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: {
    opacity: 1,
    y: 0,
    transition: {
      duration: DUR.base,
      ease: EASE_IRIS,
    },
  },
};

/**
 * stagger — container variant that staggers its children.
 * @param childDelay seconds between each child's animation start (default 0.08).
 *
 * Usage:
 *   <motion.div variants={stagger()} initial="hidden" animate="show">
 *     <motion.div variants={fadeUp}>…</motion.div>
 *   </motion.div>
 */
export function stagger(childDelay = 0.08): Variants {
  return {
    hidden: {},
    show: {
      transition: {
        staggerChildren: childDelay,
      },
    },
  };
}
