import { createRouter, createWebHistory } from 'vue-router'
import HomeView from '../views/HomeView.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView,
    },
    {
      path: '/lobby',
      name: 'lobby',
      component: () => import('../views/LobbyView.vue'),
    },
    {
      path: '/session/:id/characters',
      name: 'character-creation',
      component: () => import('../views/CharacterCreationView.vue'),
    },
    {
      path: '/session/:id/play',
      name: 'game-session',
      component: () => import('../views/GameSessionView.vue'),
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
    },
  ],
})

export default router
