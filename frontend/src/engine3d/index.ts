// Point d'entrée du moteur 3D — importé dynamiquement par Scene3DCanvas.vue
// pour que three parte dans un chunk séparé, chargé seulement en session.

export { createSceneRuntime } from './core/SceneRuntime'
export * from './types'
