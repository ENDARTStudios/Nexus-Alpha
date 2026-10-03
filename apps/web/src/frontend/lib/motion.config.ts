import type { Variants } from "framer-motion";

// Sistema de movimento padronizado da Nexus-Alpha.
export const springSoft: Variants = {
  hidden: { opacity: 0, y: 12 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { type: "spring", stiffness: 120, damping: 18 },
  },
};

export const springPanel: Variants = {
  hidden: { opacity: 0, y: 24, scale: 0.96 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: "spring", stiffness: 260, damping: 24 },
  },
  exit: {
    opacity: 0,
    y: 24,
    scale: 0.96,
    transition: { duration: 0.15 },
  },
};

export const springBubble = {
  type: "spring",
  stiffness: 320,
  damping: 22,
} as const;

export const palette = {
  graphite: "#0F172A",
  electricViolet: "#8B5CF6",
} as const;
