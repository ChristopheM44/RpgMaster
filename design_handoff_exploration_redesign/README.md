# Handoff — Refonte de l'écran Exploration (RPGMaster)

## Vue d'ensemble

Cette refonte cible l'écran **Exploration** d'un MJ virtuel D&D (Vue 3 + Pinia + TS). L'écran actuel souffre de **trois zones redondantes** :

1. Un bloc « ⚔ Combat — Hors combat / Déclencher une rencontre » dans le panneau droit, alors qu'un écran Combat dédié existe déjà.
2. Une barre d'actions en bas qui affiche **Attaquer / Foncer / Fin du tour** hors combat.
3. Une **PartyBar** en bas qui duplique le panneau droit.

L'objectif est de **rendre la place du panneau droit au groupe + quêtes + mémoire**, de **retirer la PartyBar du bas**, et de **remplacer la barre d'actions de combat** par des suggestions contextuelles ou un set utilitaire (Sort de rituel / Objet / Repos court).

5 directions sont proposées (A → E). **La direction retenue par le designer est la C — « Carnet d'aventure »** ; les autres sont fournies pour référence.

---

## À propos des fichiers de ce dossier

Les fichiers contenus ici sont **des références de design réalisées en HTML/React** — des prototypes qui montrent l'apparence et le comportement souhaités. **Ce ne sont pas du code de production à copier directement.**

L'objectif est de **recréer ces designs dans le codebase Vue existant**, en réutilisant ses patterns établis (composants, stores Pinia, classes CSS globales). Le HTML est un prototype rendu en React+Tailwind via CDN — la cible est Vue 3 SFC.

## Fidélité

**Haute fidélité (hifi).** Les couleurs, la typographie, les espacements, les états et les interactions sont définitifs. Recréer pixel-perfect dans Vue, en utilisant les composants et classes CSS déjà présents dans le codebase quand ils existent (`.rpg-eyebrow`, `.rpg-btn-primary`, etc.).

---

## Direction retenue : C — Carnet d'aventure

Le panneau droit devient un **carnet narratif** avec **trois sections repliables** :

1. **Le groupe** — liste compacte des 4 personnages
2. **Quêtes en cours** — principale, secondaires, rumeurs
3. **Carnet du chroniqueur** — PNJ et lieux mémorisés

### Layout d'ensemble (1280 × 820, mais responsive)

```
┌─────────────────────────────────────────────────────────────────┐
│ Header : Phase Exploration · ⚔ Combat · ☽ Repos · 🤖 IA · 💾 · Lobby → │
├──────────────────────────────────┬──────────────────────────────┤
│                                  │  ▼ Le groupe                 │
│   Colonne narrative (gauche)     │     · Thorvald (vous) [🤖][📜]│
│   – Récap MJ                     │     · Oaken     [🤖][📜]      │
│   – Tours joueurs                │     · Sunwing   [🤖][📜]      │
│   – Tours MJ                     │     · Vael      [🤖][📜]      │
│                                  │  ▼ Quêtes en cours           │
│                                  │     · Principale, secondaire │
│                                  │  ▼ Carnet du chroniqueur     │
│                                  │     · PNJ + lieux            │
├──────────────────────────────────┴──────────────────────────────┤
│ Barre d'actions exploration (Sort, Objet, Repos OU suggestions) │
└─────────────────────────────────────────────────────────────────┘
```

### Header (inchangé structurellement)

- À gauche : logo « RPGMaster » + titre de campagne
- Au centre : indicateurs **Phase Exploration**, **⚔ Combat** (bouton — unique point d'entrée pour déclencher une rencontre), **☽ Repos**, **🤖 IA réagit**, **💾 Sauvegarder**
- À droite : indicateur de connexion + **`Lobby →`** (bouton, déplacé à droite pour contrer la lecture latine gauche-droite des actions principales)

### Panneau droit — sections repliables

Chaque section a un header cliquable avec un chevron qui pivote (90° fermé → 0° ouvert, transition `transform 200ms ease`). État stocké dans `localStorage` (`rpg.exploration.collapsed.{group|quests|memory}`).

#### 1. Le groupe (densité = `detailed`, qui est le défaut)

Pour chaque personnage, **une carte** :

- **Avatar 36×36** (rounded-md, dégradé : ember→gold pour humain, arcane→violet pour IA)
- **Nom** (Cinzel 11px, gold pour le perso joué, parchment sinon)
- **Badge `IA`** si contrôlé par l'IA (8px, arcane bold)
- **Classe en français** (Fraunces 9px italic, muted) — `Guerrier`, `Druide`, `Roublard`, `Rôdeur`, `Magicien`, `Clerc`, `Barde`, `Paladin`, `Ensorceleur`, `Occultiste`, `Moine`, `Barbare`
- **Barre PV horizontale 2px** colorée selon ratio (vert > 50%, gold > 25%, blood sinon)
- **PV / CA** en mono 9px : `12/12 · CA 16`
- **Ligne arme + sorts** : `⚔ Épée longue · ✦ 3/4` (sorts uniquement si `spells_left` non null)
- **Boutons d'action à droite** :
  - `🤖` / `👤` — toggle contrôle IA / joueur (call `useCharacterStore().toggleAiControl(id)`)
  - `📜` — ouvrir la fiche complète (route `character-sheet` avec `params.charId`)

En densité `compact`, on retire la ligne arme/sorts et on réduit l'avatar à 28×28.

#### 2. Quêtes en cours

Liste de cartes par quête. Chaque carte :
- **Chip** colorée selon `kind` : `principale` (gold), `secondaire` (teal), `rumeur` (arcane)
- **Titre** Cinzel 13px
- **Description** Fraunces 12px, max 2 lignes (line-clamp)
- **Barre de progression** si `steps` connu : `progress/steps`
- **Échéance** si `due` présent : petit chip avec ⏳

#### 3. Carnet du chroniqueur

Liste plate de PNJ et Lieux récents :
- **Icône** : 👤 PNJ, 📍 Lieu
- **Nom** (Cinzel 12px) + **détail** (Fraunces 11px muted, 1 ligne)
- **Tag** chip à droite : `allié` (green), `neutre` (gold), `danger` (blood), `à explorer` (teal), `sûr` (parchment)

### Barre d'actions du bas (mode exploration)

**Retirer entièrement** : `Attaquer`, `Foncer`, `Fin du tour` — notions de tour qui n'ont aucun sens hors combat.

Le set d'actions est **configurable** (le designer veut tester ; en prod, choisir un défaut). Quatre presets :

- **`minimal`** — *défaut retenu* — uniquement le textarea + envoyer. Aucun raccourci. Mise sur la suggestion narrative libre.
- **`utility`** — `✦ Sort rituel` `🎒 Objet` `☽ Repos court`
- **`contextual`** — suggestions calculées selon la scène : `🗣 Parler à Toben`, `🔍 Fouiller la salle commune`, `🥾 Partir vers les collines`, `📜 Consulter une rumeur`
- **`classic`** — l'ancien set combat (à retirer en prod, gardé pour comparaison dans la maquette)

Le textarea conserve : `placeholder = "Décrivez votre action…"`, 2 lignes, et le **bouton primaire `Envoyer ↵`** à droite.

### PartyBar du bas

**Supprimée.** Le groupe est maintenant à droite. Pas de toggle en prod.

---

## Tokens de design

```css
:root {
  /* Couleurs */
  --color-bg:           #0e0d14;  /* fond global */
  --color-bg-elev:      #181623;  /* header, footer, panneaux */
  --color-surface:      #1f1c2e;  /* cartes */
  --color-surface-raised:#2a2640;
  --color-parchment:    #f7ecd0;  /* texte principal */
  --color-parchment-dark: rgba(247,236,208,0.75);
  --color-text-muted:   rgba(247,236,208,0.50);
  --color-text-dim:     rgba(247,236,208,0.32);
  --color-border:       rgba(255,235,180,0.07);
  --color-border-strong:rgba(255,235,180,0.18);

  /* Accents */
  --color-ember:  #ff8247;  /* primaire / joueur humain */
  --color-gold:   #f0c764;  /* secondaire */
  --color-blood:  #e84545;  /* danger / combat */
  --color-arcane: #c090ff;  /* IA / sorts */
  --color-teal:   #4fd8c0;  /* succès / sûr */
  --color-green:  #6fd96f;  /* PV pleins */

  /* Typo */
  --font-display: "Cinzel", serif;          /* titres, noms */
  --font-serif:   "Fraunces", Georgia, serif; /* narratif, descriptions */
  --font-body:    "Inter", system-ui, sans-serif;
  --font-mono:    "JetBrains Mono", monospace; /* stats */
}
```

### Espacements

Tailwind par défaut (4px base). Les paddings de panneaux sont **20px** (px-5), les gaps internes 8–12px.

### Border radius

- Cartes : `8px` (`rounded-lg`)
- Boutons : `6px`
- Avatars : `6–10px` selon taille
- Chips : `4px`

### Ombres

Une seule, sur le bouton primaire :
```css
box-shadow: 0 2px 12px rgba(255,130,71,0.3);
```

---

## Données

Voir `shared/data.js` pour les formes exactes. Les structures clés :

```ts
type Character = {
  id: string;
  name: string;
  initial: string;
  char_class: 'Fighter' | 'Druid' | 'Rogue' | 'Ranger' | ...; // EN dans les données, FR dans l'UI via mapping
  species: string;
  level: number;
  hp_current: number; hp_max: number; hp_temp: number;
  ac: number; init: number; speed: number;
  is_ai: boolean;
  is_self: boolean;
  abilities: { FOR: { v: number; m: string }, DEX: ..., CON: ..., INT: ..., SAG: ..., CHA: ... };
  equipped: string;          // arme(s) — string libre
  spells_left: string | null; // ex: "3 / 4", null si non lanceur
  conditions: string[];
  accent: 'ember' | 'gold' | 'arcane' | 'green';
};

type Quest = {
  id: string;
  kind: 'principale' | 'secondaire' | 'rumeur';
  title: string;
  desc: string;
  progress: number;
  steps: number | null;
  due?: string;
};

type MemoryEntry = {
  kind: 'PNJ' | 'Lieu';
  name: string;
  detail: string;
  tag: 'allié' | 'neutre' | 'sûr' | 'danger' | 'à explorer';
};
```

Le **mapping classe EN → FR** doit être appliqué côté UI :

```ts
const CLASS_FR: Record<string, string> = {
  Fighter: 'Guerrier', Druid: 'Druide', Rogue: 'Roublard', Ranger: 'Rôdeur',
  Wizard: 'Magicien', Cleric: 'Clerc', Bard: 'Barde', Paladin: 'Paladin',
  Sorcerer: 'Ensorceleur', Warlock: 'Occultiste', Monk: 'Moine', Barbarian: 'Barbare',
};
```

---

## Intégration côté Vue (suggestion d'arborescence)

```
frontend/src/
├── views/
│   └── GameSessionView.vue            # ← supprimer <PartyBar>, ajuster <ActionBar>, déplacer Lobby à droite
├── components/
│   ├── exploration/
│   │   ├── ExplorationLayout.vue      # nouveau : 2 colonnes (narratif + AdventureLogPanel)
│   │   ├── AdventureLogPanel.vue      # NOUVEAU — panneau droit (carnet)
│   │   ├── PartySection.vue           # NOUVEAU — section "Le groupe"
│   │   ├── QuestsSection.vue          # NOUVEAU — section "Quêtes en cours"
│   │   ├── MemorySection.vue          # NOUVEAU — section "Carnet du chroniqueur"
│   │   ├── CollapsibleSection.vue     # NOUVEAU — wrapper repliable + persistence
│   │   └── ExplorationActionBar.vue   # NOUVEAU — barre du bas mode exploration
│   ├── combat/
│   │   └── CombatLayout.vue           # garder l'ancien CharacterPanel ici si besoin
│   └── common/
│       └── ActionBar.vue              # à splitter : ExplorationActionBar vs CombatActionBar
└── stores/
    ├── characterStore.ts              # ajouter toggleAiControl(id) si absent
    ├── questStore.ts                  # créer si absent (mock OK avec TODO)
    └── memoryStore.ts                 # créer si absent (mock OK avec TODO)
```

### Comportements clés à brancher

- Sections repliables : `localStorage.getItem('rpg.exploration.collapsed.<id>')` (`'1'` = fermée)
- Toggle IA : `characterStore.toggleAiControl(id)`
- Ouvrir fiche : `router.push({ name: 'character-sheet', params: { charId: id } })`
- Bouton ⚔ Combat (header) : appelle l'action existante de déclenchement de rencontre
- Bouton Lobby (droite) : `router.push({ name: 'lobby' })`

---

## Fichiers de référence dans ce dossier

| Fichier | Rôle |
|---|---|
| `Refonte Exploration.html` | Document principal — design canvas avec les 5 variations |
| `shared/shell.jsx` | Header + colonne narrative + barre d'actions exploration (réutilisé par toutes) |
| `shared/data.js` | Données mock (party, narrative, quests, memory, suggestions) |
| `variations/var-c-logbook.jsx` | **★ Direction retenue** — panneau Carnet d'aventure |
| `variations/var-a-group.jsx` | A · Tableau de bord groupe (pour référence) |
| `variations/var-b-tabs.jsx` | B · Onglets (pour référence) |
| `variations/var-d-editorial.jsx` | D · Éditoriale (pour référence) |
| `variations/var-e-banner.jsx` | E · Bandeau supérieur (pour référence) |
| `design-canvas.jsx`, `tweaks-panel.jsx` | Chrome de la maquette — non pertinent pour l'intégration |

---

## Comment démarrer côté Claude Code

Dans ton repo, ouvre Claude Code et donne-lui ce prompt :

> Lis `design_handoff_exploration_redesign/README.md` puis intègre la **direction C** dans `frontend/src/components/exploration/`. Crée les composants Vue 3 SFC manquants (`AdventureLogPanel`, `PartySection`, `QuestsSection`, `MemorySection`, `CollapsibleSection`, `ExplorationActionBar`), retire la `PartyBar` du bas dans `GameSessionView.vue`, déplace le bouton `Lobby` à droite, et remplace la barre d'actions de combat par `ExplorationActionBar` en mode `minimal`. Réutilise les classes `.rpg-eyebrow`, `.rpg-btn-primary`, `.rpg-btn-tonal`, `.rpg-input` déjà définies. Pour les quêtes et la mémoire, utilise des données mockées avec un `// TODO: brancher questStore / memoryStore` clair. Demande-moi avant de modifier `CharacterPanel.vue` (à garder pour l'écran Combat).
