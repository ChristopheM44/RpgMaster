# Handoff : Grimoire & Bestiaire — Vues Sorts et Monstres

## Aperçu

Deux vues pour la bibliothèque de RPGMaster :
- **Grimoire** (`/grimoire`) — catalogue complet des sorts D&D 5e avec recherche multi-critères et fiche détaillée
- **Bestiaire** (`/bestiaire`) — catalogue complet des monstres D&D 5e avec recherche multi-critères et bloc de stats complet

Les deux vues partagent le même layout **liste/détail** en deux colonnes.

## À propos des fichiers de design

Les fichiers dans `reference/` sont des **prototypes HTML/React** montrant le rendu visuel et le comportement attendus. Ils ne sont pas du code de production. La tâche est de **recréer ces designs en Vue 3 + Tailwind CSS v4 + Pinia** dans le codebase existant, en suivant les patterns et composants `.rpg-*` déjà en place.

## Fidélité

**High-fidelity (hifi)** — Les maquettes utilisent les tokens exacts du design system Direction 3. Le développeur doit les reproduire au pixel près en utilisant les classes et tokens existants.

---

## Architecture des fichiers

```
frontend/src/
├── types/
│   └── library.ts                    ← Types Spell & Monster
├── stores/
│   ├── useSpellStore.ts              ← État + filtres + actions sorts
│   └── useMonsterStore.ts            ← État + filtres + actions monstres
├── components/
│   ├── common/
│   │   └── ListDetailLayout.vue      ← Layout partagé 2 colonnes
│   ├── spells/
│   │   ├── SpellListItem.vue         ← Item de liste sort
│   │   ├── SpellDetail.vue           ← Panneau détail sort
│   │   └── SpellFilters.vue          ← Barre de filtres sort
│   └── monsters/
│       ├── MonsterListItem.vue       ← Item de liste monstre
│       ├── MonsterDetail.vue         ← Panneau détail monstre
│       ├── MonsterFilters.vue        ← Barre de filtres monstre
│       └── AbilityBlock.vue          ← Bloc 6 caractéristiques
├── views/
│   ├── SpellsView.vue                ← Page /grimoire
│   └── MonstersView.vue              ← Page /bestiaire
└── router.ts                          ← Ajouter les 2 routes
```

---

## Configuration du routeur

```ts
// Ajouter dans router.ts
{
  path: '/grimoire',
  name: 'grimoire',
  component: () => import('@/views/SpellsView.vue'),
  meta: { title: 'Grimoire' },
},
{
  path: '/bestiaire',
  name: 'bestiaire',
  component: () => import('@/views/MonstersView.vue'),
  meta: { title: 'Bestiaire' },
},
```

## Navigation header

Ajouter dans `AppNav.vue` deux NavPills dans la section breadcrumbs :

| Pill | Route | Icône |
|---|---|---|
| Grimoire | `/grimoire` | ✦ |
| Bestiaire | `/bestiaire` | ◆ |

Style actif : `background: rgba(240,199,100,0.10)`, `border: 1px solid rgba(240,199,100,0.30)`, `color: var(--color-gold)`.

---

## Layout partagé : ListDetailLayout

Structure deux colonnes réutilisée par les deux vues.

```
┌──────────────────────────────────────────────┐
│ Sidebar (360px)         │ Detail (flex-1)    │
│ ┌────────────────────┐  │                    │
│ │ slot #header       │  │ slot #detail       │
│ │ (search + filtres) │  │ (fiche complète    │
│ ├────────────────────┤  │  ou état vide)     │
│ │ slot #list         │  │                    │
│ │ (scroll interne)   │  │                    │
│ └────────────────────┘  │                    │
└──────────────────────────────────────────────┘
```

| Propriété | Valeur |
|---|---|
| Sidebar width | `360px`, `flex-shrink: 0` |
| Sidebar background | `var(--color-bg-elev)` |
| Séparateur | `border-right: 1px solid var(--color-border)` |
| Detail panel | `flex: 1`, `overflow-y: auto` |
| Detail padding | `32px 40px 40px` |

---

## Vue 1 : Grimoire (Sorts)

### Filtres disponibles

| Filtre | Type | Options |
|---|---|---|
| Recherche | `<input>` texte | Filtre sur `name` (insensible à la casse) |
| Niveau | `<select>` | 0 (Cantrip), 1–9 |
| École | `<select>` | Abjuration, Conjuration, Divination, Enchantement, Évocation, Illusion, Nécromancie, Transmutation |
| Classe | `<select>` | Barde, Clerc, Druide, Ensorceleur, Magicien, Occultiste, Paladin, Rôdeur |
| Concentration | Toggle chip | `boolean` |
| Rituel | Toggle chip | `boolean` |

**Layout filtres :** search pleine largeur, puis une rangée de 3 `<select>` en `flex` avec `gap: 6px`, puis une rangée avec les 2 toggle chips + lien "Effacer" aligné à droite.

### Item de liste sort

```
[●] Bouclier                           [Niv.1]
    Abjuration · ◉ C
```

| Élément | Style |
|---|---|
| Dot (●) | `8×8px`, `border-radius: 50%`, couleur = `SCHOOL_COLORS[school]`, `box-shadow: 0 0 6px {color}50` |
| Nom | `font-display`, `13px`, `wt700`, `letter-spacing: 0.03em` |
| Metadata | `10px`, `color: text-muted` |
| Badge Concentration | `◉ C` en `color: gold`, `wt600` |
| Badge Rituel | `◈ R` en `color: arcane`, `wt600` |
| Badge niveau | `font-mono`, `10px wt700`, fond coloré 12% + border 40% |
| État sélectionné | `background: surface-raised`, `border-left: 3px solid {schoolColor}`, `box-shadow: shadow-card-active` |
| Séparateur | `border-bottom: 1px solid var(--color-border)` |

### Groupement

Items groupés par niveau. En-tête de groupe :
- `font-display`, `10px wt700`, `letter-spacing: 0.15em`, uppercase
- `background: rgba(0,0,0,0.15)`, `border-bottom`
- Compteur en `font-mono 9px`

### Détail sort

| Section | Détails |
|---|---|
| **Titre** | `✦` en couleur école + nom en `font-display 28px wt700 uppercase`, `letter-spacing: 0.04em` |
| **Sous-titre** | Chip école (fond 15% + border 30%) + `font-display 13px` "Niveau X" |
| **Grille stats** | 2×2 grid (`grid-template-columns: 1fr 1fr`), `gap: 1px`, fond `var(--color-border)`, cellules `background: surface`. Labels en `font-display 9px wt700 uppercase dim`, valeurs en `font-body 13px wt500` |
| **Cellules** | Incantation, Portée, Composantes (V/S/M), Durée |
| **Matériel** | Si `components.M` non null : encart `background: rgba(0,0,0,0.2)`, `border`, `font-serif italic 12px` |
| **Tags** | Chips Concentration (gold), Rituel (arcane), Type de dégâts (ember) — `padding: 4px 10px`, `radius-sm`, `10px wt700 uppercase` |
| **Description** | `font-serif 15px`, `line-height: 1.7`, `color: parchment-dark`, `text-wrap: pretty` |
| **Niveaux supérieurs** | Si non null : `font-serif 14px italic`, `line-height: 1.65` |
| **Classes** | Chips `font-body 11px wt600`, `background: surface`, `border` |
| **Source** | `font-mono 10px`, `color: text-dim`, séparé par `border-top` |

### État vide (aucune sélection)

Centré vertical + horizontal : symbole `✦` en `48px opacity 0.15` + texte `font-display 14px uppercase letter-spacing 0.1em` "Sélectionnez un sort".

---

## Vue 2 : Bestiaire (Monstres)

### Filtres disponibles

| Filtre | Type | Options |
|---|---|---|
| Recherche | `<input>` texte | Filtre sur `name` |
| FP (Facteur de puissance) | `<select>` | Valeurs dynamiques depuis les données |
| Type | `<select>` | Aberration, Bête, Céleste, Constructe, Dragon, Élémentaire, Fée, Fiélon, Géant, Humanoïde, Monstruosité, Mort-vivant, Plante, Vase |
| Taille | `<select>` | Très petit, Petit, Moyen, Grand, Très grand, Gigantesque |

### Item de liste monstre

```
[●] Gobelin                           [FP 1/4]
    Humanoïde · Petit
```

Même structure que l'item sort, avec `TYPE_COLORS[type]` au lieu de `SCHOOL_COLORS`.

### Groupement

Items groupés par FP. Tri par `crToNum()` croissant. En-tête : `FP {value}`.

### Détail monstre

| Section | Détails |
|---|---|
| **Titre** | `◆` en couleur type + nom `font-display 28px wt700 uppercase` |
| **Sous-titre** | `font-serif 13px italic` : "{Type} ({sous-type}) de taille {taille}, {alignement}" |
| **Stats principaux** | Grid 3 colonnes (`1fr 1fr 1fr`), gap 1px : **CA** (mono 22px + type en 10px), **PV** (mono 22px + dés en mono 10px), **Vitesse** (liste clé/valeur) |
| **Caractéristiques** | Grid 6 colonnes, chaque cellule : label `font-display 9px wt700 dim`, valeur `font-mono 18px wt700`, modificateur `font-mono 11px muted` |
| **Info lines** | Rangées `label (11px wt600 uppercase muted, width 140px) : valeur (12px parchment-dark)`, séparées par `border-bottom` |
| **Lignes affichées** | Jets de sauvegarde, Compétences, Résistances, Immunités (dégâts), Immunités (conditions), Sens, Langues |
| **Facteur de puissance** | Ligne spéciale : FP en `font-mono 14px wt700` + XP en `font-mono 11px muted`, formaté `fr-FR` |
| **Capacités** | Section avec `SectionHeader` + blocs nom/description. Nom en `font-display 13px wt700`, desc en `font-serif 13px lh1.65 parchment-dark` |
| **Actions** | Même format que Capacités |
| **Réactions** | Idem, si non null |
| **Actions légendaires** | Idem, si non null |
| **Environnement** | Chips `font-body 11px wt600`, `background: surface` |
| **Source** | `font-mono 10px dim`, `border-top` |

---

## Couleurs sémantiques

### Écoles de magie → `SCHOOL_COLORS`

| École | Hex | Token proche |
|---|---|---|
| Abjuration | `#4fd8c0` | `--color-teal` |
| Conjuration | `#6fd96f` | `--color-green` |
| Divination | `#f0c764` | `--color-gold` |
| Enchantement | `#c090ff` | `--color-arcane` |
| Évocation | `#ff8247` | `--color-ember` |
| Illusion | `#7eb8ff` | bleu clair custom |
| Nécromancie | `#e84545` | `--color-blood` |
| Transmutation | `#b88a2a` | `--color-gold-deep` |

### Types de monstres → `TYPE_COLORS`

| Type | Hex | Token proche |
|---|---|---|
| Aberration | `#c090ff` | `--color-arcane` |
| Bête | `#6fd96f` | `--color-green` |
| Céleste | `#f0c764` | `--color-gold` |
| Constructe | `#6b6580` | `--color-dim` |
| Dragon | `#ff8247` | `--color-ember` |
| Élémentaire | `#4fd8c0` | `--color-teal` |
| Fée | `#c090ff` | `--color-arcane` |
| Fiélon | `#e84545` | `--color-blood` |
| Géant | `#b88a2a` | `--color-gold-deep` |
| Humanoïde | `#f7ecd0` | `--color-parchment` |
| Monstruosité | `#ff8247` | `--color-ember` |
| Mort-vivant | `#e84545` | `--color-blood` |
| Plante | `#6fd96f` | `--color-green` |
| Vase | `#4fd8c0` | `--color-teal` |

---

## Composants CSS à ajouter dans `main.css`

```css
/* Select sombre pour filtres */
.rpg-mini-select {
  background: rgba(0,0,0,0.35);
  border: 1px solid var(--color-border-strong);
  border-radius: var(--radius-md);
  color: var(--color-parchment);
  padding: 5px 8px;
  font-size: 11px;
  font-family: var(--font-body);
  outline: none;
  cursor: pointer;
}
.rpg-mini-select:focus {
  border-color: var(--color-ember);
  box-shadow: 0 0 0 2px rgba(255,130,71,0.15);
}
.rpg-mini-select option {
  background: var(--color-surface);
  color: var(--color-parchment);
}

/* Toggle chip (filtre booléen) */
.rpg-toggle-chip {
  padding: 3px 10px;
  border-radius: var(--radius-sm);
  font-size: 10px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  border: 1px solid var(--color-border);
  background: transparent;
  color: var(--color-text-muted);
  cursor: pointer;
  transition: all 120ms ease;
}
.rpg-toggle-chip.active {
  border-color: var(--color-gold);
  background: rgba(240,199,100,0.12);
  color: var(--color-gold);
}
.rpg-toggle-chip.active.arcane {
  border-color: var(--color-arcane);
  background: rgba(192,144,255,0.12);
  color: var(--color-arcane);
}

/* En-tête de groupe dans les listes */
.rpg-group-header {
  padding: 10px 14px 6px;
  font-size: 10px;
  font-weight: 700;
  font-family: var(--font-display);
  letter-spacing: 0.15em;
  text-transform: uppercase;
  color: var(--color-text-dim);
  background: rgba(0,0,0,0.15);
  border-bottom: 1px solid var(--color-border);
}

/* Section header avec filet dégradé */
.rpg-detail-section {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}
.rpg-detail-section span {
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--color-text-muted);
  white-space: nowrap;
}
.rpg-detail-section::after {
  content: '';
  flex: 1;
  height: 1px;
  background: linear-gradient(90deg, var(--color-border-strong), transparent);
}

/* Ligne info label:valeur */
.rpg-info-line {
  display: flex;
  align-items: baseline;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px solid var(--color-border);
}
.rpg-info-line-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-text-muted);
  text-transform: uppercase;
  letter-spacing: 0.08em;
  width: 140px;
  flex-shrink: 0;
}
.rpg-info-line-value {
  font-size: 12px;
  color: var(--color-parchment-dark);
}
```

---

## Interactions

| Interaction | Comportement |
|---|---|
| Clic item liste | Sélectionne l'item, affiche le détail, highlight dans la liste |
| Recherche | Filtrage instantané (computed), pas de debounce nécessaire |
| Changement filtre | Filtrage instantané, la liste se regroupe dynamiquement |
| Toggle chip | Active/désactive le filtre booléen |
| "Effacer" | Reset tous les filtres + search à leur état initial |
| Navigation Grimoire ↔ Bestiaire | Via NavPills dans le header, changement de route |
| Hover item liste | `filter: brightness(1.08)` — transition 120ms |

## State Management

Chaque store gère :
- `items: Ref<Spell[]|Monster[]>` — données brutes (fetch API ou import JSON)
- Filtres individuels : `search`, `levelFilter`/`crFilter`, `schoolFilter`/`typeFilter`, etc.
- `selectedId: Ref<string|null>` — item actuellement sélectionné
- `filtered: ComputedRef` — items après application de tous les filtres
- `grouped: ComputedRef` — items groupés par niveau/FP
- `selected: ComputedRef` — item sélectionné résolu
- `clearFilters()` — action de reset

Les filtres sont **persistés dans le store Pinia** (pas en localStorage) pour survivre à la navigation entre vues.

Optionnel : synchroniser `selectedId` dans le query string (`?spell=bouclier`) via `useRoute`/`useRouter` pour rendre les fiches partageables.

---

## Fichiers de référence

| Fichier | Description |
|---|---|
| `reference/Grimoire & Bestiaire.html` | Prototype HTML complet |
| `reference/grimoire/data.js` | Données mock (sorts + monstres) |
| `reference/grimoire/spells-view.jsx` | Composant React — vue sorts |
| `reference/grimoire/monsters-view.jsx` | Composant React — vue monstres |
| `reference/grimoire/app.jsx` | Shell + navigation |
