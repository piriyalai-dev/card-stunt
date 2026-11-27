<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()
const slug = route.params.slug as string
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-canvas px-4 text-center">
    <div class="max-w-sm">
      <div class="inline-grid place-items-center w-14 h-14 rounded-2xl bg-brand text-white font-display font-extrabold text-2xl mb-4">P</div>
      <h1 class="font-display text-title-l font-bold text-ink-1">โหมดนักเรียน</h1>
      <p class="text-body text-ink-2 mt-2">
        event <span class="font-mono">{{ slug }}</span> — เลือกที่นั่ง / ดูโพย / โฟกัสโหมด
        จะมาใน Phase 5
      </p>
    </div>
  </div>
</template>
