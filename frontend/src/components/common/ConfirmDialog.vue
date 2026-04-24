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

const TONE_PRESETS: Record<Tone, { color: string; glow: string; bg: string; icon: string }> = {
  danger:  { color: 'var(--color-blood)',  glow: 'rgba(232,69,69,0.35)',  bg: 'rgba(232,69,69,0.10)',  icon: '⚠' },
  warning: { color: 'var(--color-gold)',   glow: 'rgba(240,199,100,0.35)', bg: 'rgba(240,199,100,0.10)', icon: '⚔' },
  arcane:  { color: 'var(--color-arcane)', glow: 'rgba(192,144,255,0.35)', bg: 'rgba(192,144,255,0.10)', icon: '✦' },
  info:    { color: 'var(--color-teal)',   glow: 'rgba(79,216,192,0.30)',  bg: 'rgba(79,216,192,0.10)',  icon: '?' },
}

const preset = computed(() => TONE_PRESETS[props.tone])
const displayIcon = computed(() => props.icon || preset.value.icon)

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
    class="fixed inset-0 z-[60] flex items-center justify-center p-4"
    :style="{
      background: 'rgba(7, 6, 12, 0.72)',
      backdropFilter: 'blur(6px)',
      WebkitBackdropFilter: 'blur(6px)',
      animation: 'rpg-dialog-fade 120ms ease-out',
    }"
    @click.self="onBackdrop"
  >
    <!-- Panel -->
    <div
      role="dialog"
      aria-modal="true"
      class="relative w-[420px] max-w-full overflow-hidden rounded-[14px] border"
      :style="{
        background: 'linear-gradient(180deg, var(--color-bg-elev), var(--color-bg))',
        borderColor: 'var(--color-border-strong)',
        boxShadow: `0 24px 60px rgba(0,0,0,0.65), 0 0 0 1px ${preset.glow}, 0 0 40px ${preset.glow}`,
        animation: 'rpg-dialog-in 180ms cubic-bezier(.22,1,.36,1)',
      }"
    >
      <!-- Bandeau supérieur coloré selon la tonalité -->
      <div
        class="h-[3px] w-full"
        :style="{
          background: `linear-gradient(90deg, transparent, ${preset.color}, transparent)`,
        }"
      />

      <!-- Glow radial derrière l'icône -->
      <div
        aria-hidden="true"
        class="pointer-events-none absolute"
        :style="{
          top: '-60px', left: '50%', transform: 'translateX(-50%)',
          width: '220px', height: '220px', borderRadius: '50%',
          background: `radial-gradient(circle, ${preset.glow}, transparent 70%)`,
        }"
      />

      <div class="relative px-8 pt-7 pb-6">
        <!-- Icône dans un médaillon -->
        <div class="mb-4 flex justify-center">
          <div
            class="flex h-14 w-14 items-center justify-center rounded-full text-[26px] font-bold"
            :style="{
              background: preset.bg,
              border: `1px solid ${preset.color}50`,
              color: preset.color,
              boxShadow: `0 0 24px ${preset.glow}, inset 0 0 12px ${preset.glow}`,
            }"
          >
            {{ displayIcon }}
          </div>
        </div>

        <!-- Eyebrow -->
        <div
          class="mb-2 text-center text-[10px] font-bold uppercase tracking-[0.25em]"
          :style="{ color: preset.color }"
        >
          <span class="rpg-sparkle">✦</span>
          <span>Confirmation requise</span>
        </div>

        <!-- Titre -->
        <h2
          class="mb-2 text-center font-display text-[22px] font-bold leading-[1.15] tracking-wide"
          :style="{ color: 'var(--color-parchment)' }"
        >{{ title }}</h2>

        <!-- Message -->
        <p
          v-if="message"
          class="mx-auto mb-6 max-w-[320px] text-center font-serif text-[14px] italic leading-relaxed"
          :style="{ color: 'var(--color-parchment-dark)', textWrap: 'pretty' }"
        >{{ message }}</p>

        <!-- Slot pour contenu custom (liste, warning supplémentaire…) -->
        <div v-if="$slots.default" class="mb-5">
          <slot />
        </div>

        <!-- Séparateur éditorial -->
        <div
          class="mx-auto mb-5 h-px w-24"
          :style="{ background: `linear-gradient(90deg, transparent, ${preset.color}50, transparent)` }"
        />

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
