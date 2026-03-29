<script setup lang="ts">
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center">
    <h1 class="mb-4 text-6xl font-bold text-gold">RpgMaster</h1>
    <p class="mb-8 text-xl text-parchment-dark">
      Votre Maitre de Jeu propulse par l'Intelligence Artificielle
    </p>
    <div class="flex gap-4">
      <router-link
        to="/lobby"
        class="rounded-lg bg-blood px-6 py-3 font-display text-lg text-parchment transition hover:bg-blood-light"
      >
        Nouvelle Partie
      </router-link>
      <router-link
        to="/lobby"
        class="rounded-lg border border-gold px-6 py-3 font-display text-lg text-gold transition hover:bg-gold hover:text-ink"
      >
        Charger une Partie
      </router-link>
    </div>
  </div>
</template>
