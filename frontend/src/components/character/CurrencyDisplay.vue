<script setup lang="ts">
import type { Character } from '../../types'

defineProps<{ character: Character }>()
</script>

<template>
  <div class="grid grid-cols-3 gap-1.5">
    <div class="rpg-mini-panel rounded-md border px-2 py-1.5 text-center">
      <div class="rpg-text-gold font-mono text-sm font-bold">{{ character.gp }}</div>
      <div class="rpg-text-dim text-[8px] font-bold uppercase tracking-[0.16em]">PO</div>
    </div>
    <div class="rpg-mini-panel rounded-md border px-2 py-1.5 text-center">
      <div class="rpg-text-muted font-mono text-sm font-bold">{{ character.sp }}</div>
      <div class="rpg-text-dim text-[8px] font-bold uppercase tracking-[0.16em]">PA</div>
    </div>
    <div class="rpg-mini-panel rounded-md border px-2 py-1.5 text-center">
      <div class="rpg-text-muted font-mono text-sm font-bold">{{ character.cp }}</div>
      <div class="rpg-text-dim text-[8px] font-bold uppercase tracking-[0.16em]">PC</div>
    </div>
  </div>
</template>
