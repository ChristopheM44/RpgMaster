<script setup lang="ts">
import { ref } from 'vue'
import TtsSettingsPanel from '../components/ui/TtsSettingsPanel.vue'
import LlmProviderPanel from '../components/ui/LlmProviderPanel.vue'
import ImageGenerationPanel from '../components/ui/ImageGenerationPanel.vue'

type AdminTab = 'text' | 'image' | 'voice'

const activeTab = ref<AdminTab>('text')

const tabs: Array<{ id: AdminTab; label: string; detail: string }> = [
  { id: 'text', label: 'Texte', detail: 'LLM' },
  { id: 'image', label: 'Image', detail: 'Cartes' },
  { id: 'voice', label: 'Voix', detail: 'TTS' },
]
</script>

<template>
  <div class="min-h-screen bg-ink p-6">
    <div class="mx-auto max-w-4xl space-y-6">
      <!-- En-tête page -->
      <div class="mb-2">
        <h1 class="text-2xl font-bold text-parchment">Administration</h1>
        <p class="text-parchment/60 mt-1">Paramètres du serveur RpgMaster.</p>
      </div>

      <div class="flex gap-2 rounded-xl border border-parchment/10 bg-ink/50 p-1">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          type="button"
          :class="[
            'flex-1 rounded-lg px-4 py-3 text-left transition-colors',
            activeTab === tab.id
              ? 'bg-gold/10 text-gold ring-1 ring-gold/30'
              : 'text-parchment/60 hover:bg-parchment/5 hover:text-parchment',
          ]"
          @click="activeTab = tab.id"
        >
          <span class="block font-display text-sm font-bold uppercase tracking-[0.12em]">
            {{ tab.label }}
          </span>
          <span class="block text-xs font-mono opacity-60">{{ tab.detail }}</span>
        </button>
      </div>

      <div class="rounded-xl border border-parchment/10 bg-ink/60 p-6">
        <LlmProviderPanel v-if="activeTab === 'text'" />
        <ImageGenerationPanel v-else-if="activeTab === 'image'" />
        <TtsSettingsPanel v-else />
      </div>
    </div>
  </div>
</template>
