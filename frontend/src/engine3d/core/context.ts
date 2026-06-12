// Contexte passé du runtime aux couches à chaque update — résolu une fois par
// frame de spec (thème, biome, ambiance, registre d'assets, groupe de tweens).

import type { AssetRegistry } from '../assets/AssetRegistry'
import type { GridDims } from '../types'
import type { AmbiancePreset, Biome3D, ThemeTokens } from './ThemeProvider'
import type { TweenGroup } from './tween'

export interface EngineCtx {
  dims: GridDims
  cellSizeM: number
  tokens: ThemeTokens
  biome: Biome3D
  ambiance: AmbiancePreset
  registry: AssetRegistry
  tweens: TweenGroup
}
