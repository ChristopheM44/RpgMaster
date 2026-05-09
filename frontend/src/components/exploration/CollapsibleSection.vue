<script setup lang="ts">
import { ref, onMounted } from 'vue'

const props = defineProps<{
  id: string
  eyebrow: string
  count?: number
}>()

const collapsed = ref(false)

onMounted(() => {
  const stored = localStorage.getItem(`rpg.exploration.collapsed.${props.id}`)
  if (stored === '1') collapsed.value = true
})

function toggle() {
  collapsed.value = !collapsed.value
  localStorage.setItem(`rpg.exploration.collapsed.${props.id}`, collapsed.value ? '1' : '0')
}
</script>

<template>
  <div
    class="rpg-border border-t shrink-0"
  >
    <button
      class="flex w-full cursor-pointer items-center gap-2 px-5 py-3 text-left transition-colors hover:bg-white/[0.02]"
      @click="toggle"
    >
      <span
        class="rpg-text-dim transition-transform duration-200 text-[10px]"
        :style="{
          transform: collapsed ? 'rotate(0deg)' : 'rotate(90deg)',
        }"
      >▶</span>
      <span class="rpg-eyebrow flex-1">{{ eyebrow }}</span>
      <span
        v-if="count !== undefined && count > 0"
        class="rpg-text-muted font-mono text-[11px]"
      >[{{ count }}]</span>
    </button>

    <div v-show="!collapsed">
      <slot />
    </div>
  </div>
</template>
