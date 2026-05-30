# Suivi du refactoring — Audit d'architecture 2026-05

> **Document vivant.** Autorité unique de suivi des correctifs issus de [`audit-architecture-2026-05.md`](audit-architecture-2026-05.md).
> Remplace `REFACTO_TODO.md` et `TODO.md` (supprimés du dépôt — commit `094d292`) ; complète `avancement.md` (sprints produit).
> **Dernière mise à jour : 2026-05-30.**

Chaque ligne de l'audit (§1 → §8) a un **statut**. Le travail en cours porte sur la **section 4 (Qualité du code & maintenabilité)** ; les autres sections sont tracées pour visibilité mais hors périmètre de ce cycle.

---

## Légende des statuts

| Statut | Sens |
|---|---|
| ✅ **Conforme** | Déjà correct dans le code (point ✅ de l'audit) ou décision actée — rien à faire |
| 🟢 **Fait** | Correctif livré et vérifié ce cycle |
| 🔵 **En cours** | Lot démarré, partiellement livré |
| ⚪ **À faire** | Identifié, non démarré |
| ♻️ **Continu** | Chantier borné mais sans fin nette — progression partielle = sain |

Sévérité (reprise de l'audit) : 🔴 BLOQUANT · 🟠 IMPORTANT · 🟡 SOUHAITABLE.

---

## Baseline de référence (2026-05-30)

État vert mesuré sur `main` (HEAD `094d292`) **avant** tout correctif de ce cycle. Tout lot doit conserver ces valeurs.

| Mesure | Commande | Valeur |
|---|---|---|
| Backend tests | `backend/.venv/bin/pytest tests -q` | **1760 passed** (1 warning, ~3 min) |
| Backend lint | `backend/.venv/bin/ruff check app tests --statistics` | **34 diagnostics** (22 E501, 9 UP042, 2 F841, 1 N806) |
| Frontend tests | `npm run test` | **17 fichiers / 60 tests passed** |
| Frontend build | `npm run build` | **OK** |

> Note : l'ancienne baseline de `REFACTO_TODO.md` (2026-05-09 : 1471 tests, 216 ruff, 29 tests front) est caduque (fichier supprimé) — le code a grandi et la dette Ruff a fortement baissé entre-temps.

---

## Tableau de synthèse — tout l'audit

> Colonne **Lot** : renvoie au détail §4 ci-dessous pour les items traités ce cycle ; « — » = hors périmètre de ce cycle.

### §1 Architecture globale
| § | Sév. | Item | Statut | Lot | Note |
|---|---|---|---|---|---|
| 1.1 | 🟠 | Machine à états non faisante autorité | ⚪ | — | Hors périmètre §4 |
| 1.2 | 🟡 | Cycle de dépendance `ws_game ↔ ws_handlers` | ⚪ | **Lot 2a** | Tiré dans ce cycle car *préalable* au découpage de `combat.py` |
| 1.3 | 🟡 | God-service `campaign_dossier_service` | ⚪ | **Lot 3b** | Traité avec §4.1 |

### §2 Cohérence du flux narratif
| § | Sév. | Item | Statut | Lot | Note |
|---|---|---|---|---|---|
| 2.1 | 🟠 | Heuristiques regex combat fragiles | ⚪ | — | Hors périmètre |
| 2.2 | ✅ | Pipeline d'intro de combat cohérent | ✅ | — | |
| 2.3 | 🟠 | Cascade d'appels LLM par tour social | ⚪ | — | Hors périmètre |
| 2.4 | 🟠 | `resolve_npc_dialogue` copie superficielle | ⚪ | — | Hors périmètre |
| 2.5 | ✅ | Conditions de course (`session_lock` OK) | ✅ | — | Vraie fragilité = §5.3 |

### §3 Sécurité
| § | Sév. | Item | Statut | Lot | Note |
|---|---|---|---|---|---|
| 3.1 | 🔴 | Auth fail-open + zéro autorisation | ⚪ | — | Hors périmètre §4 (chantier sécurité dédié) |
| 3.2 | ✅ | Injection prompt mitigée | ✅ | — | |
| 3.3 | ✅ | Protection SSRF complète | ✅ | — | |
| 3.4 | ✅ | Clés API stockées correctement | ✅ | — | |
| 3.5 | ✅ | Pas de fuite GM→joueur | ✅ | — | |
| 3.6 | ✅ | Validation d'entrée WS stricte | ✅ | — | |
| 3.7 | 🟡 | Token WS en query string | ⚪ | — | Hors périmètre |
| 3.8 | 🟡 | Pas de rate-limit WS / `/start` | ⚪ | — | Hors périmètre (cf. §5.2) |

### §4 Qualité du code & maintenabilité — **CYCLE EN COURS**
| § | Sév. | Item | Statut | Lot | Note |
|---|---|---|---|---|---|
| 4.1 | 🟠 | God-files (`combat`, `routes_game`, `dossier_service`) | ⚪ | **Lots 2c / 3a / 3b** | Découpe par responsabilité |
| 4.2 | 🟡 | Duplication combat manuel / IA | ⚪ | **Lot 2b** | `CombatActionNormalizer` partagé |
| 4.3 | 🟠 | Gestion d'erreur silencieuse | 🟢 | **Lot 1** | Livré 2026-05-30 |
| 4.4 | 🟡 | Typage `Any` sur le hot-path | ⚪ | **Lot 4** | ♻️ Continu / borné |
| 4.5 | ✅ | Testabilité bonne | ✅ | — | Frein résiduel levé par Lot 2a |

### §5 Performance et scalabilité
| § | Sév. | Item | Statut | Lot | Note |
|---|---|---|---|---|---|
| 5.1 | ✅ | EventBus plein ne bloque pas | ✅ | — | |
| 5.2 | 🔴 | Tâches de fond non bornées | ⚪ | — | Hors périmètre §4 |
| 5.3 | 🟠 | `close_session` pop le lock détenu | ⚪ | — | Hors périmètre |
| 5.4 | 🟠 | SQLite mal réglé (pas de WAL/busy_timeout) | ⚪ | — | Hors périmètre |
| 5.5 | 🟡 | Game state = blob JSON réécrit | ⚪ | — | Hors périmètre |
| 5.6 | 🟡 | Fuite mémoire mineure EventBus | ⚪ | — | Hors périmètre |
| 5.7 | ✅ | TTS fire-and-forget | ✅ | — | |

### §6 Frontend
| § | Sév. | Item | Statut | Lot | Note |
|---|---|---|---|---|---|
| 6.1 | ✅ | Protocole défensif | ✅ | — | |
| 6.2 | ✅ | Reconnexion et état partagé | ✅ | — | |
| 6.3 | 🟡 | `damage_applied` no-op silencieux | ⚪ | — | Hors périmètre |
| 6.4 | 🟡 | État `processing` sans terminaison garantie | ⚪ | — | Hors périmètre |
| 6.5 | 🟡 | URL backend codée en dur | ⚪ | — | Hors périmètre |

### §7 Base de données et persistance
| § | Sév. | Item | Statut | Lot | Note |
|---|---|---|---|---|---|
| 7.1 | 🟠 | SQLite = plafond dur multi-session | ⚪ | — | Hors périmètre (décision à acter) |
| 7.2 | ✅ | Schéma propre et cohérent | ✅ | — | |
| 7.3 | 🟡 | Cohérence in-memory ↔ colonnes | ⚪ | — | Hors périmètre |
| 7.4 | 🟡 | Enum `LOBBY` vestigial | ⚪ | — | Hors périmètre (lié §1.1) |

---

## Détail — Section 4 (cycle en cours)

> Principe : **déplacement pur + ré-export, zéro changement de comportement**. La suite de tests reste à 1760 ⇒ aucun test existant ne doit changer pour une découpe. Le suivi est mis à jour *dans le même commit* que le correctif.

### Lot 1 — §4.3 🟠 Observabilité des erreurs · `🟢 Fait`
- [x] Créer `app/logging_utils.py` (`log_degraded` : optionnel→WARNING / anormal→ERROR, avec contexte).
- [x] `action_resolver.py` : 4 sites cartes/persona (L238, L339, L497, L459) remontés en WARNING via `log_degraded`. L253/L507 (`logger.error`) laissés intacts.
- [x] `ws_payloads.py` : 3 `except` muets (L33, L93, L106) → `log_degraded`, fallback dégradé conservé.
- [x] `ai_player_manager.py:922` (résolution cible PNJ) → `log_degraded` ; `config.py:135` (config LLM corrompue) → `logger.warning` direct (module fondateur, pas d'import d'app).
- [~] `ws_game.py:426` : **laissé intact** — sortie de boucle normale (déconnexion client) ; logger ici serait du bruit à chaque fermeture.

_Note 2026-05-30 : tests ciblés `test_game + test_api` → **424 passed**. `ruff check` global inchangé (**34**). Pas de `ruff format` sur le code préexistant (drift Lot C non résorbée) ; seul le fichier neuf `logging_utils.py` est formaté._

### Lot 2 — Chaîne combat (ordonnée 2a → 2b → 2c)

#### Lot 2a — §1.2 🟡 Casser le cycle `ws_game ↔ ws_handlers` · `⚪ À faire` *(enabler)*
- [ ] Créer `app/api/ws_handlers/shared.py` (symboles réimportés : `action_resolver`, `event_bus`, `build_session_state_payload`, `_generate_encounter_intro`…).
- [ ] Supprimer les 7 `from app.api import ws_game` internes à `combat.py` (L679, 1011, 1234, 1273, 1362, 1765, 1802).
- [ ] Retirer les réexports « legacy tests » `ws_game.py:615-698`.

#### Lot 2b — §4.2 🟡 `CombatActionNormalizer` partagé · `⚪ À faire` *(bloqué par 2a)*
- [ ] Créer `app/game/combat_action_normalizer.py` (`resolve_target`, `resolve_spell`, `select_fallback_action`).
- [ ] Brancher chemin humain (`action_resolver`/`action_pipeline`) **et** IA (`ai_player_manager` L1123-1355).
- [ ] Garder AI-only : `_resolve_movement_intent`, `_build_deterministic_combat_action`.

#### Lot 2c — §4.1 🟠 Scinder `combat.py` · `⚪ À faire` *(bloqué par 2b)*
- [ ] `handle_start_combat` (319 l.) → `_load_encounter` / `_build_combatants` / `_setup_grid_and_terrain` / `_announce_and_transition`.
- [ ] Extraire l'aftermath vers `app/api/ws_handlers/combat_aftermath.py`.

### Lot 3 — Autres god-files (indépendants, après Lot 2)

#### Lot 3a — §4.1 🟠 `routes_game.py` → `opening_scene_service.py` · `⚪ À faire`
- [ ] Extraire le cluster ouverture (~40 helpers, L86-1442) vers `services/opening_scene_service.py`.
- [ ] Routeur réduit aux 6-7 endpoints HTTP.

#### Lot 3b — §4.1 / §1.3 🟠 `campaign_dossier_service.py` → 4 modules · `⚪ À faire`
- [ ] `campaign_forge.py` · `canon_synthesis.py` · `persona_store.py` · `map_context.py`.
- [ ] Conserver `compile_campaign_context_for_session` + getters en façade ré-exportante.

### Lot 4 — §4.4 🟡 Typage de l'état · `♻️ Continu`
- [ ] Typer `ActiveSession.state_data: GameStateData` (`session_manager.py:65`).
- [ ] Faire respecter `GameStateData` à la frontière load/save (aujourd'hui le résultat de `migrate_state_data` est jeté).
- [ ] Resserrer `extra="allow"` sur `CombatantState` / `TurnManagerState` uniquement (laisser la longue traîne).

---

## Déjà engagé (cycle post-audit précédent)

Refonte livrée entre l'audit initial (`b5a3e11`) et `3bed28b`, **matérialise le « engagé »** :

| Commit | Objet |
|---|---|
| `b5a3e11` | Début refacto suite audit |
| `ee4a164` | Refacto suite audit (sécurité/config) |
| `5952e49` | Refacto sécurité |
| `676a253` | Refacto pipeline IA |
| `b821c76` | Refacto + correction flux narratif |
| `0d33f0d` | Suite refacto (fin de cycle) |
| `173b912` | Constantes nommées au lieu de limites en dur |

Effets déjà acquis (vérifiés dans l'audit) : `ws_game.py` réduit à un dispatcher, EventBus borné non bloquant, couche token HTTP+WS, anti-injection prompt, SSRF, validation WS stricte.

---

## Vérification (rappel par lot)

```bash
# Spine — doit rester ≥ baseline après chaque lot
cd backend && .venv/bin/pytest tests -q                 # 1760 passed
.venv/bin/ruff check app tests && .venv/bin/ruff format app   # ≤ 34, sans élargir les ignores
# Ciblé : pytest tests/test_game -q (Lots 1,2,4) · pytest tests/test_api -q (Lots 2,3)
# Combat (Lot 2) : smoke test uvicorn + npm run dev → combat + tour IA
cd ../frontend && npm run test && npm run build          # contrôle après Lot 2
```
