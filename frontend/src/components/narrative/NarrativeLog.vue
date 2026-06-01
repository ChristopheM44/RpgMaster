<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useGameStore } from '../../stores/game'
import { useNarrativeStore } from '../../stores/narrative'
import { useSessionStore } from '../../stores/session'
import { useCharacterStore } from '../../stores/character'
import DiceRollResult from './DiceRollResult.vue'
import NarrativeEntry from '../exploration/NarrativeEntry.vue'
import type { NarrativeEntry as NarrativeEntryModel } from '../../types'

withDefaults(defineProps<{
  /**
   * 'full'   — the standalone exploration layout (default, unchanged)
   * 'drawer' — compact V2 combat drawer: slim header + NarrativeEntry partagé
   */
  variant?: 'full' | 'drawer'
}>(), { variant: 'full' })

const gameStore = useGameStore()
const narrativeStore = useNarrativeStore()
const sessionStore = useSessionStore()
const characterStore = useCharacterStore()
const logEl = ref<HTMLElement | null>(null)

/** IDs des compagnons IA pour distinguer leurs actions du joueur humain */
const aiCharIds = computed(() =>
  new Set(characterStore.sessionCharacters.filter(c => c.is_ai).map(c => c.id)),
)
const hasThinkingEntry = computed(() =>
  gameStore.isProcessing || gameStore.isGmThinking || gameStore.isPlayerAiThinking,
)
const thinkingLabel = computed(() =>
  gameStore.isPlayerAiThinking && !gameStore.isGmThinking
    ? 'Le joueur IA réfléchit'
    : 'Le Maître du Jeu réfléchit',
)

function audioStatusFor(entry: NarrativeEntryModel) {
  return entry.narration_id ? gameStore.audioStatusByNarrationId[entry.narration_id] : undefined
}

function audioStatusLabel(entry: NarrativeEntryModel): string {
  const status = audioStatusFor(entry)
  if (!status) return ''
  return status.status === 'error' ? 'Voix indisponible' : 'Voix en génération'
}

watch(
  () => narrativeStore.entries.length + gameStore.narrativeLog.length + (hasThinkingEntry.value ? 1 : 0),
  async () => {
    await nextTick()
    if (logEl.value) {
      logEl.value.scrollTop = logEl.value.scrollHeight
    }
  },
)
</script>

<template>
  <!-- ══ DRAWER variant (V2 combat sidebar) ════════════════════════════════════ -->
  <template v-if="variant === 'drawer'">
    <!-- Drawer header -->
    <div class="recit-drawer-header">
      <span style="color: var(--color-ember); font-size: 12px">✦</span>
      <h2 class="recit-drawer-title">Récit</h2>
      <div style="flex: 1" />
      <span class="recit-round-badge">R{{ gameStore.roundNumber || 1 }}</span>
      <button
        class="recit-collapse-btn"
        title="Replier"
        @click="sessionStore.recitOpen = false"
      >▶</button>
    </div>

    <!-- Log compact — NarrativeEntry partagé avec l'exploration -->
    <div ref="logEl" class="recit-drawer-log">
      <p v-if="narrativeStore.entries.length === 0" class="recit-empty">
        En attente…
      </p>

      <NarrativeEntry
        v-for="entry in narrativeStore.entries"
        :key="entry.id"
        :entry="entry"
        :compact="true"
      />

      <!-- Indicateur "réfléchit" — état live hors ExNarrativeEntry -->
      <div v-if="hasThinkingEntry" class="recit-thinking">
        <span class="recit-thinking-label">{{ thinkingLabel }}</span>
        <span class="recit-thinking-dots">
          <span v-for="d in ['0ms', '150ms', '300ms']" :key="d"
            class="recit-thinking-dot"
            :style="{ animationDelay: d }" />
        </span>
      </div>
    </div>
  </template>

  <!-- ══ FULL variant (exploration / standalone) ═══════════════════════════════ -->
  <div v-else class="flex flex-1 min-h-0 flex-col overflow-hidden">

    <!-- Big section heading -->
    <div
      class="flex shrink-0 items-baseline gap-4 px-10 pt-8 pb-4"
    >
      <h2
        class="rpg-text-main font-display text-[32px] font-bold tracking-[0.05em] leading-none"
      >
        <span class="rpg-text-ember">✦</span>
        Récit
      </h2>
      <div class="rpg-divider flex-1 h-px" />
    </div>

    <!-- Log -->
    <div
      ref="logEl"
      class="flex-1 overflow-y-auto px-10 pb-6 space-y-6"
    >
      <p
        v-if="gameStore.narrativeLog.length === 0"
        class="rpg-text-muted mt-16 text-center font-serif italic text-lg"
      >
        En attente du début de la session…
      </p>

      <template v-for="entry in gameStore.narrativeLog" :key="entry.id">

        <!-- Narration GM -->
        <div v-if="entry.type === 'narration'" class="space-y-3">
          <div class="flex flex-wrap items-center gap-2">
            <div class="rpg-eyebrow">
              ✦ {{ entry.speaker ?? 'Maître du Jeu' }}
            </div>
            <span
              v-if="audioStatusFor(entry)"
              class="rpg-audio-status"
              :class="{ 'is-error': audioStatusFor(entry)?.status === 'error' }"
            >
              {{ audioStatusLabel(entry) }}
            </span>
          </div>
          <p
            class="rpg-text-secondary font-serif leading-[1.8] text-[17px] text-pretty"
          >{{ entry.text }}</p>
        </div>

        <!-- Dialogue joueur humain parlant via type dialogue — gold ◉ -->
        <div
          v-else-if="entry.type === 'dialogue' && entry.speaker_kind === 'human'"
          class="rpg-player-entry flex gap-3 rounded-lg border-l-2 py-2 pl-4 pr-3"
          style="border-color: rgba(240,199,100,0.35); background: rgba(240,199,100,0.03);"
        >
          <div class="min-w-0 flex-1">
            <span
              v-if="entry.speaker"
              class="mr-2 text-[10px] font-display font-bold tracking-wide uppercase"
              style="color: var(--color-gold);"
            >◉ {{ entry.speaker }} </span>
            <span
              class="text-[12.5px] font-serif italic"
              style="color: var(--color-text-muted);"
            >« {{ entry.text }} »</span>
          </div>
        </div>

        <!-- Dialogue compagnon IA / PNJ -->
        <div
          v-else-if="entry.type === 'dialogue'"
          class="rpg-dialogue-entry flex gap-3 rounded-lg border-l-2 py-2.5 pl-4 pr-3"
          :class="entry.speaker_kind === 'companion' ? 'is-companion' : 'is-npc'"
          :style="entry.speaker_kind === 'companion'
            ? 'border-color: rgba(192,144,255,0.45); background: rgba(192,144,255,0.04)'
            : 'border-color: rgba(79,216,192,0.45); background: rgba(79,216,192,0.04)'"
        >
          <div class="min-w-0 flex-1">
            <span
              v-if="entry.speaker"
              class="mr-2 text-sm font-display font-semibold"
              :class="entry.speaker_kind === 'companion' ? 'rpg-text-arcane' : 'rpg-text-teal'"
            >{{ entry.speaker_kind === 'companion' ? '◈' : '❦' }} {{ entry.speaker }} </span>
            <span
              v-if="audioStatusFor(entry)"
              class="rpg-audio-status mr-2"
              :class="{ 'is-error': audioStatusFor(entry)?.status === 'error' }"
            >
              {{ audioStatusLabel(entry) }}
            </span>
            <span class="rpg-text-main text-sm leading-relaxed">{{ entry.text }}</span>
          </div>
        </div>

        <!-- Action compagnon IA (type player mais speaker_id dans aiCharIds) → arcane ◈ -->
        <div
          v-else-if="entry.type === 'player' && entry.speaker_id && aiCharIds.has(entry.speaker_id)"
          class="rpg-dialogue-entry flex gap-3 rounded-lg border-l-2 py-2.5 pl-4 pr-3 is-companion"
          style="border-color: rgba(192,144,255,0.45); background: rgba(192,144,255,0.04);"
        >
          <div class="min-w-0 flex-1">
            <span
              v-if="entry.speaker"
              class="mr-2 text-sm font-display font-semibold rpg-text-arcane"
            >◈ {{ entry.speaker }} </span>
            <span class="rpg-text-main text-sm leading-relaxed">{{ entry.text }}</span>
          </div>
        </div>

        <!-- Action joueur humain — gold (joueur humain) ◉ -->
        <div
          v-else-if="entry.type === 'player'"
          class="rpg-player-entry flex gap-3 rounded-lg border-l-2 py-2 pl-4 pr-3"
          style="border-color: rgba(240,199,100,0.35); background: rgba(240,199,100,0.03);"
        >
          <div class="min-w-0 flex-1">
            <span
              v-if="entry.speaker"
              class="mr-2 text-[10px] font-display font-bold tracking-wide uppercase"
              style="color: var(--color-gold);"
            >◉ {{ entry.speaker }} </span>
            <span
              class="text-[12.5px] font-serif italic"
              style="color: var(--color-text-muted);"
            >« {{ entry.text }} »</span>
          </div>
        </div>

        <!-- Jet de dé -->
        <div v-else-if="entry.type === 'roll' && entry.roll">
          <DiceRollResult :roll="entry.roll" />
        </div>

        <!-- Action de combat -->
        <div
          v-else-if="entry.type === 'combat_action' && entry.combatAction"
          class="rpg-combat-log-entry rounded-lg border px-4 py-3 text-sm space-y-2"
        >
          <div class="rpg-text-blood flex items-center gap-2 font-semibold">
            <span>⚔</span>
            <span class="font-display">{{ entry.combatAction.attacker_name }}</span>
            <span class="rpg-text-muted text-xs font-normal">attaque</span>
            <span class="font-display">{{ entry.combatAction.target_name }}</span>
            <span
              v-if="entry.combatAction.critical"
              class="rpg-chip rpg-tone-gold ml-auto"
            >Critique !</span>
          </div>
          <div class="rpg-text-muted flex flex-wrap gap-3 text-xs">
            <span>d20 : <span class="rpg-text-main font-mono font-bold">{{ entry.combatAction.d20 }}</span></span>
            <span>Total : <span class="rpg-text-main font-mono font-bold">{{ entry.combatAction.attack_roll }}</span> vs CA {{ entry.combatAction.target_ac }}</span>
            <span v-if="entry.combatAction.hit" class="rpg-text-green font-semibold">Touché</span>
            <span v-else class="rpg-text-dim">Raté</span>
            <span v-if="entry.combatAction.hit && entry.combatAction.damage !== null" class="rpg-text-blood font-semibold">{{ entry.combatAction.damage }} dégâts</span>
          </div>
        </div>

        <!-- Système — notification inline ⚙ -->
        <div
          v-else-if="entry.type === 'system'"
          class="flex items-center gap-1.5 py-1"
          style="color: var(--color-text-muted);"
        >
          <span style="font-size: 10px;">⚙</span>
          <span class="font-mono text-[10px] tracking-wide">{{ entry.text }}</span>
        </div>

      </template>

      <!-- GM pense -->
      <div
        v-if="hasThinkingEntry"
        class="rpg-thinking-entry flex items-center gap-3 rounded-lg border-l-2 py-3 pl-4"
      >
        <span class="rpg-text-gold font-serif italic text-sm opacity-70">
          {{ thinkingLabel }}
        </span>
        <span class="flex gap-1">
          <span v-for="delay in ['0ms', '150ms', '300ms']" :key="delay" class="rpg-thinking-dot inline-block h-1.5 w-1.5 rounded-full animate-bounce" :style="{ animationDelay: delay }" />
        </span>
      </div>
    </div>
  </div><!-- /v-else full variant -->
</template>

<style scoped>
/* ── Drawer variant styles ──────────────────────────────────────────────── */
.recit-drawer-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 18px;
  border-bottom: 1px solid var(--color-border);
  flex-shrink: 0;
}

.recit-drawer-title {
  font-family: var(--font-display);
  font-size: 13px;
  font-weight: 700;
  color: var(--color-parchment);
  margin: 0;
  letter-spacing: 2px;
  text-transform: uppercase;
}

.recit-round-badge {
  font-size: 9px;
  color: var(--color-text-muted);
  font-family: var(--font-mono);
  letter-spacing: 1px;
}

.recit-collapse-btn {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  background: transparent;
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: color 120ms ease, border-color 120ms ease;
}

.recit-collapse-btn:hover {
  color: var(--color-parchment);
  border-color: var(--color-border-strong);
}

.recit-drawer-log {
  flex: 1;
  overflow-y: auto;
  padding: 8px 18px 16px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  scrollbar-width: thin;
  scrollbar-color: var(--color-border-strong) transparent;
}

.recit-empty {
  color: var(--color-text-dim);
  font-family: var(--font-serif);
  font-size: 12px;
  font-style: italic;
  text-align: center;
  margin-top: 16px;
}

/* Indicateur "réfléchit" */
.recit-thinking {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0 4px;
}

.recit-thinking-label {
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 11px;
  color: var(--color-gold);
  opacity: 0.7;
}

.recit-thinking-dots {
  display: flex;
  gap: 4px;
}

.recit-thinking-dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: rgba(240, 199, 100, 0.6);
  animation: bounce 1s infinite;
}

.rpg-audio-status {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  border: 1px solid color-mix(in srgb, var(--color-gold) 35%, transparent);
  border-radius: var(--radius-sm);
  color: var(--color-gold);
  font-family: var(--font-mono);
  font-size: 9px;
  letter-spacing: 0.08em;
  line-height: 1;
  padding: 4px 6px;
  text-transform: uppercase;
}

.rpg-audio-status::before {
  content: '';
  width: 5px;
  height: 5px;
  border-radius: 999px;
  background: currentColor;
  animation: rpg-audio-pulse 900ms ease-in-out infinite;
}

.rpg-audio-status.is-error {
  border-color: color-mix(in srgb, var(--color-blood) 45%, transparent);
  color: var(--color-blood);
}

.rpg-audio-status.is-error::before {
  animation: none;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50%       { transform: translateY(-4px); }
}

@keyframes rpg-audio-pulse {
  0%, 100% { opacity: 0.35; transform: scale(0.8); }
  50% { opacity: 1; transform: scale(1); }
}
</style>
