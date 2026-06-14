# 3D Model Credits

The models in this directory are **pruned subsets** of the CC0 packs below — full packs can be re-fetched and re-staged with `frontend/scripts/fetch_3d_assets.sh`.

| Pack | Author | Source | License | Fetched |
|---|---|---|---|---|
| KayKit Character Pack: Adventurers (1.0) — `adventurers/` | Kay Lousberg | https://github.com/KayKit-Game-Assets/KayKit-Character-Pack-Adventures-1.0 | CC0-1.0 | 2026-06-10 |
| KayKit Character Pack: Skeletons (1.0) — `skeletons/` | Kay Lousberg | https://github.com/KayKit-Game-Assets/KayKit-Character-Pack-Skeletons-1.0 | CC0-1.0 | 2026-06-10 |
| KayKit Dungeon Remastered (1.0) — `dungeon/` | Kay Lousberg | https://github.com/KayKit-Game-Assets/KayKit-Dungeon-Remastered-1.0 | CC0-1.0 | 2026-06-10 |
| Kenney Nature Kit (2.1) — `nature/` | Kenney | https://kenney.nl/assets/nature-kit | CC0-1.0 | 2026-06-10 |
| KayKit Forest Nature Pack (1.0) — `nature/forest/` | Kay Lousberg | https://kaylousberg.itch.io/kaykit-forest | CC0-1.0 | 2026-06-14 |

All five packs are released under [Creative Commons Zero 1.0](https://creativecommons.org/publicdomain/zero/1.0/) (public domain): attribution is **not required**, but is appreciated by the authors — consider supporting them at https://kaylousberg.itch.io/ and https://kenney.nl/.

`nature/forest/*.gltf` ship as glTF + external `.bin` + one shared `forest_texture.png`
(this pack's only format), unlike the single-`.glb` convention used elsewhere —
`GLTFLoader` resolves the siblings by relative URI, so no conversion was needed.
