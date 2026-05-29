---
name: frontend-design
description: Guide de référence complet du design system RPGMaster pour créer ou modifier des composants Vue. À utiliser avant de créer un nouveau composant ou quand on travaille sur le frontend.
when_to_use: Quand l'utilisateur demande de créer un composant Vue, modifier le style d'un composant existant, ou travailler sur le frontend RPGMaster.
paths: "frontend/src/**"
---

# RPGMaster — Frontend Design Reference

Guide de référence complet pour créer ou modifier des composants Vue dans RPGMaster.

---

## Identité visuelle

**Direction 3 — Audacieuse / Éditoriale.** Ember + gold sur fonds obsidienne, typographie éditoriale, esthétique dark-fantasy premium. L'interface doit évoquer un grimoire vivant, pas un dashboard SaaS.

---

## Tokens de design complets

### Surfaces
```css
--color-bg: #0e0d14           /* Fond app global */
--color-bg-elev: #181623      /* Header, panneaux, footer */
--color-surface: #1f1c2e      /* Cartes, chips, sections */
--color-surface-raised: #2a2640  /* Hover, cartes sélectionnées */
```

### Texte
```css
--color-parchment: #f7ecd0
--color-parchment-dark: rgba(247,236,208,0.75)
--color-text-muted: rgba(247,236,208,0.50)
--color-text-dim: rgba(247,236,208,0.32)
```

### Bordures
```css
--color-border: rgba(255,235,180,0.07)
--color-border-strong: rgba(255,235,180,0.18)
```

### Accents
```css
--color-ember: #ff8247      /* CTA, joueur humain */
--color-gold: #f0c764       /* Titres, sélection, tour actif */
--color-gold-deep: #b88a2a  /* Dégradés, barres */
--color-blood: #e84545      /* Danger, ennemis, HP crit */
--color-arcane: #c090ff     /* IA, sorts, magie */
--color-teal: #4fd8c0       /* Alliés, déplacement, succès */
--color-green: #6fd96f      /* HP pleins, zone sûre */
--color-dim: #6b6580        /* Brouillard, désactivé */
```

### Gradient, ombres, radius
```css
--grad-primary: linear-gradient(135deg, #ff8247, #f0c764)
--shadow-card-active: 0 0 24px rgba(255,130,71,0.15)
--shadow-cta: 0 2px 12px rgba(255,130,71,0.3)
--shadow-modal: 0 24px 80px rgba(0,0,0,0.6)

--radius-sm: 4px   /* Chips, tags */
--radius-md: 6px   /* Boutons, inputs */
--radius-lg: 10px  /* Cartes */
--radius-xl: 14px  /* Modales */
```

---

## Typographie — échelle complète

| Usage | Famille | Taille | Poids | Letter-spacing |
|---|---|---|---|---|
| Page H1 | Cinzel | 44px | 700 | 1px |
| Section H2 | Cinzel | 28px | 700 | 0.5px |
| Card titre | Cinzel | 17px | 700 | 0.5px |
| Section title | Cinzel | 14px | 700 | 0.15em |
| Onglet | Cinzel | 11px | 700 | 1.2px |
| Eyebrow | Cinzel | 10px | 700 | 0.2em |
| Stat valeur | Cinzel | 22px | 700 | — |
| Récit / prose | Fraunces | 17px × `--narrative-scale` | 400 | — |
| Tagline / synopsis | Fraunces italic | 13–15px | 400 | — |
| Body UI | Inter | 14px | 400–600 | — |
| Compteur | JetBrains Mono | 16px | 700 | — |
| Metadata | JetBrains Mono | 9–10px | 400–500 | — |

---

## Effets de fond

### Grid dust (fond global)
```css
background-image: radial-gradient(circle at 1px 1px, rgba(255,235,180,0.025) 1px, transparent 0);
background-size: 24px 24px;
position: fixed; pointer-events: none; inset: 0;
```

### Lueur radiale (top de page)
```css
background: radial-gradient(ellipse at top, #1a1630 0%, transparent 60%);
position: fixed;
```

### Glow décoratif ember (sections hero)
```css
background: radial-gradient(280px 200px at top left, rgba(255,130,71,0.08), transparent);
```

---

## Patterns de layout

### Structure globale
```
┌─────────────────────────────────────────────────┐
│ AppNav (56px, border-b, bg-elev → transparent)  │
├──────────────────────┬──────────────────────────┤
│ Colonne principale   │ Panneau latéral droit    │
│ (flex-1, scroll)     │ (380–580px, border-l)    │
├──────────────────────┴──────────────────────────┤
│ ActionBar (border-t, bg-elev)                   │
└─────────────────────────────────────────────────┘
```

### AppNav
- Hauteur 56px (`h-14`), `bg-elev` avec `border-b border`
- Logo carré 32px : `--grad-primary` + glow ember
- Titre `RPGMASTER` Cinzel 15px wt700 ls 0.1em
- NavPills : `rounded-full`, état actif `color-gold` + fond gold 10%
- Indicateur "EN LIGNE" : dot vert glow

### Modales
```css
width: 560px; padding: 28px; border-radius: 14px;
background: linear-gradient(180deg, #181623, #0e0d14);
border: 1px solid var(--color-border-strong);
box-shadow: 0 24px 80px rgba(0,0,0,0.6);
/* Backdrop */
background: rgba(8,6,12,0.7); backdrop-filter: blur(6px);
```
Glow ember radial en top-right.

### Sections repliables
```vue
<script setup>
const collapsed = ref(localStorage.getItem(`rpg.exploration.collapsed.${id}`) === '1')
const toggle = () => {
  collapsed.value = !collapsed.value
  localStorage.setItem(`rpg.exploration.collapsed.${id}`, collapsed.value ? '1' : '0')
}
</script>
<!-- Chevron : rotate(90deg) fermé → rotate(0deg) ouvert, transition 200ms -->
```

---

## Icônes

### Utilisation
- **Unicode** pour les éléments inline : `✦ ◆ ◷ ◉ ❦ ⚔ ☽ ▶ →`
- **SVG custom** : `icons/color/` (coloré) et `icons/mono/` (parchment). ViewBox `0 0 24 24`, stroke-width 1.5–2px, stroke-linecap round.

### États d'interaction
| État | Style |
|---|---|
| Normal | Couleur catégorie |
| Hover | Fond `rgba(247,236,208,0.08)` |
| Active | Fond `rgba(240,199,100,0.12)` + ring gold + `drop-shadow(0 0 4px currentColor)` |
| Disabled | `opacity: 0.3` |

### Catégories
- **Exploration** (16) : joueur, alliés, portes, POI, pièges, brouillard…
- **Combat Alliés** (7) : allié, tour actif, déplacement, cibles
- **Combat Ennemis** (6) : standard, élite, vaincu, fuite
- **Combat Terrain** (7) : obstacles, couverts, zone d'effet, ligne de vue

Référence complète : `icons/ICONS-README.md`

---

## Modèles TypeScript

### Character
```ts
type Character = {
  id: string; name: string; initial: string;
  char_class: 'Fighter'|'Druid'|'Rogue'|'Ranger'|'Wizard'|'Cleric'|'Bard'|'Paladin'|'Sorcerer'|'Warlock'|'Monk'|'Barbarian';
  species: string; level: number;
  hp_current: number; hp_max: number; hp_temp: number;
  ac: number; init: number; speed: number;
  is_ai: boolean; is_self: boolean;
  abilities: Record<'FOR'|'DEX'|'CON'|'INT'|'SAG'|'CHA', { v: number; m: string }>;
  equipped: string; spells_left: string | null; conditions: string[];
  accent: 'ember'|'gold'|'arcane'|'green';
}

const CLASS_FR: Record<string, string> = {
  Fighter: 'Guerrier', Druid: 'Druide', Rogue: 'Roublard', Ranger: 'Rôdeur',
  Wizard: 'Magicien', Cleric: 'Clerc', Bard: 'Barde', Paladin: 'Paladin',
  Sorcerer: 'Ensorceleur', Warlock: 'Occultiste', Monk: 'Moine', Barbarian: 'Barbare',
}
```

### Quest
```ts
type Quest = {
  id: string; kind: 'principale'|'secondaire'|'rumeur';
  title: string; desc: string;
  progress: number; steps: number | null; due?: string;
}
```

### MemoryEntry
```ts
type MemoryEntry = {
  kind: 'PNJ'|'Lieu'; name: string; detail: string;
  tag: 'allié'|'neutre'|'sûr'|'danger'|'à explorer';
}
```

---

## Structure d'un composant Vue

```vue
<script setup lang="ts">
import { ref, computed } from 'vue'
// imports stores, composables, types
</script>

<template>
  <!-- Utiliser .rpg-* en priorité, sinon Tailwind avec les tokens @theme -->
</template>
```

### Nommage
- **Composants** : PascalCase descriptif (`AdventureLogPanel.vue`, `CombatTracker.vue`)
- **Stores** : `use{Domain}Store`
- **Tokens** : `--color-{name}`, `--font-{name}`, `--radius-{size}`
- **Classes utilitaires** : `.rpg-{component}`

---

## Checklist nouveau composant

- [ ] Tokens `--color-*` (pas de hex en dur)
- [ ] Polices via `--font-display / serif / body / mono`
- [ ] Classes `.rpg-*` réutilisées si applicable
- [ ] Titres Cinzel uppercase avec letter-spacing
- [ ] Récit Fraunces avec `text-wrap: pretty` et `line-height: 1.65`
- [ ] Stats/chiffres JetBrains Mono
- [ ] Accents sémantiques : ember=joueur, arcane=IA, blood=danger, teal=allié/succès, gold=sélection
- [ ] Bordures via `--color-border` ou `--color-border-strong`
- [ ] Hiérarchie de fond respectée : `bg` → `bg-elev` → `surface` → `surface-raised`
- [ ] Fonctionne dans le layout flex global (pas de hauteur fixe inutile)
