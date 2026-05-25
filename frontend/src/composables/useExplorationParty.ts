// Composable Exploration V2 — adapte les vraies données de session (characterStore +
// currentScene.party_positions) au shape `ExHero` attendu par les composants V2
// (HeroToken, MapLegend, SelectionInspector, RefChip, CarnetGroupSection).
//
// Fallback : si la session n'a pas encore chargé ses personnages, on retombe sur la
// fixture `EX_PARTY` pour que la démo reste affichable.
import { computed } from 'vue'
import { useCharacterStore } from '../stores/character'
import { useGameStore } from '../stores/game'
import { EX_PARTY, type ExHero } from '../fixtures/exploration'
import type { Character, GridPosition } from '../types'

const CLASS_FR: Record<string, string> = {
  fighter: 'Guerrier',
  wizard: 'Mage',
  cleric: 'Clerc',
  rogue: 'Roublard',
  ranger: 'Rôdeur',
  paladin: 'Paladin',
  barbarian: 'Barbare',
  bard: 'Barde',
  druid: 'Druide',
  monk: 'Moine',
  sorcerer: 'Ensorceleur',
  warlock: 'Occultiste',
}

const COLOR_ME = '#ff8247'   // ember
const COLOR_AI = '#c090ff'   // arcane
const COLOR_ALLY = '#4fd8c0' // teal — autre joueur humain

/** "F7" depuis { col: 5, row: 6 } (col 0 → A, row 0 → 1). */
function gridPosLabel(p: GridPosition | undefined): string {
  if (!p) return ''
  const letter = String.fromCharCode(65 + Math.max(0, Math.min(25, p.col)))
  return `${letter}${p.row + 1}`
}

function tokenOf(name: string): string {
  // Token = première lettre, ou deux si le prénom est court (ex. "EL" pour Elara)
  if (!name) return '?'
  const trimmed = name.trim()
  if (trimmed.length <= 1) return trimmed.toUpperCase()
  return trimmed.charAt(0).toUpperCase()
}

function characterToHero(c: Character, position: GridPosition | undefined, myId: string | undefined): ExHero {
  const isMe = c.id === myId
  const color = isMe ? COLOR_ME : c.is_ai ? COLOR_AI : COLOR_ALLY
  return {
    id: c.id,
    token: tokenOf(c.name),
    name: c.name,
    cls: CLASS_FR[c.char_class] ?? c.char_class,
    species: c.species,
    hp: c.hp_current,
    hpMax: c.hp_max,
    ai: c.is_ai,
    isMe,
    color,
    pos: gridPosLabel(position),
    x: position?.col ?? 0,
    y: position?.row ?? 0,
  }
}

/**
 * Retourne la party au format `ExHero[]` :
 * - Si la session a chargé `characterStore.sessionCharacters`, on convertit chaque
 *   personnage en `ExHero` (positions depuis `gameStore.currentScene.party_positions`,
 *   ou réparties autour du centre par défaut).
 * - Sinon, fallback sur `EX_PARTY` (mode démo).
 */
export function useExplorationParty() {
  const charStore = useCharacterStore()
  const gameStore = useGameStore()

  const party = computed<ExHero[]>(() => {
    const chars = charStore.sessionCharacters
    if (!chars.length) return EX_PARTY

    const positions = gameStore.currentScene?.party_positions ?? {}
    const myId = charStore.myCharacter?.id

    // Fallback : ligne horizontale centrée autour de F7 (col 5, row 6).
    // Si la scène a des positions, on les utilise par-dessus.
    return chars.map((c, idx) => {
      const fromScene = positions[c.id]
      const fallback: GridPosition = fromScene ?? {
        col: 3 + idx,
        row: 6,
      }
      return characterToHero(c, fallback, myId)
    })
  })

  function findHero(id: string | null | undefined): ExHero | undefined {
    if (!id) return undefined
    return party.value.find((h) => h.id === id)
  }

  return { party, findHero }
}
