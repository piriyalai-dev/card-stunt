<script setup lang="ts">
import { useAuthStore } from '@/stores/auth'
import { roleLabel } from '@/constants/roles'

const authStore = useAuthStore()
</script>

<template>
  <div>
    <h2 class="font-display text-title-l font-bold mb-1">แดชบอร์ด</h2>
    <p class="text-body text-ink-2 mb-6">
      สวัสดี <b>{{ authStore.displayName }}</b> ({{ roleLabel(authStore.role) }})
    </p>

    <div class="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <div class="bg-surface rounded-card border border-line p-4">
        <div class="text-title-l font-display font-extrabold">0</div>
        <div class="text-caption text-ink-2 mt-1">ฉากทั้งหมด</div>
      </div>
      <div class="bg-surface rounded-card border border-line p-4">
        <div class="text-title-l font-display font-extrabold">0</div>
        <div class="text-caption text-ink-2 mt-1">สีในชุด</div>
      </div>
      <div class="bg-surface rounded-card border border-line p-4">
        <div class="text-title-l font-display font-extrabold">297</div>
        <div class="text-caption text-ink-2 mt-1">ที่นั่ง (33×9)</div>
      </div>
      <div class="bg-surface rounded-card border border-line p-4">
        <div class="text-title-l font-display font-extrabold">—</div>
        <div class="text-caption text-ink-2 mt-1">published</div>
      </div>
    </div>

    <div class="bg-surface rounded-card border border-line p-6">
      <div class="flex items-center justify-between mb-2">
        <b>กีฬาสี 69</b>
        <span class="inline-flex items-center gap-1.5 text-caption font-bold text-ok">
          <span class="w-2 h-2 rounded-full bg-ok"></span>active
        </span>
      </div>
      <p class="text-caption text-ink-2">
        Phase 2 scaffold — ข้อมูลจริงและหน้าเครื่องมือ (Stand Configurator / Palette / Pixel Studio)
        จะมาใน Phase 3–4
      </p>
    </div>
  </div>
</template>
