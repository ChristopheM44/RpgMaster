<script setup lang="ts">
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg">
    <h1 class="font-display text-5xl font-bold tracking-widest text-gold">RpgMaster</h1>
    <p class="text-base text-parchment-dark">
      Votre Maître de Jeu propulsé par l'Intelligence Artificielle
    </p>
    <div class="flex gap-4">
      <router-link to="/lobby" class="rpg-btn-primary">
        Nouvelle Partie
      </router-link>
      <router-link to="/lobby" class="rpg-btn-secondary">
        Charger une Partie
      </router-link>
    </div>
  </div>
</template>
