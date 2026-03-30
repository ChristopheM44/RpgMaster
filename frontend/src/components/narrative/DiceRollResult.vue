<script setup lang="ts">
import type { RollResultPayload } from '../../types'

defineProps<{ roll: RollResultPayload }>()
</script>

<template>
  <div class="flex flex-wrap items-center gap-2 rounded border border-gold/30 bg-ink/60 px-3 py-2 text-sm">
    <!-- Label + character -->
    <span v-if="roll.character_name" class="font-semibold text-gold">{{ roll.character_name }}</span>
    <span v-if="roll.label" class="text-parchment/70">{{ roll.label }}</span>

    <!-- Dice notation -->
    <span class="font-mono text-arcane">{{ roll.dice_notation }}</span>

    <!-- Individual rolls -->
    <span class="text-parchment/50">[</span>
    <span
      v-for="(r, i) in roll.rolls"
      :key="i"
      class="inline-flex h-6 w-6 items-center justify-center rounded bg-ink text-center font-mono font-bold"
      :class="r === 20 ? 'text-gold border border-gold' : r === 1 ? 'text-blood border border-blood' : 'text-parchment'"
    >{{ r }}</span>
    <span class="text-parchment/50">]</span>

    <!-- Modifier -->
    <span v-if="roll.modifier !== 0" class="text-parchment/70">
      {{ roll.modifier > 0 ? '+' : '' }}{{ roll.modifier }}
    </span>

    <!-- Total -->
    <span class="ml-auto font-bold text-lg" :class="roll.success === true ? 'text-gold' : roll.success === false ? 'text-blood' : 'text-parchment'">
      = {{ roll.total }}
      <span v-if="roll.success === true" class="text-xs font-normal text-gold/80"> Succès</span>
      <span v-else-if="roll.success === false" class="text-xs font-normal text-blood/80"> Échec</span>
    </span>
  </div>
</template>
