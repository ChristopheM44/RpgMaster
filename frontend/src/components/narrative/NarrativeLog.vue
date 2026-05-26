<script setup lang="ts">
import { computed, ref, watch, nextTick } from 'vue'
import { useGameStore } from '../../stores/game'
import { useSessionStore } from '../../stores/session'
import DiceRollResult from './DiceRollResult.vue'

withDefaults(defineProps<{
  /**
   * 'full'   — the standalone exploration layout (default, unchanged)
   * 'drawer' — compact V2 combat drawer: slim header + compact entries
   */
  variant?: 'full' | 'drawer'
}>(), { variant: 'full' })

const gameStore = useGameStore()
const sessionStore = useSessionStore()
const logEl = ref<HTMLElement | null>(null)
const hasThinkingEntry = computed(() =>
  gameStore.isProcessing || gameStore.isGmThinking || gameStore.isPlayerAiThinking,
)
const thinkingLabel = computed(() =>
  gameStore.isPlayerAiThinking && !gameStore.isGmThinking
    ? 'Le joueur IA réfléchit'
    : 'Le Maître du Jeu réfléchit',
)

watch(
  () => gameStore.narrativeLog.length + (hasThinkingEntry.value ? 1 : 0),
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

    <!-- Compact log -->
    <div ref="logEl" class="recit-drawer-log">
      <p v-if="gameStore.narrativeLog.length === 0" class="recit-empty">
        En attente…
      </p>

      <template v-for="entry in gameStore.narrativeLog" :key="entry.id">
        <div v-if="entry.type === 'narration'" class="recit-entry recit-narration">
          <div class="recit-speaker">✦ {{ entry.speaker ?? 'MJ' }}</div>
          <p class="recit-text">{{ entry.text }}</p>
        </div>

        <div v-else-if="entry.type === 'dialogue'" class="recit-entry recit-dialogue">
          <span class="recit-speaker" :style="{ color: entry.speaker_kind === 'companion' ? 'var(--color-arcane)' : 'var(--color-gold)' }">
            {{ entry.speaker }}
          </span>
          <span class="recit-text">{{ entry.text }}</span>
        </div>

        <div v-else-if="entry.type === 'player'" class="recit-entry recit-player">
          <span class="recit-speaker" style="color: var(--color-ember)">{{ entry.speaker }}</span>
          <span class="recit-text">{{ entry.text }}</span>
        </div>

        <div v-else-if="entry.type === 'roll' && entry.roll" class="recit-entry">
          <DiceRollResult :roll="entry.roll" />
        </div>

        <div v-else-if="entry.type === 'combat_action' && entry.combatAction" class="recit-entry recit-combat">
          ⚔ <strong>{{ entry.combatAction.attacker_name }}</strong>
          → {{ entry.combatAction.target_name }}
          <span v-if="entry.combatAction.hit" style="color: var(--color-blood)"> {{ entry.combatAction.damage }}dmg</span>
          <span v-else style="color: var(--color-text-dim)"> raté</span>
        </div>

        <div v-else-if="entry.type === 'system'" class="recit-entry recit-system">
          ── {{ entry.text }} ──
        </div>
      </template>

      <div v-if="hasThinkingEntry" class="recit-entry recit-thinking">
        <span>{{ thinkingLabel }}</span>
        <span class="flex gap-1 ml-2">
          <span v-for="d in ['0ms','150ms','300ms']" :key="d"
            class="inline-block h-1.5 w-1.5 rounded-full bg-gold/60 animate-bounce"
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
          <div class="rpg-eyebrow">
            ✦ {{ entry.speaker ?? 'Maître du Jeu' }}
          </div>
          <p
            class="rpg-text-secondary font-serif leading-[1.8] text-[17px] text-pretty"
          >{{ entry.text }}</p>
        </div>

        <!-- Dialogue compagnon / PNJ -->
        <div
          v-else-if="entry.type === 'dialogue'"
          class="rpg-dialogue-entry flex gap-3 rounded-lg border-l-2 py-2.5 pl-4 pr-3"
          :class="{ 'is-companion': entry.speaker_kind === 'companion' }"
        >
          <div class="min-w-0 flex-1">
            <span
              v-if="entry.speaker"
              class="mr-2 text-sm font-display font-semibold"
              :class="entry.speaker_kind === 'companion' ? 'rpg-text-arcane' : 'rpg-text-gold'"
            >{{ entry.speaker }} </span>
            <span class="rpg-text-main text-sm leading-relaxed">{{ entry.text }}</span>
          </div>
        </div>

        <!-- Action joueur -->
        <div
          v-else-if="entry.type === 'player'"
          class="rpg-player-entry flex gap-3 rounded-lg border-l-2 py-2.5 pl-4 pr-3"
        >
          <div class="min-w-0 flex-1">
            <span
              v-if="entry.speaker"
              class="rpg-text-arcane mr-2 text-sm font-display font-semibold"
            >{{ entry.speaker }} </span>
            <span class="rpg-text-main text-sm">{{ entry.text }}</span>
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

        <!-- Système -->
        <div v-else-if="entry.type === 'system'" class="rpg-text-dim py-1 text-center text-xs">
          ──── {{ entry.text }} ────
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

.recit-entry {
  font-size: 12px;
  line-height: 1.55;
}

.recit-narration {
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.recit-speaker {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 1px;
  text-transform: uppercase;
  color: var(--color-text-muted);
}

.recit-text {
  font-family: var(--font-serif);
  color: var(--color-parchment-dark);
  font-size: 12px;
  line-height: 1.55;
}

.recit-dialogue,
.recit-player {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 5px 10px;
  border-left: 2px solid var(--color-border-strong);
  background: rgba(0, 0, 0, 0.2);
  border-radius: 0 4px 4px 0;
}

.recit-dialogue .recit-speaker { font-family: var(--font-display); }

.recit-combat {
  color: var(--color-text-muted);
  font-size: 11px;
  font-family: var(--font-mono);
  padding: 4px 8px;
  background: rgba(232, 69, 69, 0.06);
  border-radius: 4px;
  border: 1px solid rgba(232, 69, 69, 0.15);
}

.recit-system {
  color: var(--color-text-dim);
  font-size: 10px;
  text-align: center;
}

.recit-thinking {
  display: flex;
  align-items: center;
  color: var(--color-gold);
  font-family: var(--font-serif);
  font-style: italic;
  font-size: 11px;
  opacity: 0.7;
}
</style>
