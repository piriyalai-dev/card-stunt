<script setup lang="ts">
/**
 * 🔑 ใส่รหัสล็อกอิน (พิมพ์แจกนักเรียนรายที่นั่ง) — แทนการเลือกที่นั่งจากผัง/ค้นหาเลข ปชช.
 */
import { ref } from 'vue'
import type { PublicMeta } from '@/types/public'

defineProps<{
  meta: PublicMeta
  busy: boolean
  error: string
}>()

const emit = defineEmits<{ (e: 'claim', code: string): void }>()

const code = ref('')

function submit(): void {
  const value = code.value.trim()
  if (!value) return
  emit('claim', value)
}
</script>

<template>
  <div class="mx-auto w-full max-w-md px-5 py-10">
    <div class="rounded-card border border-line bg-surface p-5 text-center">
      <div class="mx-auto grid h-14 w-14 place-items-center rounded-2xl bg-brand-tint text-2xl text-brand">
        <i class="bi bi-key" aria-hidden="true" />
      </div>
      <h1 class="mt-3 font-display text-title-l font-bold text-ink-1">{{ meta.name }}</h1>
      <p class="mt-1 text-body text-ink-2">ใส่รหัสล็อกอินที่พิมพ์แจกไว้บนโพยของที่นั่งคุณ</p>

      <form class="mt-5" @submit.prevent="submit">
        <input
          v-model="code"
          type="text"
          inputmode="text"
          autocomplete="off"
          spellcheck="false"
          autocapitalize="characters"
          placeholder="รหัสล็อกอิน เช่น 7K2Q9X4M"
          class="h-14 w-full rounded-control border border-line bg-canvas px-4 text-center font-mono text-title-m font-bold uppercase tracking-wide"
          :disabled="busy"
        />
        <p v-if="error" class="mt-2 text-caption font-semibold text-danger">{{ error }}</p>
        <button
          type="submit"
          class="mt-4 h-12 w-full rounded-control bg-brand text-body font-bold text-white disabled:opacity-50"
          :disabled="busy || !code.trim()"
        >
          {{ busy ? 'กำลังตรวจสอบ…' : 'เข้าดูโพย' }}
        </button>
      </form>
    </div>
  </div>
</template>
