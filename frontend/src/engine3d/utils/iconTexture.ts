// Rasterise les icônes SVG du registre rpgMapIcons en textures three pour les
// billboards de POI/sorties/zones. Cache par id ; null si indisponible
// (environnement sans DOM, icône manquante) → l'appelant affiche le glyphe ✦.

import * as THREE from 'three'
import { resolveRpgMapIcon } from '../../icons/rpgMapIcons'

const SIZE = 96
const cache = new Map<string, Promise<THREE.Texture | null>>()

export function loadIconTexture(iconId: string): Promise<THREE.Texture | null> {
  const cached = cache.get(iconId)
  if (cached) return cached

  const promise = rasterize(iconId)
  cache.set(iconId, promise)
  return promise
}

async function rasterize(iconId: string): Promise<THREE.Texture | null> {
  if (typeof document === 'undefined' || typeof Image === 'undefined') return null
  const definition = resolveRpgMapIcon(iconId)
  if (!definition?.colorSrc) return null

  const image = await loadImage(definition.colorSrc)
  if (!image) return null

  const canvas = document.createElement('canvas')
  canvas.width = SIZE
  canvas.height = SIZE
  const ctx = canvas.getContext('2d')
  if (!ctx) return null

  const padding = SIZE * 0.14
  ctx.drawImage(image, padding, padding, SIZE - padding * 2, SIZE - padding * 2)

  const texture = new THREE.CanvasTexture(canvas)
  texture.colorSpace = THREE.SRGBColorSpace
  texture.anisotropy = 2
  return texture
}

function loadImage(src: string): Promise<HTMLImageElement | null> {
  return new Promise((resolve) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => resolve(null)
    image.src = src
  })
}
