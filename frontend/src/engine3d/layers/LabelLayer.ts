// Étiquettes DOM projetées au-dessus de la scène 3D (lot 3, décision « étiquettes
// en DOM ») : noms des personnages (rôle + PV), repères (✦ titre), bannières de
// sortie cliquables (sens + destination). Nettes à tout zoom, polices du design
// system ; les styles `.e3d-*` vivent dans Scene3DCanvas.vue. Anti-chevauchement :
// les plus proches de la caméra restent en place, les autres remontent.

import * as THREE from 'three'
import type { ExitDirection, PoiRole, TokenSpec } from '../types'

type LabelKind = 'plate' | 'pin' | 'banner'

interface LabelEntry {
  el: HTMLElement
  kind: LabelKind
  key: string
  /** Décalage monde au-dessus de l'ancre du jeton. */
  lift: number
  size: { w: number; h: number } | null
}

const EXIT_GLYPH: Record<ExitDirection, string> = { travel: '→', up: '↑', down: '↓' }
const EXIT_KICKER: Record<ExitDirection, string> = { travel: 'Sortie', up: 'Monter', down: 'Descendre' }
const POI_GLYPH: Record<PoiRole, string> = { clue: '✦', loot: '▣', cover: '◆', hazard: '⚠', point: '✦' }

export interface LabelCallbacks {
  onExitClick(id: string, screen: { x: number; y: number }): void
}

export class LabelLayer {
  private root: HTMLElement | null = null
  private entries = new Map<string, LabelEntry>()
  private specs: TokenSpec[] = []
  private readonly projected = new THREE.Vector3()

  constructor(private callbacks: LabelCallbacks) {}

  attach(root: HTMLElement | null): void {
    if (root === this.root) return
    this.clear()
    this.root = root
    this.sync(this.specs)
  }

  sync(specs: TokenSpec[]): void {
    this.specs = specs
    if (!this.root) return
    const seen = new Set<string>()
    for (const spec of specs) {
      const label = describe(spec)
      if (!label) continue
      seen.add(spec.id)
      const existing = this.entries.get(spec.id)
      if (existing && existing.key === label.key) continue
      if (existing) existing.el.remove()
      const el = this.build(spec, label)
      this.root.appendChild(el)
      this.entries.set(spec.id, { el, kind: label.kind, key: label.key, lift: label.lift, size: null })
    }
    for (const [id, entry] of this.entries) {
      if (!seen.has(id)) {
        entry.el.remove()
        this.entries.delete(id)
      }
    }
  }

  /** Projette et place les étiquettes (appelé à chaque frame). */
  tick(
    camera: THREE.Camera,
    width: number,
    height: number,
    anchor: (id: string) => THREE.Vector3 | null,
  ): void {
    if (!this.root || this.entries.size === 0) return
    const items: { entry: LabelEntry; x: number; y: number; depth: number }[] = []
    for (const [id, entry] of this.entries) {
      const world = anchor(id)
      if (!world) {
        entry.el.style.display = 'none'
        continue
      }
      this.projected.set(world.x, world.y + entry.lift, world.z).project(camera)
      const x = (this.projected.x * 0.5 + 0.5) * width
      const y = (-this.projected.y * 0.5 + 0.5) * height
      const offscreen = this.projected.z > 1 || x < -80 || x > width + 80 || y < -40 || y > height + 60
      entry.el.style.display = offscreen ? 'none' : ''
      if (!offscreen) items.push({ entry, x, y, depth: this.projected.z })
    }
    // Bannières d'abord (fixes), puis noms et repères du plus proche au plus lointain.
    items.sort((a, b) => Number(b.entry.kind === 'banner') - Number(a.entry.kind === 'banner') || a.depth - b.depth)
    const placed: { x: number; y: number; w: number; h: number }[] = []
    for (const item of items) {
      const size = item.entry.size ?? measure(item.entry)
      if (item.entry.kind !== 'banner') {
        for (let pass = 0; pass < 6; pass++) {
          const hit = placed.find((p) => Math.abs(p.x - item.x) < (p.w + size.w) / 2 + 2
            && Math.abs((p.y - p.h / 2) - (item.y - size.h / 2)) < (p.h + size.h) / 2 + 1)
          if (!hit) break
          item.y = hit.y - hit.h - 2
        }
      }
      placed.push({ x: item.x, y: item.y, w: size.w, h: size.h })
      item.entry.el.style.transform = `translate(${Math.round(item.x)}px, ${Math.round(item.y)}px) translate(-50%, -100%)`
    }
  }

  dispose(): void {
    this.clear()
    this.root = null
    this.specs = []
  }

  private clear(): void {
    for (const entry of this.entries.values()) entry.el.remove()
    this.entries.clear()
  }

  private build(spec: TokenSpec, label: LabelDescription): HTMLElement {
    const doc = this.root!.ownerDocument
    if (label.kind === 'banner') {
      const button = doc.createElement('button')
      button.type = 'button'
      button.className = label.className
      const dir = doc.createElement('span')
      dir.className = 'e3d-banner-dir'
      dir.textContent = label.glyph
      const text = doc.createElement('span')
      text.className = 'e3d-banner-text'
      const kicker = doc.createElement('b')
      kicker.textContent = label.kicker
      const name = doc.createElement('span')
      name.textContent = spec.name
      text.append(kicker, name)
      button.append(dir, text)
      button.title = `${label.kicker} · ${spec.name}`
      button.addEventListener('click', (event) => {
        event.stopPropagation()
        const rect = button.getBoundingClientRect()
        const rootRect = this.root?.getBoundingClientRect()
        this.callbacks.onExitClick(spec.id, {
          x: rect.left + rect.width / 2 - (rootRect?.left ?? 0),
          y: rect.top - (rootRect?.top ?? 0),
        })
      })
      return button
    }
    const el = doc.createElement('div')
    el.className = label.className
    if (label.kind === 'pin') {
      const glyph = doc.createElement('span')
      glyph.className = 'e3d-pin-glyph'
      glyph.textContent = label.glyph
      el.append(glyph, doc.createTextNode(spec.name))
      return el
    }
    const name = doc.createElement('span')
    name.className = 'e3d-plate-name'
    name.textContent = spec.name
    el.append(name)
    if (spec.hpRatio !== null) {
      const ratio = Math.max(0, Math.min(1, spec.hpRatio))
      const bar = doc.createElement('span')
      bar.className = 'e3d-plate-hp'
      const fill = doc.createElement('i')
      fill.style.width = `${Math.round(ratio * 100)}%`
      fill.className = ratio > 0.5 ? 'is-ok' : ratio > 0.25 ? 'is-hurt' : 'is-critical'
      bar.append(fill)
      el.append(bar)
    }
    return el
  }
}

interface LabelDescription {
  kind: LabelKind
  key: string
  className: string
  lift: number
  glyph: string
  kicker: string
}

/** Description d'étiquette d'un jeton (null = pas d'étiquette, ex. danger au sol). Pur. */
export function describe(spec: TokenSpec): LabelDescription | null {
  const state = `${spec.selected ? ' is-selected' : ''}${spec.highlighted ? ' is-highlighted' : ''}`
  if (spec.kind === 'exit') {
    const direction = spec.exitDirection ?? 'travel'
    const kicker = spec.arrival ? `Arrivée · ${EXIT_KICKER[direction].toLowerCase()}` : EXIT_KICKER[direction]
    const tone = spec.arrival ? ' is-arrival' : spec.exitActive ? '' : ' is-inactive'
    return {
      kind: 'banner',
      key: `banner|${spec.name}|${direction}|${tone}|${state}`,
      className: `e3d-label e3d-banner${tone}${state}`,
      lift: 0.15,
      glyph: EXIT_GLYPH[direction],
      kicker,
    }
  }
  if (spec.kind === 'poi') {
    const role = spec.poiRole ?? 'point'
    if (role === 'hazard') return null
    return {
      kind: 'pin',
      key: `pin|${spec.name}|${role}|${state}`,
      className: `e3d-label e3d-pin e3d-poi-${role}${state}`,
      lift: 0.3,
      glyph: POI_GLYPH[role],
      kicker: '',
    }
  }
  const role = spec.role ?? (spec.kind === 'npc' ? 'npc' : 'ally')
  return {
    kind: 'plate',
    key: `plate|${spec.name}|${role}|${spec.hpRatio?.toFixed(2) ?? 'x'}|${spec.defeated}|${spec.active}|${state}`,
    className: `e3d-label e3d-plate e3d-role-${role}${spec.defeated ? ' is-defeated' : ''}${spec.active ? ' is-active' : ''}${state}`,
    lift: 0.08,
    glyph: '',
    kicker: '',
  }
}

function measure(entry: LabelEntry): { w: number; h: number } {
  const size = { w: entry.el.offsetWidth || 60, h: entry.el.offsetHeight || 18 }
  if (entry.el.offsetWidth) entry.size = size
  return size
}
