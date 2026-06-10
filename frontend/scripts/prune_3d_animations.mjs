#!/usr/bin/env node
// Allège les personnages KayKit committés dans public/models : ne garde que
// les clips utiles au jeu (Idle / Walking_A / Death_A), resample + prune +
// dedup via gltf-transform. Lancé par scripts/fetch_3d_assets.sh après copie.
import { readdirSync, statSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { NodeIO } from '@gltf-transform/core'
import { dedup, prune, quantize, resample, weld } from '@gltf-transform/functions'

const root = join(dirname(fileURLToPath(import.meta.url)), '..', 'public', 'models')
const KEEP = /^(idle|walking_a|death_a)$/i
const FALLBACK_KEEP = /idle|walk/i

const io = new NodeIO()
const targets = ['adventurers', 'skeletons']
  .flatMap((dir) => {
    const full = join(root, dir)
    try {
      return readdirSync(full).filter((f) => f.endsWith('.glb')).map((f) => join(full, f))
    } catch {
      return []
    }
  })

let totalBefore = 0
let totalAfter = 0
for (const file of targets) {
  const before = statSync(file).size
  const document = await io.read(file)
  const animations = document.getRoot().listAnimations()
  const names = animations.map((a) => a.getName())
  let keep = animations.filter((a) => KEEP.test(a.getName()))
  if (keep.length === 0) keep = animations.filter((a) => FALLBACK_KEEP.test(a.getName()))
  if (keep.length === 0) keep = animations.slice(0, 2)
  const keepSet = new Set(keep)
  for (const animation of animations) {
    if (!keepSet.has(animation)) animation.dispose()
  }
  // weld+quantize : KHR_mesh_quantization, décodé nativement par GLTFLoader.
  await document.transform(resample(), weld(), quantize(), prune(), dedup())
  await io.write(file, document)
  const after = statSync(file).size
  totalBefore += before
  totalAfter += after
  console.log(
    `${file.split('/').slice(-2).join('/')}: ${(before / 1e6).toFixed(2)}→${(after / 1e6).toFixed(2)} Mo` +
    ` | gardé: ${keep.map((a) => a.getName()).join(', ')} | dispo: ${names.length} clips`,
  )
}
console.log(`TOTAL personnages: ${(totalBefore / 1e6).toFixed(1)} → ${(totalAfter / 1e6).toFixed(1)} Mo`)
