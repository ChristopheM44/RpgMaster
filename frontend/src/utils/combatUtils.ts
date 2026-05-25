import type { CombatantState } from '../types'

/**
 * Returns the semantic tone color token name for a combatant.
 * Mirrors the design spec colour coding:
 *   - Joueur humain (vous) → ember
 *   - Allié contrôlé par IA     → arcane
 *   - Allié humain secondaire    → teal
 *   - Ennemi                     → blood
 */
export function toneForCombatant(
  unit: CombatantState,
  myCharId: string | null | undefined,
): 'ember' | 'arcane' | 'teal' | 'blood' {
  if (unit.kind !== 'pc') return 'blood'
  if (unit.id === myCharId) return 'ember'
  if (unit.is_ai || unit.is_ai_controlled) return 'arcane'
  return 'teal'
}

/** CSS var-based colour string for a tone name. */
export function toneColor(tone: 'ember' | 'arcane' | 'teal' | 'blood' | 'gold' | 'green'): string {
  return `var(--color-${tone})`
}

/** HP ratio colour: green > 50%, gold > 25%, blood ≤ 25% */
export function hpColor(cur: number, max: number): string {
  const ratio = max > 0 ? cur / max : 0
  if (ratio > 0.5) return 'var(--color-green)'
  if (ratio > 0.25) return 'var(--color-gold)'
  return 'var(--color-blood)'
}
