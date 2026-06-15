# Step 2 — Génération image IA pour cartes majeures

> **Statut (2026-06)** : implémenté de bout en bout (backend + frontend),
> mais **désactivé par défaut** (`image_generation_enabled=False`, aucun
> provider configuré). Voir `docs/decision-couche-visuelle-piste-e-2026-06.md`
> pour l'analyse et la recommandation. Le contenu ci-dessous décrit le design
> tel qu'implémenté.

La V1 des cartes reste procédurale, déterministe et entièrement rendue en SVG/Vue.
La V2 ajoute un rendu bitmap IA optionnel pour les lieux importants, en
complément des données structurées (jamais en remplacement).

## Principe

- Conserver `current_scene`, `region_map` et `city_maps` comme sources de vérité.
- Ajouter plus tard un champ optionnel non bloquant, par exemple
  `visual_asset: { provider: "image_ai", url: "...", prompt_hash: "..." }`.
- Utiliser l’image comme fond inspectable, jamais comme unique représentation du gameplay.
- Garder les POI, sorties, positions et statuts rendus par-dessus en SVG/HTML.
- Revenir automatiquement au rendu procédural si l’image est absente, lente ou incohérente.

## Critères Avant Implémentation

- Les thèmes (`scene_theme`) et décors procéduraux doivent déjà être cohérents.
- Le prompt image doit être dérivé du journal, de la scène canonique et du biome validé.
- Aucun secret MJ ne doit être envoyé à un provider externe pour générer une image visible.
