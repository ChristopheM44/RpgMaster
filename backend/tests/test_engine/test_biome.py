"""infer_region_biome — inférence de biome depuis un corpus de noms/descriptions (Piste C.1)."""

from __future__ import annotations

from app.services.biome import infer_region_biome


def test_infer_region_biome_detects_coastal_keywords() -> None:
    assert infer_region_biome("Port-Neuf, quai nord et brume marine") == "coastal"
    assert infer_region_biome("Falaise des naufrageurs") == "coastal"
    assert infer_region_biome("Harbor district") == "coastal"


def test_infer_region_biome_detects_desert_keywords() -> None:
    assert infer_region_biome("Les dunes du désert d'Ashar") == "desert"
    assert infer_region_biome("Oasis cachée") == "desert"


def test_infer_region_biome_detects_mountain_keywords() -> None:
    assert infer_region_biome("Col du Mont Brisé") == "mountain"
    assert infer_region_biome("Mountain pass") == "mountain"


def test_infer_region_biome_defaults_without_keywords() -> None:
    assert infer_region_biome("Auberge du Pont, Bois Creux") == "default"
    assert infer_region_biome("") == "default"


def test_infer_region_biome_priority_coastal_over_desert_over_mountain() -> None:
    # Cote l'emporte sur desert
    assert infer_region_biome("oasis au bord de la mer") == "coastal"
    # Desert l'emporte sur montagne
    assert infer_region_biome("dunes au pied du mont") == "desert"


def test_infer_region_biome_is_case_insensitive() -> None:
    assert infer_region_biome("LE DÉSERT D'ASHAR") == "desert"
    assert infer_region_biome("MOUNTAIN PEAK") == "mountain"
