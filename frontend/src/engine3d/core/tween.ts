// Mini-système de tweens piloté par la boucle rAF du runtime — déplace les
// tokens (lerp/chemin) et anime anneaux/pulses sans dépendance externe.

export interface Tween {
  /** Avance le tween ; retourne true quand il est terminé. */
  update(dt: number): boolean
  cancel(): void
}

export class TweenGroup {
  private tweens = new Set<Tween>()

  add(tween: Tween): void {
    this.tweens.add(tween)
  }

  update(dt: number): void {
    for (const tween of this.tweens) {
      if (tween.update(dt)) this.tweens.delete(tween)
    }
  }

  cancel(tween: Tween | null | undefined): void {
    if (!tween) return
    tween.cancel()
    this.tweens.delete(tween)
  }

  clear(): void {
    this.tweens.clear()
  }
}

export function easeInOut(t: number): number {
  return t < 0.5 ? 2 * t * t : 1 - (-2 * t + 2) ** 2 / 2
}

interface Vec3Like {
  x: number
  y: number
  z: number
  set(x: number, y: number, z: number): unknown
}

/** Lerp d'une position vers une cible en `duration` secondes. */
export function tweenTo(
  target: Vec3Like,
  to: { x: number; y: number; z: number },
  duration: number,
  onComplete?: () => void,
): Tween {
  const from = { x: target.x, y: target.y, z: target.z }
  let elapsed = 0
  let cancelled = false
  return {
    update(dt: number): boolean {
      if (cancelled) return true
      elapsed += dt
      const t = duration <= 0 ? 1 : Math.min(1, elapsed / duration)
      const k = easeInOut(t)
      target.set(from.x + (to.x - from.x) * k, from.y + (to.y - from.y) * k, from.z + (to.z - from.z) * k)
      if (t >= 1) {
        onComplete?.()
        return true
      }
      return false
    },
    cancel() {
      cancelled = true
    },
  }
}

/**
 * Suit un chemin de points à vitesse constante (unités monde/s).
 * `onStep` reçoit l'index du segment courant (orientation du modèle).
 */
export function tweenPath(
  target: Vec3Like,
  points: { x: number; y: number; z: number }[],
  speed: number,
  onStep?: (segment: number, direction: { x: number; z: number }) => void,
  onComplete?: () => void,
): Tween {
  if (points.length === 0) {
    return { update: () => true, cancel: () => undefined }
  }
  let segment = 0
  let progress = 0
  let cancelled = false
  let current = { x: target.x, y: target.y, z: target.z }
  let notified = -1

  return {
    update(dt: number): boolean {
      if (cancelled) return true
      let remaining = dt * Math.max(0.01, speed)
      while (remaining > 0 && segment < points.length) {
        const next = points[segment]
        if (!next) break
        const dx = next.x - current.x
        const dy = next.y - current.y
        const dz = next.z - current.z
        const dist = Math.hypot(dx, dy, dz)
        if (notified !== segment && dist > 1e-4) {
          onStep?.(segment, { x: dx / dist, z: dz / dist })
          notified = segment
        }
        const left = dist - progress
        if (remaining >= left) {
          remaining -= left
          current = { x: next.x, y: next.y, z: next.z }
          target.set(next.x, next.y, next.z)
          segment += 1
          progress = 0
        } else {
          progress += remaining
          const k = dist <= 1e-6 ? 1 : progress / dist
          target.set(current.x + dx * k, current.y + dy * k, current.z + dz * k)
          remaining = 0
        }
      }
      if (segment >= points.length) {
        onComplete?.()
        return true
      }
      return false
    },
    cancel() {
      cancelled = true
    },
  }
}
