# Décision — Couche visuelle (Piste E)

> Suite de `docs/plans/je-voudrais-que-l-on-effervescent-rainbow.md` — Piste E
> ("préparatoire, à rechallenger après A→D"). Ce document est le **livrable de
> Piste E** : il rouvre la question avec des données réelles et tranche, sans
> modifier de code (conformément à "Ne pas implémenter maintenant").

## Constat corrigé

Le constat initial du plan ("un hook image existe déjà, optionnel") était
**sous-estimé**. État réel au 2026-06-15 :

- **Option 2 (`visual_asset` / API image) est déjà implémentée de bout en
  bout**, pas seulement "câblée" :
  - Backend : prompts publics construits depuis `SceneSpec`/cartes
    (`local_map_service.build_scene_visual_asset`,
    `build_graph_map_visual_asset`, `build_graph_map_visual_prompt` — données
    publiques uniquement, aucun secret MJ).
  - `app/llm/image_client.py::ImageClient` — client générique compatible
    OpenAI (DALL·E / SD-WebUI / ComfyUI), retry via `with_llm_retry`, détection
    d'erreurs 404/HTML pour endpoint mal configuré.
  - `app/services/visual_asset_service.py::generate_visual_asset` — cycle de
    vie async complet `prompt_ready → generating → ready/failed`, fire-and-forget
    (`asyncio.create_task`), publication WS (`SCENE_LAYOUT_CHANGED`,
    `REGION_MAP_UPDATED`, `CITY_MAP_UPDATED`) + persistance via
    `session_manager.save_state`.
  - Frontend : `RegionMap.vue` et `TownMap.vue` affichent `visual_asset` en
    fond de carte 2D (avec badges `prompt_ready`/`generating`) ;
    `sceneAdapter.ts` + `GroundLayer.ts` l'utilisent comme texture de sol 3D
    quand `status === "ready"`.
  - **Mais désactivée par défaut** : `Settings.image_generation_enabled =
    False`, `image_provider`/`image_base_url`/`image_model` vides, et
    `.runtime/llm_runtime.json` ne contient **aucune** clé `image_*` — donc
    *aucun provider n'est configuré* dans ce projet aujourd'hui.

- **Option 1 (rendu 3D procédural)** est également plus avancée que le constat
  initial ne le laissait supposer :
  - `frontend/src/engine3d/core/ThemeProvider.ts::BIOME_3D` couvre **les 11
    thèmes** de `SceneTheme` (`forest, beach, coastal, rocky, mountain,
    dungeon, cave, city, plains, swamp, desert`), chacun avec `ground`,
    `groundAccent`, `grid`, `gridOpacity`, `fog`, `scatter[]`,
    `cornerTorches`.
  - `backend/app/engine/theme_packs.py::THEME_PACKS` (livré en Piste B) a 13
    entrées = les 11 mêmes thèmes + 2 fallbacks (`wilderness`, `default`).
  - **Alignement 1:1** : la variété de scènes ajoutée par la Piste B
    (nouveaux packs de thèmes) bénéficie **automatiquement** au rendu 3D
    existant, sans aucune ligne de code supplémentaire.
  - Infrastructure d'assets déjà conséquente : `ProceduralFactory.ts` (501
    lignes), `AssetRegistry.ts` (126 lignes), `manifest.ts` (287 lignes, ~60
    modèles glTF référencés — packs KayKit/Kenney CC0 : personnages,
    monstres, props de donjon).

## Comparatif

| | Option 1 — Rendu 3D procédural | Option 2 — `visual_asset` (API image) |
|---|---|---|
| État | Implémenté, aligné avec Piste B (13 packs ↔ 11 thèmes) | Implémenté de bout en bout, **désactivé** |
| Travail restant | Variété de contenu (assets, palettes, scatter) — pas de plomberie | Choisir un provider, configurer `.runtime/llm_runtime.json`, activer le flag |
| Dépendances externes | Aucune (modèles glTF locaux, CC0) | API image externe (coût + latence par génération) |
| Risque | Faible — itération visuelle locale | Coût récurrent, latence (image async, fallback déjà géré), disponibilité du provider |
| Gouvernance | Décision technique pure | Décision produit/coût (quel provider, quel budget) |

## Recommandation

1. **Court terme — Option 1 sans action requise.** L'alignement `BIOME_3D` ↔
   `THEME_PACKS` est déjà complet : les nouvelles scènes générées par les
   Pistes A→D (thèmes, tailles, enclosures) sont immédiatement rendues avec la
   variété 3D existante. Toute amélioration future ici est un travail de
   contenu (nouveaux assets/scatter par biome), pas de plomberie — peut être
   planifié indépendamment, hors urgence.

2. **Option 2 reste "à un flag près" mais hors scope code.** Le pipeline est
   prêt et testé (cf. `tests/test_game/` pour `visual_asset_service`) ; il ne
   manque qu'une décision produit (quel provider d'images, quel budget/latence
   acceptable) pour renseigner `image_provider`/`image_base_url`/`image_model`
   et passer `image_generation_enabled=True`. Cette décision est **humaine,
   pas technique** — elle est explicitement reportée tant qu'aucun budget/
   provider n'est choisi.

3. **Aucun changement de code requis pour clore Piste E.** Conformément au
   plan ("Ne pas implémenter maintenant"), ce document constitue le livrable :
   la décision est "ne rien faire côté code maintenant ; rouvrir Option 2 si
   un budget image est alloué".

## Statut Piste E

✅ Validée (documentation seule) — voir `docs/map-image-generation-step2.md`
pour le statut mis à jour du hook `visual_asset`.
