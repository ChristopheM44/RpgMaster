from __future__ import annotations

import pytest

from app.agents.context_manager import ContextManager
from app.agents.schemas import ContextMessage


# ---------------------------------------------------------------------------
# add_message / get_messages
# ---------------------------------------------------------------------------


def test_add_and_get_messages() -> None:
    """Les messages ajoutés sont bien récupérés dans l'ordre."""
    cm = ContextManager(max_messages=10)
    cm.add_message("gm", "MJ", "Vous entrez dans la taverne.")
    cm.add_message("player", "Thorin", "Je commande une bière.")

    messages = cm.get_messages()
    assert len(messages) == 2
    assert messages[0].role == "gm"
    assert messages[0].speaker == "MJ"
    assert messages[1].content == "Je commande une bière."


def test_get_messages_last_n() -> None:
    """get_messages(last_n=2) retourne les 2 derniers messages."""
    cm = ContextManager(max_messages=10)
    for i in range(5):
        cm.add_message("player", f"Joueur{i}", f"Message {i}")

    last_two = cm.get_messages(last_n=2)
    assert len(last_two) == 2
    assert last_two[0].content == "Message 3"
    assert last_two[1].content == "Message 4"


def test_get_messages_last_n_greater_than_size() -> None:
    """Si last_n > taille de la fenêtre, retourne tous les messages."""
    cm = ContextManager(max_messages=10)
    cm.add_message("gm", "MJ", "Scène 1")
    cm.add_message("gm", "MJ", "Scène 2")

    result = cm.get_messages(last_n=100)
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Fenêtre glissante
# ---------------------------------------------------------------------------


def test_sliding_window_evicts_oldest() -> None:
    """La fenêtre évince les messages les plus anciens quand elle est pleine."""
    cm = ContextManager(max_messages=3)
    cm.add_message("gm", "MJ", "Message 1")
    cm.add_message("gm", "MJ", "Message 2")
    cm.add_message("gm", "MJ", "Message 3")
    cm.add_message("gm", "MJ", "Message 4")  # Évince "Message 1"

    messages = cm.get_messages()
    assert len(messages) == 3
    assert messages[0].content == "Message 2"
    assert messages[-1].content == "Message 4"


def test_size_and_is_full() -> None:
    """size et is_full reflètent l'état de la fenêtre."""
    cm = ContextManager(max_messages=3)
    assert cm.size == 0
    assert cm.is_full is False

    cm.add_message("gm", "MJ", "a")
    cm.add_message("gm", "MJ", "b")
    assert cm.size == 2
    assert cm.is_full is False

    cm.add_message("gm", "MJ", "c")
    assert cm.size == 3
    assert cm.is_full is True


def test_clear() -> None:
    """clear() vide la fenêtre."""
    cm = ContextManager(max_messages=5)
    cm.add_message("gm", "MJ", "test")
    cm.clear()
    assert cm.size == 0
    assert cm.get_messages() == []


# ---------------------------------------------------------------------------
# add_message avec metadata
# ---------------------------------------------------------------------------


def test_add_message_with_metadata() -> None:
    """Les métadonnées sont bien stockées."""
    cm = ContextManager(max_messages=5)
    cm.add_message("system", "Système", "Initiative lancée", metadata={"roll": 15})

    msg = cm.get_messages()[0]
    assert msg.metadata["roll"] == 15


def test_add_message_default_metadata() -> None:
    """La metadata est un dict vide par défaut."""
    cm = ContextManager(max_messages=5)
    cm.add_message("gm", "MJ", "test")

    msg = cm.get_messages()[0]
    assert msg.metadata == {}


# ---------------------------------------------------------------------------
# to_ollama_messages
# ---------------------------------------------------------------------------


def test_to_ollama_messages_structure() -> None:
    """to_ollama_messages() retourne system + messages convertis en format Ollama."""
    cm = ContextManager(max_messages=10)
    cm.add_message("player", "Aria", "Je cherche le trône.")
    cm.add_message("gm", "MJ", "La salle du trône est au nord.")

    result = cm.to_ollama_messages("Tu es le MJ.")

    assert result[0] == {"role": "system", "content": "Tu es le MJ."}
    assert result[1]["role"] == "user"
    assert "[Aria]" in result[1]["content"]
    assert result[2]["role"] == "assistant"
    assert "[MJ]" in result[2]["content"]


def test_to_ollama_messages_player_becomes_user() -> None:
    """Le rôle 'player' est converti en 'user' pour Ollama."""
    cm = ContextManager(max_messages=5)
    cm.add_message("player", "Thorin", "J'attaque.")

    messages = cm.to_ollama_messages("sys")
    assert messages[1]["role"] == "user"


def test_to_ollama_messages_gm_becomes_assistant() -> None:
    """Le rôle 'gm' est converti en 'assistant' pour Ollama."""
    cm = ContextManager(max_messages=5)
    cm.add_message("gm", "MJ", "Le gobelin riposte.")

    messages = cm.to_ollama_messages("sys")
    assert messages[1]["role"] == "assistant"


def test_to_ollama_messages_with_last_n() -> None:
    """to_ollama_messages(last_n=1) ne transmet qu'un message."""
    cm = ContextManager(max_messages=10)
    cm.add_message("gm", "MJ", "Premier message")
    cm.add_message("gm", "MJ", "Dernier message")

    messages = cm.to_ollama_messages("sys", last_n=1)
    # system + 1 message
    assert len(messages) == 2
    assert "Dernier message" in messages[1]["content"]


def test_to_ollama_messages_empty_context() -> None:
    """to_ollama_messages() avec fenêtre vide retourne seulement le system prompt."""
    cm = ContextManager(max_messages=5)
    messages = cm.to_ollama_messages("Tu es le MJ.")
    assert len(messages) == 1
    assert messages[0]["role"] == "system"
