<script setup lang="ts">
// Pictos de lieux (cartes Région / Ville) — traits SVG 24×24 en currentColor,
// lisibles à 14-20 px. Un seul vocabulaire pour les deux échelles de carte.
import type { MapGlyph } from './mapLayout'

defineProps<{ glyph: MapGlyph; size?: number }>()
</script>

<template>
  <g
    class="map-glyph"
    fill="none"
    stroke="currentColor"
    stroke-width="1.8"
    stroke-linecap="round"
    stroke-linejoin="round"
    :transform="`translate(${-(size ?? 18) / 2} ${-(size ?? 18) / 2}) scale(${(size ?? 18) / 24})`"
  >
    <template v-if="glyph === 'village'">
      <path d="M3 12 8 7.5 13 12" /><path d="M4.5 11v7h7v-7" /><path d="M13 13.5 17 10l4 3.5" /><path d="M14.5 13v5H20v-5" />
    </template>
    <template v-else-if="glyph === 'city'">
      <path d="M4 20V9l3-2 3 2v11" /><path d="M10 20V5l3-2 3 2v15" /><path d="M16 20v-8l2.5-1.5L21 12v8" /><path d="M3 20h19" />
    </template>
    <template v-else-if="glyph === 'port'">
      <circle cx="12" cy="5" r="2" /><path d="M12 7v13" /><path d="M8 11h8" /><path d="M5 14a7 7 0 0 0 14 0" />
    </template>
    <template v-else-if="glyph === 'temple'">
      <path d="M3 9 12 4l9 5" /><path d="M4 9h16" /><path d="M6 9v9M10 9v9M14 9v9M18 9v9" /><path d="M3 20h18" />
    </template>
    <template v-else-if="glyph === 'tower'">
      <path d="M7 21V9h10v12" /><path d="M6 9V5h2v2h2V5h4v2h2V5h2v4" /><path d="M11 21v-4h2v4" /><path d="M5 21h14" />
    </template>
    <template v-else-if="glyph === 'landmark'">
      <path d="M9 21 10 6l2-3 2 3 1 15" /><path d="M7 21h10" /><path d="M11 10h2" />
    </template>
    <template v-else-if="glyph === 'forest'">
      <path d="M8 3 3.5 12H6l-2.5 5h9L10 12h2.5Z" /><path d="M8 17v4" /><path d="M16 7l-3.5 7h2l-2 4h7l-2-4h2Z" /><path d="M16 18v3" />
    </template>
    <template v-else-if="glyph === 'mountain'">
      <path d="M2 20 9 7l4 6 2-3 7 10Z" /><path d="M7.5 10 9 12l1.5-1.5" />
    </template>
    <template v-else-if="glyph === 'oasis'">
      <path d="M12 21v-9" /><path d="M12 12c-1-3-4-4-7-3" /><path d="M12 12c1-3 4-4 7-3" /><path d="M12 12c-2-1-3-4-2-6" /><path d="M4 21c3-2 13-2 16 0" />
    </template>
    <template v-else-if="glyph === 'cave'">
      <path d="M3 20c0-8 4-14 9-14s9 6 9 14" /><path d="M8.5 20c0-4 1.5-7 3.5-7s3.5 3 3.5 7" /><path d="M2 20h20" />
    </template>
    <template v-else-if="glyph === 'ruin'">
      <path d="M5 20V8h3v12" /><path d="M11 20v-7h3v7" /><path d="M17 20v-9l3-1v10" /><path d="M4 8h5M3 20h19" /><path d="M11 13l3-2" />
    </template>
    <template v-else-if="glyph === 'crossroads'">
      <path d="M12 21V3" /><path d="M12 6h7l2 2-2 2h-7" /><path d="M12 12H5l-2 2 2 2h7" />
    </template>
    <template v-else-if="glyph === 'mine'">
      <path d="M4 20 14 10" /><path d="M9 5c4-2 8-1 11 2-2-1-5-1-7 0" /><path d="M13 6l4 4" />
    </template>
    <template v-else-if="glyph === 'camp'">
      <path d="M3 20 12 5l9 15" /><path d="M12 5v15" /><path d="M9 20l3-5 3 5" />
    </template>
    <template v-else-if="glyph === 'tavern'">
      <path d="M6 7h9v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1Z" /><path d="M15 10h2a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2h-2" /><path d="M6 7c0-2 2-3 4.5-3S15 5 15 7" />
    </template>
    <template v-else-if="glyph === 'shop'">
      <path d="M4 10h16l-1.5 10h-13Z" /><path d="M8 10V8a4 4 0 0 1 8 0v2" /><path d="M10 15h4" />
    </template>
    <template v-else-if="glyph === 'palace'">
      <path d="M3 19 4 8l4.5 4L12 5l3.5 7L20 8l1 11Z" /><path d="M3 21h18" />
    </template>
    <template v-else-if="glyph === 'gate'">
      <path d="M4 21V7h16v14" /><path d="M9 21v-6a3 3 0 0 1 6 0v6" /><path d="M4 7V4h3v3M10.5 7V4h3v3M17 7V4h3v3" />
    </template>
    <template v-else-if="glyph === 'square'">
      <circle cx="12" cy="12" r="8" /><circle cx="12" cy="12" r="2.5" /><path d="M12 4v5.5M12 14.5V20M4 12h5.5M14.5 12H20" />
    </template>
    <template v-else-if="glyph === 'district'">
      <rect x="3.5" y="3.5" width="7" height="7" rx="1" /><rect x="13.5" y="3.5" width="7" height="7" rx="1" /><rect x="3.5" y="13.5" width="7" height="7" rx="1" /><rect x="13.5" y="13.5" width="7" height="7" rx="1" />
    </template>
    <template v-else-if="glyph === 'vault'">
      <path d="M4 10h16v9H4Z" /><path d="M4 10a8 5 0 0 1 16 0" /><path d="M12 13v3" />
    </template>
    <template v-else-if="glyph === 'lair'">
      <path d="M6 10a6 6 0 1 1 12 0v4l-2 2v3h-8v-3l-2-2Z" /><circle cx="9.5" cy="11" r="1.2" /><circle cx="14.5" cy="11" r="1.2" /><path d="M11 19v-2M13 19v-2" />
    </template>
    <template v-else-if="glyph === 'trap'">
      <path d="M3 18h18" /><path d="M5 18l2-6 2 6 2-6 2 6 2-6 2 6 2-6" />
    </template>
    <template v-else-if="glyph === 'passage'">
      <path d="M3 8h18M3 16h18" /><path d="M14 12h5m-2-2 2 2-2 2" />
    </template>
    <template v-else-if="glyph === 'door'">
      <path d="M6 21V5a1 1 0 0 1 1-1h10a1 1 0 0 1 1 1v16" /><circle cx="14.5" cy="13" r="0.8" /><path d="M4 21h16" />
    </template>
    <template v-else>
      <path d="M4 20V11l8-6 8 6v9" /><path d="M10 20v-5h4v5" />
    </template>
  </g>
</template>
