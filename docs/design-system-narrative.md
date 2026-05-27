# Palette Récit — Design System Narratif

> Référence complète des entrées du log narratif (Récit).  
> Fichiers clés : `NarrativeEntry.vue`, `RollCard.vue`, `DecisionCard.vue`, `fixtures/exploration.ts`

## Palette des 12 types

| Type | Couleur | Token CSS | Glyph | `ExNarrativeEntry.type` |
|---|---|---|---|---|
| Maître du Jeu | `#ff8247` | `--color-ember` | `✦` | `gm` |
| Joueur Humain | `#f0c764` | `--color-gold` | `◉` | `player` |
| Joueur IA (compagnon) | `#c090ff` | `--color-arcane` | `◈` | `dialogue` + `speakerKind='companion'` |
| PNJ | `#4fd8c0` | `--color-teal` | `❦` | `dialogue` + `speakerKind='npc'` |
| Jet — Succès | `#6fd96f` | `--color-green` | `✓` | `roll` + `roll.hit=true` |
| Jet — Échec | `#e84545` | `--color-blood` | `✕` | `roll` + `roll.hit=false` |
| Jet — Critique | `#ffd700` | `--color-crit` | `★` | `roll` + `roll.critical=true` |
| Attaque / Combat | `#e84545` | `--color-blood` | `⚔` | `combat` |
| Décision | `#f0c764` | `--color-gold` | `◆` | `decision` |
| Système (notification) | `rgba(247,236,208,.50)` | `--color-text-muted` | `⚙` | `system` |
| Divider (section) | `#f0c764` | `--color-gold` | `✦ … ✦` | `divider` |

> **Note :** Attaque et Combat (événement) sont fusionnés en `blood`. Le type `Environnement` (☽ `#6b6580`) est réservé pour une prochaine vague.

---

## Convention sémantique des couleurs

| Couleur | Token | Signification |
|---|---|---|
| Ember `#ff8247` | `--color-ember` | Maître du Jeu · accents CTA · boutons primaires |
| Gold `#f0c764` | `--color-gold` | **Joueur humain** · sélection · décisions · tour actif |
| Arcane `#c090ff` | `--color-arcane` | Compagnon IA · sorts · magie |
| Teal `#4fd8c0` | `--color-teal` | PNJ · alliés · déplacement · succès |
| Blood `#e84545` | `--color-blood` | Danger · ennemis · attaques · HP critiques |
| Green `#6fd96f` | `--color-green` | Jet réussi · HP pleins · zone sûre |
| Crit `#ffd700` | `--color-crit` | Jet critique uniquement — or pur, distinct de gold |
| Text-muted | `--color-text-muted` | Notifications système · métadonnées |

---

## Types de données

### `ExNarrativeEntry` (union discriminée)

```typescript
// fixtures/exploration.ts
export interface ExRoll {
  label: string
  value: number
  hit: boolean
  critical?: boolean   // → is-critical dans RollCard (★, --color-crit)
}

export type ExNarrativeEntry =
  | { id: number; type: 'divider'; text: string }
  | { id: number; type: 'gm'; text: string; refs?: string[] }
  | { id: number; type: 'player'; who: string; text: string; refs?: string[] }
  | { id: number; type: 'dialogue'; who: string; text: string; speakerKind?: 'companion' | 'npc' }
  | { id: number; type: 'roll'; who: string; what: string; rolls: ExRoll[]; result?: string; detail?: string }
  | { id: number; type: 'decision'; who: string; text: string; options: ExDecisionOption[] }
  | { id: number; type: 'combat'; attacker: string; target: string; d20: number;
      attackRoll: number; targetAc: number; hit: boolean; damage: number | null; critical?: boolean }
  | { id: number; type: 'system'; text: string }
```

### Mapping backend → ExNarrativeEntry (`stores/narrative.ts`)

| Type backend | `entry_kind` | → ExNarrativeEntry |
|---|---|---|
| `narration` | — | `gm` |
| `narration` | `system` | `divider` (séparateur de section) |
| `narration` | `dialogue` + speaker human/companion | `player` |
| `dialogue` | — | `dialogue` (speakerKind depuis `speaker_kind`) |
| `player` | — | `player` |
| `roll` | — | `roll` (avec `critical` propagé) |
| `combat_action` | — | `combat` |
| `system` | — | `system` (notification inline ⚙) |

---

## Composants

### `NarrativeEntry.vue`
Composant canonique. Gère tous les types. Utilisé dans le drawer combat et la colonne exploration.

Classes CSS clés :
- `.ne-gm` — ember eyebrow `✦ Maître du jeu`
- `.ne-player` — gold border-left `◉ NOM`
- `.ne-dialogue.tone-arcane` — compagnon IA `◈`
- `.ne-dialogue.tone-teal` — PNJ `❦`
- `.ne-combat` — blood
- `.ne-system` — ⚙ text-muted, font-mono

### `RollCard.vue`
Prop déterminante : `entry.rolls[0].critical`

| État CSS | Condition | Couleur | Glyph |
|---|---|---|---|
| `.is-critical` | `critical === true` | `--color-crit` | `★` |
| `.is-success` | `hit === true` | `--color-green` | `✓` |
| `.is-fail` | `hit === false` | `--color-blood` | `✕` |

> Priorité : `is-critical` > `is-success` > `is-fail`

### `DecisionCard.vue`
Eyebrow : `◆ Décision · {who}` (gold, Cinzel uppercase)

---

## Anti-patterns

- ❌ `color: var(--color-ember)` pour identifier le joueur humain → utiliser `--color-gold`
- ❌ `tone-gold` sur les dialogues PNJ → utiliser `tone-teal` + glyph `❦`
- ❌ Hex en dur (`#ff8247`) dans les templates Vue → toujours via `var(--color-*)`
- ❌ Exposer `motivations.hidden` ou `secrets` côté joueur IA
