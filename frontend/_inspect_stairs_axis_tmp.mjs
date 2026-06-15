import { NodeIO } from '@gltf-transform/core'
import path from 'path'

const io = new NodeIO()
const base = 'public/models/dungeon'

function quatToMat3(q) {
  const [x, y, z, w] = q
  const x2 = x + x, y2 = y + y, z2 = z + z
  const xx = x * x2, xy = x * y2, xz = x * z2
  const yy = y * y2, yz = y * z2, zz = z * z2
  const wx = w * x2, wy = w * y2, wz = w * z2
  return [
    [1 - (yy + zz), xy - wz, xz + wy],
    [xy + wz, 1 - (xx + zz), yz - wx],
    [xz - wy, yz + wx, 1 - (xx + yy)],
  ]
}

function transformPoint(p, t, r, s) {
  const R = quatToMat3(r)
  const sx = p[0] * s[0], sy = p[1] * s[1], sz = p[2] * s[2]
  return [
    R[0][0] * sx + R[0][1] * sy + R[0][2] * sz + t[0],
    R[1][0] * sx + R[1][1] * sy + R[1][2] * sz + t[1],
    R[2][0] * sx + R[2][1] * sy + R[2][2] * sz + t[2],
  ]
}

const doc = await io.read(path.join(base, 'stairs.glb'))
const root = doc.getRoot()

const points = []

function walk(node, ancestors) {
  const t = node.getTranslation()
  const r = node.getRotation()
  const s = node.getScale()
  const mesh = node.getMesh()

  if (mesh) {
    for (const prim of mesh.listPrimitives()) {
      const pos = prim.getAttribute('POSITION')
      if (pos) {
        const arr = pos.getArray()
        for (let i = 0; i < arr.length; i += 3) {
          let p = [arr[i], arr[i + 1], arr[i + 2]]
          p = transformPoint(p, t, r, s)
          for (let a = ancestors.length - 1; a >= 0; a--) {
            p = transformPoint(p, ancestors[a].t, ancestors[a].r, ancestors[a].s)
          }
          points.push(p)
        }
      }
    }
  }

  const nextAncestors = [...ancestors, { t, r, s }]
  for (const child of node.listChildren()) walk(child, nextAncestors)
}

for (const scene of root.listScenes()) {
  for (const node of scene.listChildren()) walk(node, [])
}

console.log(`stairs.glb : ${points.length} vertices`)

let zmin = Infinity, zmax = -Infinity
for (const p of points) {
  zmin = Math.min(zmin, p[2])
  zmax = Math.max(zmax, p[2])
}
console.log(`Z range: [${zmin.toFixed(3)}, ${zmax.toFixed(3)}]`)

// Bin into 8 slices along Z, report mean Y per slice + Y range per slice
const bins = 8
const sums = new Array(bins).fill(0)
const counts = new Array(bins).fill(0)
const ymins = new Array(bins).fill(Infinity)
const ymaxs = new Array(bins).fill(-Infinity)
const span = zmax - zmin

for (const p of points) {
  let bin = Math.floor(((p[2] - zmin) / span) * bins)
  if (bin >= bins) bin = bins - 1
  sums[bin] += p[1]
  counts[bin] += 1
  ymins[bin] = Math.min(ymins[bin], p[1])
  ymaxs[bin] = Math.max(ymaxs[bin], p[1])
}

console.log('\nZ-bin -> meanY (n) [yMin, yMax]')
for (let b = 0; b < bins; b++) {
  const z0 = zmin + (span * b) / bins
  const z1 = zmin + (span * (b + 1)) / bins
  const mean = counts[b] ? sums[b] / counts[b] : NaN
  console.log(
    `  Z[${z0.toFixed(2)}, ${z1.toFixed(2)}) -> meanY=${mean.toFixed(3)} (n=${counts[b]}) [${ymins[b].toFixed(3)}, ${ymaxs[b].toFixed(3)}]`,
  )
}

// Same analysis along X, in case the ramp runs along X instead of Z
let xmin = Infinity, xmax = -Infinity
for (const p of points) {
  xmin = Math.min(xmin, p[0])
  xmax = Math.max(xmax, p[0])
}
console.log(`\nX range: [${xmin.toFixed(3)}, ${xmax.toFixed(3)}]`)

const sumsX = new Array(bins).fill(0)
const countsX = new Array(bins).fill(0)
const spanX = xmax - xmin
for (const p of points) {
  let bin = Math.floor(((p[0] - xmin) / spanX) * bins)
  if (bin >= bins) bin = bins - 1
  sumsX[bin] += p[1]
  countsX[bin] += 1
}
console.log('\nX-bin -> meanY (n)')
for (let b = 0; b < bins; b++) {
  const x0 = xmin + (spanX * b) / bins
  const x1 = xmin + (spanX * (b + 1)) / bins
  const mean = countsX[b] ? sumsX[b] / countsX[b] : NaN
  console.log(`  X[${x0.toFixed(2)}, ${x1.toFixed(2)}) -> meanY=${mean.toFixed(3)} (n=${countsX[b]})`)
}
