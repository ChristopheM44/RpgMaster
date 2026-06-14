import { existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import {
  MODEL_MANIFEST,
  modelForClass,
  modelForElement,
  modelForMonster,
  modelForNpc,
  PROP_TARGET_HEIGHT_M,
  SCATTER_MODELS,
  SCATTER_TARGET_HEIGHT_M,
} from '../assets/manifest'
import { BIOME_3D } from '../core/ThemeProvider'

describe('manifest 3D', () => {
  it('toutes les classes D&D (ids bruts ET libellés FR) résolvent un modèle', () => {
    const raw = ['fighter', 'paladin', 'cleric', 'barbarian', 'monk', 'wizard', 'sorcerer', 'warlock', 'rogue', 'bard', 'ranger', 'druid']
    for (const cls of raw) {
      expect(modelForClass(cls), cls).toBeTruthy()
    }
    const fr = ['Guerrier', 'Magicien', 'Clerc', 'Roublard', 'Rôdeur', 'Barbare', 'Druide', 'Occultiste']
    for (const cls of fr) {
      expect(modelForClass(cls), cls).toBeTruthy()
    }
    expect(modelForClass('artificer_maison')).toBeNull()
    expect(modelForClass(null)).toBeNull()
  })

  it('toute clé résolue existe dans le manifest (classes, monstres, scatter, props)', () => {
    const referenced = new Set<string>()
    for (const cls of ['fighter', 'wizard', 'rogue', 'ranger', 'barbarian']) {
      const key = modelForClass(cls)
      if (key) referenced.add(key)
    }
    const monsterKey = modelForMonster('squelette gardien')
    if (monsterKey) referenced.add(monsterKey)
    for (const keys of Object.values(SCATTER_MODELS)) {
      keys.forEach((key) => referenced.add(key))
    }
    for (const key of referenced) {
      expect(MODEL_MANIFEST[key], `clé manquante: ${key}`).toBeDefined()
    }
  })

  it('monstres : squelettes détectés, humanoïdes approximés, bêtes → null (pion)', () => {
    expect(modelForMonster('Squelette archer')).toBe('monster/skeleton_mage')
    expect(modelForMonster('skeleton warrior')).toBe('monster/skeleton_warrior')
    expect(modelForMonster('liche ancienne')).toBe('monster/skeleton_mage')
    // Humanoïdes sans modèle dédié → silhouette approchante.
    expect(modelForMonster('gobelin fourbe')).toBe('monster/skeleton_minion')
    expect(modelForMonster('Kobold éclaireur')).toBe('monster/skeleton_minion')
    expect(modelForMonster('Orc des collines')).toBe('monster/skeleton_warrior')
    expect(modelForMonster('Chamane gnoll')).toBe('monster/skeleton_mage')
    expect(modelForMonster('Spectre hurlant')).toBe('monster/skeleton_rogue')
    // Bêtes : un squelette serait pire que l'abstraction du pion.
    expect(modelForMonster('Loup affamé')).toBeNull()
    expect(modelForMonster('Araignée géante')).toBeNull()
    expect(modelForMonster(undefined)).toBeNull()
    // Priorité conservée : la règle liche prime sur la règle nécromant.
    expect(modelForMonster('liche nécromancienne')).toBe('monster/skeleton_mage')
  })

  it('PNJ : mots-clés FR/EN → modèle de personnage, défaut → quidam humanoïde', () => {
    expect(modelForNpc('Garde du pont')).toBe('char/knight')
    expect(modelForNpc('Capitaine Aldric, sentinelle')).toBe('char/knight')
    expect(modelForNpc('Vieille sorcière des marais')).toBe('char/mage')
    expect(modelForNpc('Prêtresse de la Lumière')).toBe('char/mage')
    expect(modelForNpc('Silhouette encapuchonnée')).toBe('char/rogue_hooded')
    expect(modelForNpc('Forgeron taciturne')).toBe('char/barbarian')
    expect(modelForNpc('Aubergiste jovial')).toBe('char/rogue')
    expect(modelForNpc('Merchant of curiosities')).toBe('char/rogue')
    // Plus jamais de pion : un PNJ sans rôle reconnaissable tombe sur un humanoïde.
    const fallback = modelForNpc('Vieil homme énigmatique')
    expect(fallback).not.toBeNull()
    expect(MODEL_MANIFEST[fallback!], `clé manquante: ${fallback}`).toBeDefined()
    // Déterministe : même corpus → même apparence.
    expect(modelForNpc('Vieil homme énigmatique')).toBe(fallback)
    // Corpus vide → null (aucun PNJ à représenter).
    expect(modelForNpc(null)).toBeNull()
    expect(modelForNpc('')).toBeNull()
    for (const corpus of ['Garde', 'Sorcière', 'Mendiant', 'Forgeron', 'Villageois', 'Inconnu', 'Bram']) {
      const key = modelForNpc(corpus)
      expect(key && MODEL_MANIFEST[key], `clé manquante: ${key}`).toBeTruthy()
    }
  })

  it('éléments : porte → modèle, variantes par empreinte, torche murale', () => {
    expect(modelForElement('door', 'Porte de fer', { x: 1, z: 1 })).toBe('prop/door')
    expect(modelForElement('furniture', 'Petite table', { x: 1, z: 1 })).toBe('prop/table_small')
    expect(modelForElement('cover', 'Gros tonneau', { x: 1.6, z: 1.6 })).toBe('prop/barrel_large')
    expect(modelForElement('furniture', 'Petite étagère', { x: 1, z: 0.6 })).toBe('prop/shelf_small')
    expect(modelForElement('light', 'Torche murale', { x: 0.3, z: 0.3 })).toBe('prop/torch_mounted')
    expect(modelForElement('light', 'Brasero', { x: 1, z: 1 })).toBe('prop/torch_lit')
  })

  it('éléments : props ajoutés (chest doré, campfire, tente, pot)', () => {
    expect(modelForElement('decor', 'Coffre au trésor doré', { x: 1, z: 1 })).toBe('prop/chest_gold')
    expect(modelForElement('furniture', 'Vieux coffre', { x: 1, z: 1 })).toBe('prop/chest')
    expect(modelForElement('light', 'Feu de camp', { x: 1.5, z: 1.5 })).toBe('prop/campfire')
    expect(modelForElement('decor', 'Foyer de pierres', { x: 1, z: 1 })).toBe('prop/campfire')
    expect(modelForElement('decor', 'Tente de toile', { x: 2, z: 2 })).toBe('prop/tent')
    expect(modelForElement('decor', 'Grande jarre', { x: 1, z: 1 })).toBe('prop/pot')
  })

  it('éléments : un rocher en couvert → modèle de roche, pas des caisses', () => {
    expect(modelForElement('cover', 'Rocher érodé', { x: 1, z: 1 })).toBe('nature/rock_large_a')
    expect(modelForElement('decor', 'Gros caillou', { x: 1, z: 1 })).toBe('nature/rock_large_a')
    // Couvert vraiment indéterminé → caisses (repli conservé).
    expect(modelForElement('cover', 'Empilement bizarre', { x: 1, z: 1 })).toBe('prop/crates_stacked')
  })

  it('éléments : statues / obélisques (props verticaux)', () => {
    expect(modelForElement('decor', 'Statue du héros déchu', { x: 1, z: 1 })).toBe('prop/statue')
    expect(modelForElement('decor', 'Idole de pierre', { x: 1, z: 1 })).toBe('prop/statue')
    expect(modelForElement('decor', 'Obélisque gravé', { x: 1, z: 1 })).toBe('prop/obelisk')
    expect(modelForElement('cover', 'Menhir dressé', { x: 1, z: 1 })).toBe('prop/obelisk')
  })

  it('props à hauteur intrinsèque : clés valides et fit height', () => {
    for (const [key, height] of Object.entries(PROP_TARGET_HEIGHT_M)) {
      expect(MODEL_MANIFEST[key], `clé inconnue: ${key}`).toBeDefined()
      expect(MODEL_MANIFEST[key]?.fit, `${key} devrait être fit:height`).toBe('height')
      expect(height).toBeGreaterThan(0.5)
    }
  })

  it('chaque fichier de MODEL_MANIFEST existe sur le disque (anti-régression)', () => {
    const modelsDir = join(dirname(fileURLToPath(import.meta.url)), '../../../public/models')
    for (const [key, def] of Object.entries(MODEL_MANIFEST)) {
      expect(existsSync(join(modelsDir, def.file)), `fichier manquant pour ${key}: ${def.file}`).toBe(true)
    }
  })

  it('éléments : mots-clés FR → props, cover par défaut → caisses, sinon null', () => {
    expect(modelForElement('furniture', 'Table centrale', { x: 2, z: 1 })).toBe('prop/table_medium')
    expect(modelForElement('furniture', 'Grande table du banquet', { x: 3, z: 1 })).toBe('prop/table_long')
    expect(modelForElement('furniture', 'Étagère murale', { x: 1, z: 2 })).toBe('prop/shelf_large')
    expect(modelForElement('cover', 'Tonneaux renversés', { x: 1, z: 1 })).toBe('prop/barrel_small')
    expect(modelForElement('cover', 'Empilement bizarre', { x: 1, z: 1 })).toBe('prop/crates_stacked')
    expect(modelForElement('furniture', 'Machin inconnu', { x: 1, z: 1 })).toBeNull()
    expect(modelForElement('wall', 'Mur', { x: 4, z: 0.2 })).toBeNull()
  })

  it('chaque ScatterKind utilisé par un biome a modèles + hauteur cible', () => {
    const kinds = new Set(Object.values(BIOME_3D).flatMap((biome) => biome.scatter))
    kinds.add('torch')
    for (const kind of kinds) {
      expect(SCATTER_MODELS[kind], `modèles manquants: ${kind}`).toBeDefined()
      expect(SCATTER_TARGET_HEIGHT_M[kind], `hauteur manquante: ${kind}`).toBeGreaterThan(0)
    }
  })
})
