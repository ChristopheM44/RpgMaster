<script setup lang="ts">
import type { Character, EquipmentItem } from '../../types'

defineProps<{
  open: boolean
  from: Character | null
  characters: Character[]
}>()

const emit = defineEmits<{
  give: [payload: { itemId: string; targetId: string }]
  cancel: []
}>()

function itemName(item: EquipmentItem): string {
  return item.name_fr || item.name || item.id
}
</script>

<template>
  <div v-if="open && from" class="fixed inset-0 z-[70] flex items-center justify-center bg-black/60 p-4">
    <div class="rpg-save-popover w-full max-w-md rounded-xl border p-5 shadow-2xl">
      <div class="rpg-eyebrow mb-3">Donner un objet</div>
      <div class="space-y-2">
        <div
          v-for="item in from?.equipment ?? []"
          :key="item.id"
          class="rpg-mini-panel rounded-md border p-3"
        >
          <div class="rpg-text-main text-sm font-bold">{{ itemName(item) }}</div>
          <div class="mt-2 flex flex-wrap gap-2">
            <button
              v-for="target in characters.filter(c => c.id !== from?.id)"
              :key="target.id"
              class="rpg-btn-secondary !py-1 !text-[10px]"
              @click="emit('give', { itemId: item.id, targetId: target.id })"
            >
              {{ target.name }}
            </button>
          </div>
        </div>
      </div>
      <button class="rpg-btn-secondary mt-4 w-full justify-center" @click="emit('cancel')">Fermer</button>
    </div>
  </div>
</template>
