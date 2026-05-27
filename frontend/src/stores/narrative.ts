import { defineStore } from 'pinia'
import { computed } from 'vue'
import { useGameStore } from './game'
import type { NarrativeEntry as BackendNarrativeEntry } from '../types'
import type { ExNarrativeEntry } from '../fixtures/exploration'

// Adapter backend → V2 récit
// Backend NarrativeEntry types : narration | dialogue | roll | system | player | combat_action
// V2 ExNarrativeEntry types    : divider  | gm       | player | roll | decision
// `decision` n'existe pas (encore) côté backend — pas d'émission par cet adapter.

function adapt(entry: BackendNarrativeEntry, idx: number): ExNarrativeEntry | null {
  const id = idx + 1

  // ── combat_action → combat ──────────────────────────────────────────────────
  if (entry.type === 'combat_action' && entry.combatAction) {
    const ca = entry.combatAction
    return {
      id,
      type: 'combat',
      attacker: ca.attacker_name,
      target: ca.target_name,
      d20: ca.d20,
      attackRoll: ca.attack_roll,
      targetAc: ca.target_ac,
      hit: ca.hit,
      damage: ca.damage,
      critical: ca.critical,
    }
  }

  if (entry.type === 'system') {
    // Inline system notifications (⚙ text-muted) — distinct des dividers de section (gold)
    return { id, type: 'system', text: entry.text ?? '' }
  }

  if (entry.type === 'roll' && entry.roll) {
    const r = entry.roll
    const hit = r.success ?? (r.dc !== undefined && r.dc !== null ? r.total >= r.dc : r.total >= 10)
    const critical = !!(r.critical)
    const what = r.label
      ? (r.dc !== undefined && r.dc !== null ? `${r.label} · DD ${r.dc}` : r.label)
      : r.dice_notation
    return {
      id,
      type: 'roll',
      who: r.character_name ?? entry.speaker ?? '—',
      what,
      rolls: [{ label: r.dice_notation, value: r.total, hit, critical }],
      result: critical ? 'Critique !' : hit ? 'Succès' : 'Échec',
      detail: r.breakdown ?? undefined,
    }
  }

  if (entry.type === 'player') {
    return {
      id,
      type: 'player',
      who: entry.speaker ?? 'Vous',
      text: entry.text ?? '',
    }
  }

  // ── dialogue → type dédié avec speakerKind ──────────────────────────────────
  if (entry.type === 'dialogue') {
    // Un joueur humain parlant via dialogue → player (gold), pas NPC (teal)
    if (entry.speaker_kind === 'human') {
      return {
        id,
        type: 'player',
        who: entry.speaker ?? '',
        text: entry.text ?? '',
      }
    }
    return {
      id,
      type: 'dialogue',
      who: entry.speaker ?? '',
      text: entry.text ?? '',
      speakerKind: entry.speaker_kind === 'companion' ? 'companion' : 'npc',
    }
  }

  if (entry.type === 'narration') {
    if (entry.entry_kind === 'system') {
      return { id, type: 'divider', text: entry.text ?? '' }
    }
    if (entry.entry_kind === 'dialogue' && (entry.speaker_kind === 'human' || entry.speaker_kind === 'companion')) {
      return {
        id,
        type: 'player',
        who: entry.speaker ?? '',
        text: entry.text ?? '',
      }
    }
    // narration / action GM par défaut
    return { id, type: 'gm', text: entry.text ?? '' }
  }

  return null
}

export const useNarrativeStore = defineStore('narrative', () => {
  const gameStore = useGameStore()

  const entries = computed<ExNarrativeEntry[]>(() =>
    gameStore.narrativeLog
      .map((entry, idx) => adapt(entry, idx))
      .filter((e): e is ExNarrativeEntry => e !== null),
  )

  return { entries }
})
