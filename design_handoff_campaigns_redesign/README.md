# Handoff — Refonte de la partie Campagnes (RpgMaster)

## Vue d'ensemble

Refonte visuelle complète de l'écran **Campagnes** de RpgMaster, dans la **direction 3 (audacieuse / éditoriale)** déjà validée pour le reste de l'app (Lobby, Fiche de personnage, Session de jeu, Combat, Dialogues).

Cet écran est élargi pour devenir un **hub de campagne** : au lieu d'une simple liste avec un panneau de sessions, la campagne devient le point d'entrée vers tout son contenu — sessions, arc narratif, notes du MJ, et accès rapide au **Journal de quêtes**, au **Journal du chroniqueur** et au **Carnet d'aventure**.

## À propos des fichiers de design

Les fichiers livrés dans ce bundle sont des **références de design écrites en HTML/React (Babel inline)** — ce sont des prototypes qui montrent l'intention visuelle et comportementale, **pas du code de production à copier-coller**.

La tâche est de **réimplémenter ces écrans dans la codebase cible** (l'app RpgMaster est en **Vue 3** côté frontend — voir `patch/src/views/LobbyView.vue` du repo principal pour la convention) en utilisant ses patterns établis : composants Vue SFC, classes Tailwind, tokens CSS dans `assets/main.css`.

## Fidélité

**Hi-fi.** Couleurs, typographies, tailles et espacements sont définitifs. Le développeur doit reproduire pixel-perfect. Toutes les valeurs exactes sont listées dans la section *Design tokens* ci-dessous.

---

## Écrans livrés

Le prototype `preview.html` empile les **4 états** de la vue :

### 1. Liste + détail (onglet Sessions actif)
**Layout** : `1440 × 900`, en-tête `RPGMASTER` 56px en haut, body en `flex` 2 colonnes.
- **Gauche (flex:1)** : titre de page `Campagnes` + tagline + CTA "Forger une campagne", puis liste de cards de campagnes en colonne (gap 10px, padding latéral 56px).
- **Droite (380–580px fixe)** : panneau de détail de la campagne sélectionnée, avec `borderLeft: 1px solid rgba(255,235,180,0.07)` et fond `linear-gradient(180deg, #181623, #0e0d14)`.

### 2. Détail — onglet Scénario
Même layout, l'onglet **Scénario** est actif côté droit. Affiche une **timeline verticale** des chapitres avec 3 états (`done`, `active`, `planned`), chacun avec un dot numéroté (numérotation romaine I–VI), un titre, un statut chip et un summary en `Fraunces` italique.

### 3. Détail — onglet Notes du MJ
Onglet **Notes du MJ** actif : affiche un **synopsis** dans une card, des **chips de tonalités** (Dark fantasy, Mystère, Politique, Exploration, Combat tactique) en `arcane (#c090ff)`, et un **mémo privé** stylé comme une citation italique (guillemet `"` en gros décoratif).

### 4. Modale — Nouvelle campagne
Modale 560px de large, centrée, par-dessus la liste assombrie (`opacity: 0.4`). Backdrop `rgba(8,6,12,0.7)` avec `backdrop-filter: blur(6px)`. Champs : nom (input), description (textarea), tonalités (chips multi-sélectionnables max 3). Footer : Annuler / Forger.

---

## Composants détaillés

### `CampaignShellD3` (chrome partagé)
- **Header 56px** : logo carré 32px gradient ember→gold, titre `RPGMASTER` Cinzel 15px wt700 ls1, breadcrumbs `Lobby › Campagnes`, à droite : NavPills (Lobby, **Campagnes** active, Admin), séparateur, indicateur "EN LIGNE" avec dot vert glow, bouton "← Lobby" outline.
- **Body** : fond `radial-gradient(ellipse at top, #1a1630 0%, #0e0d14 60%)` + overlay grille `radial-gradient(circle at 1px 1px, rgba(255,235,180,0.025) 1px, transparent 0)` `24px × 24px`.

### `CampaignsHeader`
- Eyebrow `✦ VOS CHRONIQUES` ember 10px wt700 ls3 uppercase
- H1 `Campagnes` Cinzel 44px wt700 ls1 lh1.05
- Tagline Fraunces 15px italic textSoft, max-width 620px
- À droite : un seul CTA `✦ Forger une campagne` gradient ember→gold, padding 10×22, Cinzel 12px ls1.2 uppercase, shadow ember
- Glow décoratif radial ember 280×200 en top-left

### `CampaignCard` (dans la liste)
- Padding `16px 18px`, fond `#1f1c2e` (ou gradient ember-tinted si selected), border 1px `#border` ou `#ff8247` si selected, radius 10px
- Si sélectionnée : bande verticale gauche 3px gradient ember→gold + box-shadow ember
- Header : nom en Cinzel 17 wt700 + sous-ligne "✦ Chapitre {num} — {title}" en Fraunces italic muted
- **Barre de progression** 4px : remplissage proportionnel `chaptersDone/total`, gradient `goldDeep → ember`
- Sous-ligne mono : `{done} / {total} chapitres` … `{updated}`
- **Chip row** : sessions, persos, quêtes (gold si > 0), PNJ — chaque chip mono 10px, border 1px, padding 3×8

### `CampaignDetail` (panneau droit)
- **Hero** : eyebrow `✦ CAMPAGNE SÉLECTIONNÉE`, h2 Cinzel 28, tagline Fraunces 13 italic, glow ember en top-right
- **DetailStat row** : 4 stats côte à côte (Sessions, Persos, Quêtes, Chronique) — chaque stat en card sombre 8×10 padding, label uppercase 9px, valeur Cinzel 22 colorée selon la stat, sub mono 9px
- **Tabs** : 3 onglets sous bordure (`Sessions ◆`, `Scénario ✦`, `Notes du MJ ❦`) — Cinzel 11 ls1.2 uppercase, soulignés ember 2px quand actifs
- **Tab content** scrollable (overflow-y auto)
- **Codex footer toujours visible** : 3 cards d'accès rapide en grid 1fr 1fr 1fr, chacune avec : icône colorée, compteur mono large, label Cinzel, sub small. Tones : gold (Journal de quêtes), arcane (Journal du chroniqueur), teal (Carnet d'aventure)

### `SessionsTab`
- Liste de session-rows : numéro avatar 32px (gradient ember→gold si active, sinon noir), titre `Session {n}` + chip ACTIVE éventuelle, sous-ligne chapitre Fraunces italic, hash mono à droite
- 2 CTA en bas : `▶ Jouer la session courante` (primary ember→gold) puis `→ Session suivante (transférer personnages)` (arcane outline)

### `ArcTab` (timeline)
- Ligne verticale 1px `linear-gradient(180deg, #borderStrong, #border 50%, transparent)` à `left: 13px`
- Pour chaque chapitre : dot numéroté 28px (gradient ember→gold si active avec glow, sinon surface) + card avec titre, chip de statut, compteur sessions, summary Fraunces 12 lh1.5
- Bouton `+ Ajouter un chapitre` en dashed outline en bas

### `NotesTab`
- Section **Synopsis** : card surface, paragraphe Fraunces 13 lh1.6
- Section **Tonalités** : chips arcane rounded-full
- Section **Mémo privé** : card bgElev avec border plus marquée, gros guillemet typographique gold `"` en absolute top-left, contenu italique Fraunces 13 textSoft
- Footer 2 boutons : `Éditer` (gold outline) / `Supprimer la campagne` (rouge outline diluée)

### `NewCampaignModal`
- Largeur 560px, padding 28px, radius 14px, fond `linear-gradient(180deg, #181623, #0e0d14)`, border 1px borderStrong, shadow `0 24px 80px rgba(0,0,0,0.6)` + inset gold subtil
- Glow ember radial top-right 240×240
- Eyebrow `✦ FORGER UNE NOUVELLE CHRONIQUE` ember
- H2 `Nouvelle campagne` Cinzel 28
- Champs : input nom Fraunces 16, textarea description Fraunces 14 (3 rows), section "Tonalités max 3" en chips arcane
- Footer : `Annuler` outline + `⚔ Forger` gradient ember→gold

---

## Comportements & interactions

- **Sélection d'une campagne** → met à jour le panneau droit, conserve l'onglet actif si possible (sinon retombe sur `Sessions`)
- **Onglets** : changement instantané, pas de transition
- **Hover** sur les cards : pas de variation lourde, juste cursor pointer (le selected state est marqué)
- **Modale** :
  - Backdrop click → close
  - `Esc` → close
  - Champ nom requis (validation client minimale)
  - Tonalités : sélection multi, max 3 simultanées
- **Codex footer** : chaque card est un `<button>` qui navigue vers la vue dédiée (à brancher quand les routes existeront — pour l'instant, no-op)
- **Bouton "Session suivante (transférer personnages)"** : ouvre une confirmation (le pattern de dialog est déjà défini dans `direction3-dialogs.jsx` du repo principal — réutiliser le `DlgArcane` ou `DlgWarning`)

## State management

État local minimal (rien à persister en plus de ce qui existe déjà côté backend) :
- `selectedCampaignId: string` — campagne mise en avant dans le panneau droit
- `activeTab: 'sessions' | 'arc' | 'notes'` — onglet actif du panneau de détail
- `showNewModal: boolean` — visibilité de la modale

Les données backend doivent fournir, par campagne :
```ts
{
  id: string,
  name: string,
  tagline?: string,           // une ligne sous le titre
  description?: string,       // synopsis (onglet Notes)
  sessions: number,           // nombre de sessions
  activeSession: number,      // index 1-based de la session active
  chars: number,              // nb de PJ
  quests: { active: number, done: number, rumors: number },
  journal: { entries: number },           // journal du chroniqueur
  chronicler: { npcs: number, places: number },  // carnet d'aventure
  updated: string,            // "DD/MM/YY HH:MM"
  arc: Array<{                // chapitres
    id: string,
    num: string,              // numérotation romaine "I", "II", …
    title: string,
    state: 'done' | 'active' | 'planned',
    sessions: number,
    summary: string,
  }>,
  // À ajouter côté backend :
  tones?: string[],            // tonalités (ex: ["Dark fantasy", "Mystère"])
  privateNotes?: string,       // mémo privé du MJ
}
```

---

## Design tokens (direction 3)

```css
/* fonds */
--bg:            #0e0d14;
--bg-elev:       #181623;
--surface:       #1f1c2e;
--surface-raised:#2a2640;

/* bordures */
--border:        rgba(255,235,180,0.07);
--border-strong: rgba(255,235,180,0.18);

/* texte */
--text:      #f7ecd0;
--text-soft: rgba(247,236,208,0.75);
--text-muted:rgba(247,236,208,0.50);
--text-dim:  rgba(247,236,208,0.32);

/* accents */
--gold:      #f0c764;
--gold-deep: #b88a2a;
--ember:     #ff8247;   /* accent signature D3 */
--blood:     #e84545;
--arcane:    #c090ff;
--teal:      #4fd8c0;
--green:     #6fd96f;

/* gradient signature */
--grad-primary: linear-gradient(135deg, #ff8247, #f0c764);

/* ombres */
--shadow-card-active: 0 0 24px rgba(255,130,71,0.15);
--shadow-cta:         0 2px 12px rgba(255,130,71,0.3);
--shadow-modal:       0 24px 80px rgba(0,0,0,0.6);

/* radii */
--r-sm: 4px;
--r:    8px;
--r-md: 10px;
--r-lg: 14px;
```

### Typographies
- **Cinzel** (titres, labels, CTA) — wt 500/600/700, ls 0.5–3 selon usage
- **Fraunces** (prose, taglines, synopsis, summaries) — wt 400/500, italic fréquent
- **Inter** (UI, body) — wt 400/500/600/700
- **JetBrains Mono** (compteurs, hashes, dates)

### Échelle typographique utilisée
| Usage | Famille | Taille | Poids | LS |
|---|---|---|---|---|
| Page H1 | Cinzel | 44 | 700 | 1 |
| Détail H2 | Cinzel | 28 | 700 | 0.5 |
| Modale H2 | Cinzel | 28 | 700 | 0.5 |
| Card titre | Cinzel | 17 | 700 | 0.5 |
| Onglet | Cinzel | 11 | 700 | 1.2 |
| Eyebrow | Cinzel | 10 | 700 | 3 |
| Stat valeur | Cinzel | 22 | 700 | — |
| Tagline / synopsis | Fraunces (italic) | 13–15 | 400 | — |
| Compteur | JetBrains Mono | 16 | 700 | — |

### Spacing
Pas de scale stricte — paddings courants : `4 / 6 / 8 / 10 / 12 / 14 / 16 / 18 / 20 / 24 / 28 / 32 / 40 / 56`. Gap entre cards de campagne : `10`. Padding latéral page : `56`.

---

## Assets

Aucun asset bitmap. Toutes les "icônes" sont des **glyphes Unicode** (`✦ ◆ ◷ ◉ ❦ ⚔ ☽ ▶ →`). Si la codebase a une lib d'icônes plus riche (Lucide, Phosphor), libre au dev de remplacer en gardant la **même tonalité graphique** (étoiles à 4 branches, losanges, plumes).

Polices : Google Fonts (Cinzel, Fraunces, Inter, JetBrains Mono) — déjà chargées dans `index.html` du repo, ne pas dupliquer.

---

## Fichiers livrés dans ce bundle

| Fichier | Rôle |
|---|---|
| `direction3-campaigns.jsx` | **Source de référence** — tous les composants de la vue, hi-fi |
| `data.js` | Mock data partagé (personnages, narrative log) — pour faire tourner le preview |
| `preview.html` | Preview standalone — ouvrir dans un navigateur, empile les 4 états dans une page scrollable |
| `README.md` | Ce document |

## Pour ouvrir le preview

```bash
cd design_handoff_campaigns_redesign
python3 -m http.server 8000
# puis ouvrir http://localhost:8000/preview.html
```

(ou n'importe quel serveur statique — le fichier ne marche pas en `file://` à cause des modules)

---

## Cohérence avec les autres écrans déjà refondus

Cet écran réutilise **strictement les mêmes tokens et patterns** que les écrans déjà livrés en direction 3 :
- `LobbyD3` (style des cards, panneau droit, chrome)
- `CharacterSheetD3` (style des stats, des sections, du hero)
- `Direction3` session de jeu (composer, party bar)
- `CombatViewD3` (battlemap, tracker)
- `DlgDanger / DlgWarning / DlgArcane` (dialogues)

→ Le dev doit donc factoriser au maximum (composants `Eyebrow`, `Section`, `StatCard`, `NavPill`, `CampaignChrome`) plutôt que dupliquer.
