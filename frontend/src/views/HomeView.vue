<script setup lang="ts">
</script>

<template>
  <div class="flex min-h-screen flex-col items-center justify-center gap-6 bg-bg">
    <h1 class="font-display text-5xl font-bold tracking-widest text-gold">RpgMaster</h1>
    <p class="text-base text-parchment-dark">
      Votre Maître de Jeu propulsé par l'Intelligence Artificielle
    </p>
    <div class="flex gap-4">
      <router-link to="/campaigns?forge=1" class="rpg-btn-primary">
        Nouvelle Chronique
      </router-link>
      <router-link to="/campaigns" class="rpg-btn-secondary">
        Reprendre une Chronique
      </router-link>
    </div>
  </div>
</template>
