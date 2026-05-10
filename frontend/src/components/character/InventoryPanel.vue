<script setup lang="ts">
import { computed } from 'vue'
import type { Character, EquipmentItem } from '../../types'

const props = defineProps<{ character: Character }>()

const items = computed(() => props.character.equipment ?? [])
const equipped = computed(() => items.value.filter((item) => item.equipped))

function itemName(item: EquipmentItem): string {
  return item.name_fr || item.name || item.id
}

function itemKind(item: EquipmentItem): string {
  return item.item_type || item.category || 'gear'
}
</script>

<template>
  <div class="space-y-3">
    <div v-if="equipped.length" class="space-y-1.5">
      <div class="rpg-eyebrow">Équipé</div>
      <div
        v-for="item in equipped"
        :key="item.id"
        class="rpg-mini-panel rounded-md border px-3 py-2"
      >
        <div class="rpg-text-main truncate text-xs font-bold">{{ itemName(item) }}</div>
        <div class="rpg-text-dim text-[10px]">{{ item.slot || item.occupied_slots?.join(', ') || itemKind(item) }}</div>
      </div>
    </div>

    <div class="space-y-1.5">
      <div class="rpg-eyebrow">Inventaire</div>
      <div
        v-for="item in items"
        :key="item.id"
        class="rpg-mini-panel flex items-center justify-between gap-3 rounded-md border px-3 py-2"
      >
        <div class="min-w-0">
          <div class="rpg-text-main truncate text-xs font-bold">{{ itemName(item) }}</div>
          <div class="rpg-text-dim text-[10px]">{{ itemKind(item) }} · x{{ item.quantity ?? 1 }}</div>
        </div>
        <span v-if="item.attuned" class="rpg-text-gold text-[10px] font-bold">harm.</span>
      </div>
      <p v-if="!items.length" class="rpg-text-dim text-xs italic">Inventaire vide.</p>
    </div>
  </div>
</template>
