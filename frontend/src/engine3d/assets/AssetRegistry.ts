// Chargement + cache des glTF du manifest. Tout échec (fichier absent, réseau,
// clé inconnue, registre désactivé) résout à null : l'appelant bascule sur la
// fabrique procédurale — le rendu ne casse jamais.

import * as THREE from 'three'
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { clone as cloneSkinned } from 'three/addons/utils/SkeletonUtils.js'
import { MODEL_MANIFEST } from './manifest'

export interface LoadedModel {
  key: string
  prototype: THREE.Group
  animations: THREE.AnimationClip[]
  size: THREE.Vector3
  min: THREE.Vector3
  center: THREE.Vector3
  minY: number
  skinned: boolean
}

export interface InstantiateOptions {
  /** Hauteur cible en unités monde (fit 'height'). */
  targetHeight?: number
  /** Empreinte cible en unités monde (fit 'footprint'). */
  footprint?: { x: number; z: number }
  /** Garde-fou : ne jamais dépasser cette hauteur monde. */
  maxHeight?: number
}

export class AssetRegistry {
  /** Désactivable (tests, mode dégradé) : load() résout alors toujours null. */
  enabled = true

  private loader = new GLTFLoader()
  private cache = new Map<string, Promise<LoadedModel | null>>()
  private warned = new Set<string>()

  constructor(private baseUrl: string = resolveBaseUrl()) {}

  load(key: string): Promise<LoadedModel | null> {
    if (!this.enabled) return Promise.resolve(null)
    const cached = this.cache.get(key)
    if (cached) return cached

    const def = MODEL_MANIFEST[key]
    if (!def) {
      this.warnOnce(`modèle inconnu du manifest: ${key}`)
      return Promise.resolve(null)
    }

    const promise = new Promise<LoadedModel | null>((resolve) => {
      this.loader.load(
        `${this.baseUrl}${def.file}`,
        (gltf) => {
          const prototype = gltf.scene
          let skinned = false
          prototype.traverse((node) => {
            if ((node as THREE.SkinnedMesh).isSkinnedMesh) skinned = true
          })
          const box = new THREE.Box3().setFromObject(prototype)
          const size = box.getSize(new THREE.Vector3())
          const center = box.getCenter(new THREE.Vector3())
          resolve({
            key,
            prototype,
            animations: gltf.animations ?? [],
            size: size.max(new THREE.Vector3(0.001, 0.001, 0.001)),
            min: box.min.clone(),
            center,
            minY: box.min.y,
            skinned,
          })
        },
        undefined,
        () => {
          this.warnOnce(`chargement échoué pour ${key} (${def.file}) — fallback procédural`)
          resolve(null)
        },
      )
    })
    this.cache.set(key, promise)
    return promise
  }

  /**
   * Clone une instance posée au sol (base à y=0), mise à l'échelle selon les
   * options, ombres activées. SkeletonUtils pour les modèles rigged.
   */
  instantiate(model: LoadedModel, options: InstantiateOptions = {}): THREE.Group {
    const instance = (model.skinned ? cloneSkinned(model.prototype) : model.prototype.clone(true)) as THREE.Group

    let scale = 1
    if (options.footprint) {
      scale = Math.min(options.footprint.x / model.size.x, options.footprint.z / model.size.z)
    } else if (options.targetHeight) {
      scale = options.targetHeight / model.size.y
    }
    if (options.maxHeight && model.size.y * scale > options.maxHeight) {
      scale = options.maxHeight / model.size.y
    }

    const container = new THREE.Group()
    instance.scale.setScalar(scale)
    instance.position.y = -model.minY * scale
    instance.traverse((node) => {
      const mesh = node as THREE.Mesh
      if (mesh.isMesh) {
        mesh.castShadow = true
        mesh.receiveShadow = true
      }
    })
    container.add(instance)
    return container
  }

  private warnOnce(message: string): void {
    if (this.warned.has(message)) return
    this.warned.add(message)
    console.warn(`[engine3d] ${message}`)
  }
}

function resolveBaseUrl(): string {
  const base = typeof import.meta !== 'undefined' ? (import.meta.env?.BASE_URL ?? '/') : '/'
  return `${base.endsWith('/') ? base : `${base}/`}models/`
}
