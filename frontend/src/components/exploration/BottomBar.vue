<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useCharacterStore } from '../../stores/character'
import { useGameStore } from '../../stores/game'
import type { SceneOption } from '../../types'

const emit = defineEmits<{
  action: [actionType: string, content?: string, targetId?: string, extra?: Record<string, unknown>]
}>()

const charStore = useCharacterStore()
const gameStore = useGameStore()

const input = ref('')
const menuOpen = ref(false)
const targetId = ref<string | null>(null)
const menuEl = ref<HTMLElement | null>(null)

const aiCompanions = computed(() =>
  charStore.sessionCharacters.filter((c) => c.is_ai),
)

const targetCompanion = computed(() =>
  targetId.value ? aiCompanions.value.find((c) => c.id === targetId.value) ?? null : null,
)

const placeholder = computed(() =>
  targetCompanion.value
    ? `Parler à ${targetCompanion.value.name}…`
    : 'Décrivez votre action, parlez, ou posez une question au MJ…',
)

const me = computed(() => charStore.myCharacter)
const initial = computed(() => (me.value?.name ?? 'V').charAt(0).toUpperCase())

const canSend = computed(() => gameStore.connected && !gameStore.isProcessing)
const sceneOptions = computed(() => gameStore.sceneOptions.slice(0, 4))

function submit() {
  const text = input.value.trim()
  if (!text || !canSend.value) return
  const extra = targetCompanion.value
    ? { addressed_to: targetCompanion.value.id, audience: 'companion' }
    : undefined
  emit('action', 'free_text', text, undefined, extra)
  input.value = ''
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    submit()
  }
}

function chooseTarget(id: string | null) {
  targetId.value = id
  menuOpen.value = false
}

function chooseSceneOption(option: SceneOption) {
  if (!canSend.value) return
  emit('action', option.action_type ?? 'free_text', option.prompt || option.label, undefined, {
    scene_option_id: option.id,
    scene_id: option.scene_id,
    linked_poi_id: option.linked_poi_id,
  })
}

function avatarStyle(color: string | undefined) {
  const c = color ?? '#c090ff'
  return { background: `radial-gradient(circle at 30% 30%, ${c}, ${c}aa)` }
}

function onClickOutside(e: MouseEvent) {
  if (!menuOpen.value) return
  if (menuEl.value && !menuEl.value.contains(e.target as Node)) {
    menuOpen.value = false
  }
}

onMounted(() => {
  document.addEventListener('click', onClickOutside)
})

onUnmounted(() => {
  document.removeEventListener('click', onClickOutside)
})
</script>

<template>
  <div class="bottom-shell">
    <div v-if="sceneOptions.length" class="bb-options" aria-label="Pistes de scène">
      <button
        v-for="option in sceneOptions"
        :key="option.id"
        type="button"
        class="bb-option"
        :disabled="!canSend"
        @click="chooseSceneOption(option)"
      >
        <span class="bb-option-mark">✦</span>
        <span>{{ option.label }}</span>
      </button>
    </div>

    <div class="bottom-bar">
      <!-- "Vous incarnez" block -->
      <div class="bb-identity">
        <div class="bb-avatar">{{ initial }}</div>
        <div class="bb-identity-text">
          <div class="bb-identity-eyebrow">Vous incarnez</div>
          <div class="bb-identity-name">{{ me?.name ?? 'Thorvald' }}</div>
        </div>
      </div>

      <!-- @ dropdown -->
      <div ref="menuEl" class="bb-mention">
        <button
          type="button"
          class="bb-mention-btn"
          :class="{ 'is-active': targetCompanion }"
          @click.stop="menuOpen = !menuOpen"
        >
          <span class="bb-mention-at">@</span>
          <span class="bb-mention-label">{{ targetCompanion?.name ?? 'Parler à…' }}</span>
          <span class="bb-mention-caret">▼</span>
        </button>
        <div v-if="menuOpen" class="bb-mention-menu">
          <button
            type="button"
            class="bb-mention-item"
            :class="{ 'is-active': !targetCompanion }"
            @click="chooseTarget(null)"
          >
            <span style="font-size: 11px">✦</span> Au MJ / le groupe
          </button>
          <div class="bb-mention-divider" />
          <button
            v-for="c in aiCompanions"
            :key="c.id"
            type="button"
            class="bb-mention-item"
            :class="{ 'is-active': targetCompanion?.id === c.id }"
            @click="chooseTarget(c.id)"
          >
            <span
              class="bb-mention-avatar"
              :style="avatarStyle('#c090ff')"
            >{{ c.name.charAt(0).toUpperCase() }}</span>
            {{ c.name }}
            <span style="flex: 1" />
            <span class="bb-mention-badge">IA</span>
          </button>
          <button
            v-if="!aiCompanions.length"
            type="button"
            class="bb-mention-item bb-mention-empty"
            disabled
          >Aucun compagnon</button>
        </div>
      </div>

      <!-- Input -->
      <input
        v-model="input"
        class="rpg-input bb-input"
        :placeholder="placeholder"
        :disabled="!canSend"
        @keydown="onKeydown"
      />

      <!-- Send -->
      <button
        class="rpg-btn-primary bb-send"
        :disabled="!input.trim() || !canSend"
        @click="submit"
      >
        Envoyer <span class="bb-send-key">↵</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.bottom-shell {
  flex-shrink: 0;
  border-top: 1px solid var(--color-border);
  background: var(--color-bg-elev);
  position: relative;
  z-index: 10;
}

.bb-options {
  display: flex;
  gap: 8px;
  overflow-x: auto;
  padding: 10px 20px 0;
}

.bb-option {
  min-height: 30px;
  max-width: 260px;
  flex: 0 0 auto;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 6px;
  border: 1px solid var(--color-border);
  background: color-mix(in srgb, var(--color-gold) 10%, transparent);
  color: var(--color-parchment);
  font-family: var(--font-display);
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 0.6px;
  text-transform: uppercase;
  white-space: nowrap;
  cursor: pointer;
  transition: background 120ms, border-color 120ms, color 120ms;
}

.bb-option:hover:not(:disabled) {
  border-color: var(--color-border-strong);
  background: color-mix(in srgb, var(--color-gold) 16%, transparent);
  color: var(--color-gold);
}

.bb-option:disabled {
  opacity: 0.45;
  cursor: default;
}

.bb-option-mark {
  color: var(--color-ember);
}

.bottom-bar {
  padding: 12px 20px;
  display: flex;
  align-items: center;
  gap: 10px;
}

/* Identity block */
.bb-identity {
  display: flex;
  align-items: center;
  gap: 7px;
  flex-shrink: 0;
}

.bb-avatar {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  background: linear-gradient(135deg, var(--color-ember), var(--color-gold));
  color: var(--color-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
}

.bb-identity-text { line-height: 1.2; }

.bb-identity-eyebrow {
  font-size: 8px;
  color: var(--color-text-dim);
  letter-spacing: 1px;
  text-transform: uppercase;
  font-weight: 700;
}

.bb-identity-name {
  font-family: var(--font-display);
  font-size: 12px;
  font-weight: 700;
  color: var(--color-gold);
}

/* Mention */
.bb-mention {
  position: relative;
  flex-shrink: 0;
}

.bb-mention-btn {
  display: flex;
  align-items: center;
  gap: 5px;
  padding: 8px 10px;
  border-radius: 6px;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-border);
  color: var(--color-text-muted);
  font-size: 11px;
  font-weight: 600;
  font-family: var(--font-display);
  letter-spacing: 0.6px;
  cursor: pointer;
  transition: background 120ms, color 120ms, border-color 120ms;
}

.bb-mention-btn.is-active {
  background: rgba(192, 144, 255, 0.10);
  border-color: rgba(192, 144, 255, 0.4);
  color: var(--color-arcane);
}

.bb-mention-at {
  font-family: var(--font-mono);
  font-weight: 700;
}

.bb-mention-caret {
  font-size: 8px;
  margin-left: 2px;
}

.bb-mention-menu {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  min-width: 200px;
  padding: 4px;
  background: var(--color-bg-elev);
  border: 1px solid var(--color-border-strong);
  border-radius: 6px;
  box-shadow: 0 12px 36px rgba(0, 0, 0, 0.6);
  z-index: 20;
  display: flex;
  flex-direction: column;
}

.bb-mention-item {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 6px 10px;
  background: transparent;
  border: none;
  border-radius: 4px;
  color: var(--color-parchment);
  font-family: var(--font-display);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.4px;
  cursor: pointer;
  text-align: left;
  white-space: nowrap;
}

.bb-mention-item:hover {
  background: rgba(247, 236, 208, 0.06);
}

.bb-mention-item.is-active {
  background: rgba(240, 199, 100, 0.15);
  color: var(--color-gold);
}

.bb-mention-avatar {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-family: var(--font-display);
  font-size: 8px;
  font-weight: 700;
  color: var(--color-bg);
}

.bb-mention-badge {
  font-size: 8px;
  color: var(--color-arcane);
  font-weight: 700;
}

.bb-mention-divider {
  height: 1px;
  background: var(--color-border);
  margin: 2px 0;
}

.bb-mention-empty {
  color: var(--color-text-dim);
  cursor: default;
}

/* Input */
.bb-input {
  flex: 1;
  padding: 10px 14px;
  font-family: var(--font-serif);
  font-size: 14px;
}

/* Send */
.bb-send {
  flex-shrink: 0;
  padding: 10px 18px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.bb-send-key {
  font-family: var(--font-mono);
  font-size: 11px;
}
</style>
