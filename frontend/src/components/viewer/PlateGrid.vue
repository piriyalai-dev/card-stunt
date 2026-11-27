<script setup lang="ts">
/**
 * 🔳 เพลทของที่นั่งหนึ่งช่อง — grid ของ "ช่องย่อย" (default 5×5)
 *
 * ใช้ CSS grid ไม่ใช่ canvas เพราะเพลทเล็ก (≤16×16) — canvas มีไว้สำหรับกริดเต็มใน Studio
 */
import { computed } from 'vue'
import type { Plate, PublicColor } from '@/types/public'

const props = withDefaults(
  defineProps<{
    plate: Plate
    colors: Map<number, PublicColor>
    showCodes?: boolean
    gap?: number
  }>(),
  { showCodes: true, gap: 3 },
)

const cols = computed(() => props.plate?.[0]?.length ?? 0)
const empty = computed(() => !props.plate || cols.value === 0)

function colorOf(id: number | null): PublicColor | null {
  return id === null ? null : props.colors.get(id) ?? null
}

function cellStyle(id: number | null) {
  const color = colorOf(id)
  return {
    backgroundColor: color?.hex ?? '#E5E7EB',
    color: color?.text_color ?? '#94A3B8',
  }
}

function codeOf(id: number | null): string {
  return colorOf(id)?.code ?? ''
}
</script>

<template>
  <div
    v-if="empty"
    class="grid aspect-[4/3] w-full place-items-center rounded-control border border-dashed border-line text-caption text-ink-3"
  >
    ไม่มีข้อมูลด้านนี้
  </div>
  <div
    v-else
    class="grid w-full"
    :style="{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gap: `${gap}px` }"
  >
    <template v-for="(row, r) in plate" :key="r">
      <div
        v-for="(cell, c) in row"
        :key="c"
        class="grid aspect-square min-w-0 place-items-center rounded-[3px] font-bold leading-none"
        :class="showCodes ? 'text-[9px] sm:text-[10px]' : ''"
        :style="cellStyle(cell)"
        :title="colorOf(cell) ? `${colorOf(cell)?.code} ${colorOf(cell)?.name_th}` : 'ว่าง'"
      >
        <span v-if="showCodes && cell !== null">{{ codeOf(cell) }}</span>
      </div>
    </template>
  </div>
</template>
