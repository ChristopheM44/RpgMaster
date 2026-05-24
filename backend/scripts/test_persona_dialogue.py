"""Script de démonstration : voir une persona riche en action vs un PNJ générique.

Usage :
    cd backend && source .venv/bin/activate
    python scripts/test_persona_dialogue.py

Ce script :
1. Construit une NPCPersona riche (Mère Éline, oracle archaïque avec secrets).
2. Construit une persona "light" minimaliste pour comparaison.
3. Appelle gm_agent.run_npc_dialogue avec chacune, pour la même question joueur.
4. Affiche le PROMPT rendu (pour vérifier l'injection) et la RÉPONSE du LLM.

Pré-requis :
- Ollama démarré avec le modèle configuré dans .env (mistral:7b par défaut).
- Aucune clé OpenAI nécessaire — c'est uniquement le pipeline texte local.

Le but est de te montrer concrètement la différence de comportement quand la
persona est riche (voix archaïque, motivations cachées, secrets) versus light.
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Ajoute backend/ au PYTHONPATH si lancé depuis ailleurs
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.agents.gm_agent import GMAgent
from app.agents.persona import (
    NPCPersona,
    PersonaKnowledge,
    PersonaMotivations,
    PersonaVoice,
    stub_npc_persona_from_legacy,
)
from app.llm.model_router import router


# ---------------------------------------------------------------------------
# Personas de test
# ---------------------------------------------------------------------------


RICH_PERSONA = NPCPersona(
    id="mere_eline",
    name="Mère Éline",
    archetype="oracle",
    short_description=(
        "Vieille oracle aveugle qui lit l'avenir dans les os de poulet. "
        "Autrefois grande prêtresse d'un temple aujourd'hui détruit."
    ),
    voice=PersonaVoice(
        gender="female",
        age_range="ancient",
        accent="noble",
        speech_register="archaic",
        pitch="low",
        rate="slow",
        timbre="raspy",
    ),
    motivations=PersonaMotivations(
        visible=["aider les voyageurs perdus", "vendre ses prédictions"],
        hidden=[
            "retrouver son ancien temple oublié",
            "se venger du grand prêtre qui l'a exilée il y a 40 ans",
        ],
        fears=["mourir avant la rédemption", "que sa cécité s'aggrave"],
    ),
    knowledge=PersonaKnowledge(
        knows=[
            "l'histoire occulte de la région",
            "le chemin vers le temple oublié",
            "les noms secrets de trois nobles corrompus",
        ],
        ignores=[
            "les évènements récents de la cour royale",
            "les nouveaux sortilèges arcanes",
        ],
        rumors=["un dragon dormirait sous les ruines"],
    ),
    importance="rich",
    attitude_default="indifferent",
    secrets=[
        "Connaît l'emplacement du temple oublié",
        "A volé une relique sacrée avant son exil",
    ],
    quest_hooks=[
        "Demander de l'aide pour retrouver le temple",
        "Offrir de prédire le destin d'un compagnon",
    ],
    catchphrases=["Les os ne mentent jamais, mon enfant.", "(rire sec)"],
)


LIGHT_PERSONA = stub_npc_persona_from_legacy(
    "Mère Éline", "Vieille femme énigmatique"
)


# ---------------------------------------------------------------------------
# Helpers d'affichage
# ---------------------------------------------------------------------------


def hr(title: str = "") -> None:
    line = "=" * 72
    print(f"\n{line}")
    if title:
        print(f"  {title}")
        print(line)


async def dump_rendered_prompt(agent: GMAgent, persona: NPCPersona) -> None:
    """Affiche le prompt Jinja rendu pour ce dialogue — utile pour vérifier
    visuellement que la persona est bien injectée par la macro _persona_render.j2."""
    from app.agents.base_agent import _PROMPTS_DIR
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    env = Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    macro_tpl = env.from_string(
        "{% import '_persona_render.j2' as P %}"
        "{{ P.render_persona(p, include_hidden=True) }}"
    )
    print(macro_tpl.render(p=persona))


async def run_dialogue(persona: NPCPersona, player_message: str) -> None:
    agent = GMAgent(client=router.get_gm_client())
    hr(f"PERSONA INJECTÉE (importance={persona.importance})")
    await dump_rendered_prompt(agent, persona)

    hr(f"MESSAGE JOUEUR → {persona.name}")
    print(player_message)

    hr("APPEL LLM — Patiente, mistral:7b peut prendre 10-30s…")
    try:
        response = await agent.run_npc_dialogue(
            npc_name=persona.name,
            npc_personality=persona,  # ← on passe la persona structurée
            player_message=player_message,
            game_state={
                "phase": "EXPLORATION",
                "npc_states": {
                    persona.id: {
                        "name": persona.name,
                        "attitude": "indifferent",
                        "last_location": "place_du_marche",
                    }
                },
                "current_scene": {"scene_id": "place_du_marche"},
                "adventure_journal": {"location_place": "place_du_marche"},
            },
            messages=[],
        )
    except Exception as exc:
        print(f"\n[ERREUR LLM] {exc}")
        print("Vérifie qu'Ollama tourne (`ollama serve`) et que le modèle est chargé.")
        return

    hr(f"NARRATION RETOURNÉE — Mood: {response.mood}")
    print(response.narration)

    if response.actions:
        hr("ACTIONS MÉCANIQUES PROPOSÉES")
        for action in response.actions:
            print(f"- {action.type} target={action.target} params={action.params}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def main() -> None:
    player_message = (
        "Mère Éline, j'ai entendu dire que vous connaissez un ancien temple. "
        "Pouvez-vous m'y conduire ?"
    )

    hr("CAS 1 — PERSONA LIGHT (équivalent à l'état actuel du pipeline)")
    print(
        "Cette persona ne contient ni voix structurée, ni motivations cachées, ni secrets.\n"
        "C'est ce que le pipeline action_resolver injecte actuellement pour tout PNJ.\n"
    )
    await run_dialogue(LIGHT_PERSONA, player_message)

    hr("CAS 2 — PERSONA RICHE (ce que la refonte permet)")
    print(
        "Cette persona a une voix archaïque, des motivations cachées (vengeance),\n"
        "des secrets (temple oublié, relique volée), et des connaissances explicites.\n"
        "Note dans la réponse : registre archaïque, allusions énigmatiques au temple,\n"
        "comportement plus profond.\n"
    )
    await run_dialogue(RICH_PERSONA, player_message)

    hr("DIAGNOSTIC")
    print(
        "Compare les deux narrations :\n"
        "- Vocabulaire (archaïque vs neutre)\n"
        "- Présence d'allusions aux motivations cachées (vengeance, temple)\n"
        "- Catchphrases utilisées (« Les os ne mentent jamais »)\n"
        "- Ton et longueur de la réponse\n\n"
        "Si CAS 2 produit une réponse sensiblement plus riche que CAS 1,\n"
        "la persona fonctionne. Si les deux sortent identiques, mistral:7b\n"
        "n'exploite pas assez les nuances — passe à un modèle plus gros (qwen2.5:14b,\n"
        "llama3.1:8b-instruct…) via GM_MODEL dans .env."
    )


if __name__ == "__main__":
    asyncio.run(main())
