import { describe, expect, it } from 'vitest'
import {
  MODEL_MANIFEST,
  modelForClass,
  modelForElement,
  modelForMonster,
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

  it('monstres : squelettes détectés, autres → null (pion procédural)', () => {
    expect(modelForMonster('Squelette archer')).toBe('monster/skeleton_mage')
    expect(modelForMonster('skeleton warrior')).toBe('monster/skeleton_warrior')
    expect(modelForMonster('liche ancienne')).toBe('monster/skeleton_mage')
    expect(modelForMonster('gobelin fourbe')).toBeNull()
    expect(modelForMonster(undefined)).toBeNull()
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
