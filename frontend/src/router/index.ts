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
      path: '/session/:id/setup',
      name: 'character-setup',
      component: () => import('../views/CharacterSetupView.vue'),
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
      path: '/character/:charId',
      name: 'character-sheet',
      component: () => import('../views/CharacterSheetView.vue'),
    },
    {
      path: '/admin',
      name: 'admin',
      component: () => import('../views/AdminView.vue'),
    },
    {
      path: '/campaigns',
      name: 'campaigns',
      component: () => import('../views/CampaignView.vue'),
    },
    {
      path: '/grimoire',
      name: 'grimoire',
      component: () => import('../views/SpellsView.vue'),
      meta: { title: 'Grimoire' },
    },
    {
      path: '/bestiaire',
      name: 'bestiaire',
      component: () => import('../views/MonstersView.vue'),
      meta: { title: 'Bestiaire' },
    },
  ],
})

export default router
