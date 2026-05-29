<script setup lang="ts">
import TtsSettingsPanel from '../components/ui/TtsSettingsPanel.vue'
import LlmProviderPanel from '../components/ui/LlmProviderPanel.vue'
import ImageGenerationPanel from '../components/ui/ImageGenerationPanel.vue'
</script>

<template>
  <div class="min-h-screen bg-ink p-6">
    <div class="max-w-2xl mx-auto space-y-6">
      <!-- En-tête page -->
      <div class="mb-2">
        <h1 class="text-2xl font-bold text-parchment">Administration</h1>
        <p class="text-parchment/60 mt-1">Paramètres du serveur RpgMaster.</p>
      </div>

      <!-- Panel LLM / Provider -->
      <div class="rounded-xl border border-parchment/10 bg-ink/60 p-6">
        <LlmProviderPanel />
      </div>

      <!-- Panel génération image -->
      <div class="rounded-xl border border-parchment/10 bg-ink/60 p-6">
        <ImageGenerationPanel />
      </div>

      <!-- Panel TTS -->
      <div class="rounded-xl border border-parchment/10 bg-ink/60 p-6">
        <TtsSettingsPanel />
      </div>
    </div>
  </div>
</template>
