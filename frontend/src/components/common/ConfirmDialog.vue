<script setup lang="ts">
import { onMounted, onBeforeUnmount, computed } from 'vue'

/**
 * Dialogue de confirmation — style Direction 3 (éditorial / obsidienne).
 *
 * Usage :
 *   <ConfirmDialog
 *     v-if="confirmOpen"
 *     title="Lâcher cet objet ?"
 *     message="Cette action est irréversible."
 *     confirm-label="Confirmer"
 *     tone="danger"
 *     @confirm="doIt"
 *     @cancel="confirmOpen = false"
 *   />
 *
 * Tonalités : 'danger' (rouge), 'warning' (or), 'arcane' (violet), 'info' (neutre).
 */

type Tone = 'danger' | 'warning' | 'arcane' | 'info'

const props = withDefaults(
  defineProps<{
    title: string
    message?: string
    confirmLabel?: string
    cancelLabel?: string
    tone?: Tone
    icon?: string          // Glyphe (✦, ⚠, ⚔, ☽…). Défaut selon tonalité.
    loading?: boolean
    /** Désactive la fermeture au clic hors fenêtre (utile pendant loading) */
    persistent?: boolean
  }>(),
  {
    message: '',
    confirmLabel: 'Confirmer',
    cancelLabel: 'Annuler',
    tone: 'danger',
    icon: '',
    loading: false,
    persistent: false,
  },
)

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

// ─── Tonalités ────────────────────────────────────────────────────────────

const TONE_ICONS: Record<Tone, string> = {
  danger: '⚠',
  warning: '⚔',
  arcane: '✦',
  info: '?',
}

const TONE_CLASSES: Record<Tone, string> = {
  danger: 'rpg-tone-blood',
  warning: 'rpg-tone-gold',
  arcane: 'rpg-tone-arcane',
  info: 'rpg-tone-teal',
}

const toneClass = computed(() => TONE_CLASSES[props.tone])
const displayIcon = computed(() => props.icon || TONE_ICONS[props.tone])

// ─── Fermeture Escape + backdrop ──────────────────────────────────────────

function onEsc(e: KeyboardEvent) {
  if (e.key === 'Escape' && !props.loading && !props.persistent) emit('cancel')
}
onMounted(() => window.addEventListener('keydown', onEsc))
onBeforeUnmount(() => window.removeEventListener('keydown', onEsc))

function onBackdrop() {
  if (props.loading || props.persistent) return
  emit('cancel')
}
</script>

<template>
  <!-- Backdrop -->
  <div
    class="rpg-modal-backdrop fixed inset-0 z-[60] flex items-center justify-center p-4"
    @click.self="onBackdrop"
  >
    <!-- Panel -->
    <div
      role="dialog"
      aria-modal="true"
      class="rpg-dialog-panel relative w-[420px] max-w-full overflow-hidden rounded-[14px] border"
      :class="toneClass"
    >
      <!-- Bandeau supérieur coloré selon la tonalité -->
      <div class="rpg-dialog-bar h-[3px] w-full" />

      <!-- Glow radial derrière l'icône -->
      <div
        aria-hidden="true"
        class="rpg-dialog-glow pointer-events-none absolute"
      />

      <div class="relative px-8 pt-7 pb-6">
        <!-- Icône dans un médaillon -->
        <div class="mb-4 flex justify-center">
          <div
            class="rpg-dialog-icon flex h-14 w-14 items-center justify-center rounded-full text-[26px] font-bold"
          >
            {{ displayIcon }}
          </div>
        </div>

        <!-- Eyebrow -->
        <div
          class="rpg-tone-text mb-2 text-center text-[10px] font-bold uppercase tracking-[0.25em]"
        >
          <span class="rpg-sparkle">✦</span>
          <span>Confirmation requise</span>
        </div>

        <!-- Titre -->
        <h2
          class="rpg-text-main mb-2 text-center font-display text-[22px] font-bold leading-[1.15] tracking-wide"
        >{{ title }}</h2>

        <!-- Message -->
        <p
          v-if="message"
          class="rpg-text-secondary rpg-pretty mx-auto mb-6 max-w-[320px] text-center font-serif text-[14px] italic leading-relaxed"
        >{{ message }}</p>

        <!-- Slot pour contenu custom (liste, warning supplémentaire…) -->
        <div v-if="$slots.default" class="mb-5">
          <slot />
        </div>

        <!-- Séparateur éditorial -->
        <div class="rpg-dialog-divider mx-auto mb-5 h-px w-24" />

        <!-- Actions -->
        <div class="flex gap-3">
          <button
            type="button"
            class="rpg-btn-secondary flex-1 justify-center"
            :disabled="loading"
            @click="emit('cancel')"
          >{{ cancelLabel }}</button>

          <button
            type="button"
            class="flex-1 justify-center"
            :class="[
              'inline-flex items-center justify-center gap-1.5 rounded-md px-4 py-2.5',
              'text-[12px] font-bold uppercase tracking-[0.1em] transition',
              tone === 'danger' ? 'rpg-btn-tonal tone-blood'  : '',
              tone === 'warning'? 'rpg-btn-primary'           : '',
              tone === 'arcane' ? 'rpg-btn-tonal tone-arcane' : '',
              tone === 'info'   ? 'rpg-btn-tonal tone-teal'   : '',
            ]"
            :disabled="loading"
            @click="emit('confirm')"
          >
            <span v-if="loading" class="rpg-pulse">…</span>
            <template v-else>
              <span>{{ confirmLabel }}</span>
              <span aria-hidden="true">→</span>
            </template>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
@keyframes rpg-dialog-fade {
  from { opacity: 0; }
  to   { opacity: 1; }
}
@keyframes rpg-dialog-in {
  from { opacity: 0; transform: translateY(8px) scale(0.97); }
  to   { opacity: 1; transform: translateY(0)   scale(1); }
}
</style>
