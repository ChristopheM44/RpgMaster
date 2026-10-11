import type { Character, SceneLayout } from '../../types'

/** Scène figée du banc d'essai carte (générée par backend/scripts/export_map_lab_fixtures.py). */
export interface MapLabFixture {
  id: string
  title: string
  /** Session d'origine ou « synthétique — … ». */
  source: string
  scene: SceneLayout
  characters: Pick<Character, 'id' | 'name' | 'char_class' | 'species' | 'is_ai' | 'hp_current' | 'hp_max'>[]
}
