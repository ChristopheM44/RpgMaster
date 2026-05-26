import pytest
from app.engine.adventure_seeds import generate_adventure_context, PRESETS, BIOMES

def test_generate_adventure_context_classical_random():
    """Vérifie que la génération classique/aléatoire par défaut produit un dictionnaire complet et valide."""
    seed = generate_adventure_context()
    
    assert isinstance(seed, dict)
    assert seed["preset_id"] == "classique"
    assert seed["location_place"] != ""
    assert seed["location_region"] != ""
    assert seed["weather"] != ""
    assert seed["scene_theme"] in ["city", "dungeon", "forest", "swamp", "desert", "mountain", "coastal", "cave", "plains"]
    assert seed["tone"] != ""
    assert "DÉCOR ET AMBIANCE" in seed["opening_brief"]
    assert "DIRECTIVES DE NARRATION" in seed["opening_brief"]

def test_generate_adventure_context_with_specific_preset():
    """Vérifie que le chargement d'un preset d'univers comme Pangée ou Jungle se fait avec les bonnes valeurs."""
    # Test preset Pangée Romain
    seed_pangee = generate_adventure_context(preset_id="pangee_romain")
    assert seed_pangee["preset_id"] == "pangee_romain"
    assert seed_pangee["scene_theme"] == "rocky"
    assert "Pangée" in seed_pangee["opening_brief"]
    assert "romaine impériale" in seed_pangee["opening_brief"]
    
    # Test preset Jungle
    seed_jungle = generate_adventure_context(preset_id="jungle_dinos")
    assert seed_jungle["preset_id"] == "jungle_dinos"
    assert seed_jungle["scene_theme"] == "swamp"
    assert "dinosaures du SRD" in seed_jungle["opening_brief"]

def test_generate_adventure_context_preset_with_overrides():
    """Vérifie que les surcharges utilisateur fonctionnent même lorsqu'un preset d'univers est demandé."""
    seed = generate_adventure_context(
        preset_id="pangee_romain",
        biome_id="desert",  # Surcharge de theme rocky -> desert
        weather="Pluie battante magique"  # Surcharge de weather
    )
    
    assert seed["preset_id"] == "pangee_romain"
    assert seed["scene_theme"] == "desert"
    assert seed["weather"] == "Pluie battante magique"
    assert "Pangée" in seed["opening_brief"]  # Le reste du prompt reste identique

def test_generate_adventure_context_invalid_options():
    """Vérifie que le système retombe élégamment sur ses pieds face à des presets ou biomes invalides."""
    seed = generate_adventure_context(preset_id="invalide_preset", biome_id="invalide_biome")
    
    # Doit retomber sur une génération classique par défaut
    assert seed["preset_id"] == "classique"
    assert seed["scene_theme"] in ["city", "dungeon", "forest", "swamp", "desert", "mountain", "coastal", "cave", "plains"]
    assert seed["location_place"] != ""
