/**
 * Source-of-truth JS des couleurs de la charte « Grimoire Vivant », alignée sur les
 * tokens `@theme` de `src/assets/main.css`.
 *
 * À utiliser UNIQUEMENT là où une **valeur hex réelle** est requise en JavaScript :
 * - manipulation d'alpha en JS (`` `${tokens.gold}50` ``, `` `${c}aa` ``),
 * - contexte canvas / Three.js (le moteur 3D ne résout pas les `var(--color-*)`).
 *
 * Dans **tout contexte CSS/DOM** (templates Vue, `:style` sans alpha, blocs
 * `<style>`, attributs SVG inline), préférer `var(--color-*)` qui pointe directement
 * vers la même source — pas de duplication.
 *
 * ⚠️ Toute modification ici DOIT rester synchrone avec `@theme` dans `main.css`.
 */
export const tokens = {
  bg: '#0e0d14',
  bgElev: '#181623',
  surface: '#1f1c2e',
  surfaceRaised: '#2a2640',
  parchment: '#f7ecd0',
  ember: '#ff8247',
  gold: '#f0c764',
  goldDeep: '#b88a2a',
  blood: '#e84545',
  arcane: '#c090ff',
  teal: '#4fd8c0',
  green: '#6fd96f',
  crit: '#ffd700',
  // Couleurs de contenu sans token sémantique CSS dédié (catégorisation données).
  frost: '#7eb8ff', // école d'Illusion
  construct: '#6b6580', // type Constructe
} as const

export type TokenColor = keyof typeof tokens
