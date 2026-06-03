import { describe, expect, it } from 'vitest'
import {
  buildSceneExitPrompt,
  buildScenePoiInteractionPrompt,
  cleanExitLabel,
} from '../scenePoiInteractions'

// Libellés de sortie tirés de sessions réelles (backend/rpgmaster.db) — ce sont
// surtout des verbes impératifs, pas les simples préfixes nominaux supposés.
const REAL_EXIT_LABELS = [
  'Continuer vers Phandalin',
  "S'enfoncer dans les bois",
  'Prendre la route',
  'Retourner dans la cour',
  'Aller vers la sacristie',
  'Quartier du Marché',
  'Quartier des Marchands',
  "Retour vers la Piste d'Ambre",
  'Retour aux Égouts',
]

describe('buildSceneExitPrompt — anti-doublon sur libellés réels', () => {
  it.each(REAL_EXIT_LABELS)('« %s » : aucun doublon de préposition', (label) => {
    const phrase = buildSceneExitPrompt(label)
    // Critère §4.1 : jamais « vers … vers » ni « vers vers ».
    expect(phrase).not.toMatch(/\bvers\b[^.]*\bvers\b/i)
    // Jamais un préfixe d'interface brut recollé après « vers ».
    expect(phrase).not.toMatch(/vers\s+(?:Direction|Accès|Passage)\b/i)
    expect(phrase.endsWith('.')).toBe(true)
  })

  it('naturalise le cas §4.1 « Direction les Docks »', () => {
    expect(buildSceneExitPrompt('Direction les Docks')).toBe('Je me dirige vers les Docks.')
  })

  it('émet les structures de déplacement telles quelles (anti-doublon)', () => {
    expect(buildSceneExitPrompt('Continuer vers Phandalin')).toBe('Continuer vers Phandalin.')
    expect(buildSceneExitPrompt('Retour aux Égouts')).toBe('Retour aux Égouts.')
    expect(buildSceneExitPrompt("S'enfoncer dans les bois")).toBe("S'enfoncer dans les bois.")
    expect(buildSceneExitPrompt('Aller vers la sacristie')).toBe('Aller vers la sacristie.')
  })

  it('préfixe les noms de lieu nus', () => {
    expect(buildSceneExitPrompt('Quartier du Marché')).toBe('Je me dirige vers Quartier du Marché.')
  })

  it('gère les préfixes directionnels nommés (préposition/article)', () => {
    expect(buildSceneExitPrompt('Vers les quais')).toBe('Je me dirige vers les quais.')
    expect(buildSceneExitPrompt('Accès aux caves')).toBe('Je me dirige aux caves.')
    expect(buildSceneExitPrompt('Passage vers les caves')).toBe('Je me dirige vers les caves.')
  })

  it("ne tronque pas un nom de lieu (« Passage souterrain » reste intact)", () => {
    expect(buildSceneExitPrompt('Passage souterrain')).toBe(
      'Je me dirige vers Passage souterrain.',
    )
  })

  it('retombe proprement quand le strip viderait le libellé', () => {
    expect(buildSceneExitPrompt('Direction')).toBe('Je me dirige vers Direction.')
  })
})

describe('cleanExitLabel — strip uniquement les préfixes prouvés', () => {
  it('retire un préfixe directionnel qui introduit une destination', () => {
    expect(cleanExitLabel('Direction les Docks')).toBe('les Docks')
    expect(cleanExitLabel('Vers les quais')).toBe('les quais')
  })

  it('laisse intact ce qui n’est pas un préfixe directionnel', () => {
    expect(cleanExitLabel('Passage souterrain')).toBe('Passage souterrain')
    expect(cleanExitLabel('Continuer vers Phandalin')).toBe('Continuer vers Phandalin')
  })
})

describe('buildScenePoiInteractionPrompt — plus de fuite mécanique sur examine', () => {
  it("produit une phrase naturelle sans « J'examine : » ni DC", () => {
    const phrase = buildScenePoiInteractionPrompt('La Faille Sombre', {
      label: 'Observer',
      intent: 'examine',
    })
    expect(phrase).toBe("Je m'arrête devant La Faille Sombre et l'examine attentivement.")
    expect(phrase).not.toContain(':')
    expect(phrase).not.toMatch(/DD\s*\d/)
  })

  it('respecte un prompt fourni par le MJ', () => {
    expect(
      buildScenePoiInteractionPrompt('Khalid', {
        label: 'Parler',
        intent: 'talk',
        prompt: 'Je salue Khalid.',
      }),
    ).toBe('Je salue Khalid.')
  })
})
