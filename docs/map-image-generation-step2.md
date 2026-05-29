# Step 2 — Génération image IA pour cartes majeures

La V1 des cartes reste procédurale, déterministe et entièrement rendue en SVG/Vue.
Une future V2 pourra ajouter un rendu bitmap IA pour les lieux importants sans
remplacer les données structurées.

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
