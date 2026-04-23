# Patch Direction 3 — Audacieuse / Éditoriale

Ce patch applique la **direction audacieuse** (ember + gold sur fonds obsidienne,
typographie éditoriale Fraunces/Cinzel/Inter/JetBrains Mono) aux vues
principales de RpgMaster.

## Contenu

```
patch/
├── index.html                                     ← polices Google Fonts
└── src/
    ├── assets/main.css                            ← tokens + helpers .rpg-*
    ├── components/common/AppNav.vue               ← barre de nav restylée
    └── views/
        ├── LobbyView.vue                          ← hero + liste + aside détail
        ├── CharacterSheetView.vue                 ← fiche PJ restylée
        └── GameSessionView.vue                    ← table de jeu restylée
```

## Installation

1. Copier les fichiers de `patch/` vers `frontend/` en conservant les chemins
   (ils remplacent des fichiers existants).
2. Vérifier que Tailwind v4 prend bien en compte le nouveau `@theme` dans
   `src/assets/main.css` — pas de `tailwind.config.js` à modifier, les tokens
   `--color-*`, `--font-*`, `--radius-*` deviennent automatiquement des
   utilitaires (`bg-ember`, `text-parchment`, `font-display`, `rounded-lg`…).
3. Redémarrer le serveur Vite : `npm run dev`.

## Compatibilité

Les tokens historiques `--color-ink`, `--color-stone`, `--color-parchment`,
`--color-gold`, `--color-arcane`, `--color-blood`, `--color-forest` sont
**conservés** (remappés sur la nouvelle palette). Les composants qui ne sont
pas dans ce patch (NarrativeLog, CombatTracker, TacticalGrid, ActionBar,
CharacterSummary, SaveLoadPanel, AdventureStartModal) continueront à
fonctionner — ils hériteront juste de la nouvelle palette via les tokens.

Pour les repasser complètement sur le nouveau système, réutiliser les classes
`.rpg-card`, `.rpg-eyebrow`, `.rpg-section-title`, `.rpg-btn-primary`,
`.rpg-btn-secondary`, `.rpg-btn-tonal`, `.rpg-input`, `.rpg-chip`.

## Tokens clés

| Token                 | Valeur       | Usage                         |
|-----------------------|--------------|-------------------------------|
| `--color-bg`          | `#0e0d14`    | Fond app                      |
| `--color-bg-elev`     | `#181623`    | Top bar, aside                |
| `--color-surface`     | `#1f1c2e`    | Cartes, chips                 |
| `--color-ember`       | `#ff8247`    | Accent chaud signature        |
| `--color-gold`        | `#f0c764`    | CTA, titres forts             |
| `--color-parchment`   | `#f7ecd0`    | Texte principal               |
| `--font-display`      | Cinzel       | Titres héroïques              |
| `--font-serif`        | Fraunces     | Récit, citations              |
| `--font-body`         | Inter        | UI                            |
| `--font-mono`         | JetBrains    | Chiffres, stats               |

## Notes de migration

- Le récit (`NarrativeLog`) gagnera beaucoup à être passé en `font-serif`
  (Fraunces) avec la classe utilitaire `.prose-narrative`.
- Les boutons d'action (`ActionBar`) peuvent être migrés vers `.rpg-btn-tonal`
  + tonalités (`tone-blood` pour attaque, `tone-arcane` pour sort, etc.).
- Les tokens `--narrative-scale` et `--density` peuvent être pilotés par un
  store Pinia si l'on veut exposer les Tweaks en production.
