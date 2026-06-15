import { NodeIO } from '@gltf-transform/core'
import path from 'path'

const io = new NodeIO()
const files = ['stairs.glb', 'wall_doorway.glb', 'wall_corner.glb', 'wall.glb']
const base = 'public/models/dungeon'

function fmt(arr) {
  return '[' + Array.from(arr).map((v) => v.toFixed(3)).join(', ') + ']'
}

// Compose a simple TRS into a 4x4 column-major matrix (gl-matrix convention not needed,
// we just need to transform points: p' = R*S*p + T, with R from quaternion).
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

for (const file of files) {
  const doc = await io.read(path.join(base, file))
  const root = doc.getRoot()
  const scenes = root.listScenes()
  console.log(`\n========== ${file} ==========`)

  let globalMin = [Infinity, Infinity, Infinity]
  let globalMax = [-Infinity, -Infinity, -Infinity]

  function walk(node, depth, parentT, parentR, parentS) {
    const t = node.getTranslation()
    const r = node.getRotation()
    const s = node.getScale()
    const mesh = node.getMesh()
    const indent = '  '.repeat(depth)
    console.log(
      `${indent}Node "${node.getName()}" T=${fmt(t)} R(quat)=${fmt(r)} S=${fmt(s)}` +
        (mesh ? ` MESH="${mesh.getName()}"` : ''),
    )

    // World transform = parent ∘ local (assumes parent has no scale-skew issues; fine for these assets)
    const wt = transformPoint(t, parentT, parentR, parentS)
    // combine rotations by composing quaternions (approx: just chain transformPoint per-level instead)
    // For correctness with nested transforms we instead transform points through the chain explicitly.

    if (mesh) {
      for (const prim of mesh.listPrimitives()) {
        const pos = prim.getAttribute('POSITION')
        if (pos) {
          const arr = pos.getArray()
          let lmin = [Infinity, Infinity, Infinity]
          let lmax = [-Infinity, -Infinity, -Infinity]
          for (let i = 0; i < arr.length; i += 3) {
            for (let k = 0; k < 3; k++) {
              lmin[k] = Math.min(lmin[k], arr[i + k])
              lmax[k] = Math.max(lmax[k], arr[i + k])
            }
          }
          console.log(`${indent}  prim local AABB min=${fmt(lmin)} max=${fmt(lmax)} size=${fmt(lmax.map((v, i) => v - lmin[i]))}`)

          // transform the 8 corners by this node's local transform, then by parent chain (recorded via closures below)
          for (let cx = 0; cx < 2; cx++) {
            for (let cy = 0; cy < 2; cy++) {
              for (let cz = 0; cz < 2; cz++) {
                let corner = [cx ? lmax[0] : lmin[0], cy ? lmax[1] : lmin[1], cz ? lmax[2] : lmin[2]]
                corner = transformPoint(corner, t, r, s)
                corner = applyAncestors(corner, depth)
                for (let k = 0; k < 3; k++) {
                  globalMin[k] = Math.min(globalMin[k], corner[k])
                  globalMax[k] = Math.max(globalMax[k], corner[k])
                }
              }
            }
          }
        }
      }
    }

    ancestorStack.push({ t, r, s })
    for (const child of node.listChildren()) walk(child, depth + 1, t, r, s)
    ancestorStack.pop()
  }

  const ancestorStack = []
  function applyAncestors(point, depth) {
    // ancestorStack currently holds [root..current] local transforms; apply from current's parent up to root
    let p = point
    for (let i = ancestorStack.length - 1; i >= 0; i--) {
      const a = ancestorStack[i]
      p = transformPoint(p, a.t, a.r, a.s)
    }
    return p
  }

  for (const scene of scenes) {
    for (const node of scene.listChildren()) walk(node, 0, [0, 0, 0], [0, 0, 0, 1], [1, 1, 1])
  }

  const size = globalMax.map((v, i) => v - globalMin[i])
  const center = globalMax.map((v, i) => (v + globalMin[i]) / 2)
  console.log(`  >>> GLOBAL AABB min=${fmt(globalMin)} max=${fmt(globalMax)}`)
  console.log(`  >>> size=${fmt(size)} center=${fmt(center)} minY=${globalMin[1].toFixed(3)}`)
}
