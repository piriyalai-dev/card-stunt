<script setup lang="ts">
/**
 * แบนเนอร์ติดตั้ง PWA + แบนเนอร์ "มีเวอร์ชันใหม่"
 *
 * วางไว้ใน `App.vue` (ครอบทั้ง admin และ viewer) — ผู้ชมในสนามเป็นผู้ใช้มือถือหลัก
 *
 * ⚠️ **ไม่เดาจาก user agent** — แสดงเฉพาะเมื่อเบราว์เซอร์ยิง `beforeinstallprompt`
 *    จริง (Chrome/Edge/Android) ส่วน iOS Safari ไม่ยิงเลย ⇒ ผู้ใช้ iOS เห็นเฉพาะคำแนะนำ
 *    "แชร์ → เพิ่มไปที่หน้าจอ" ซึ่งเป็นทางเดียวที่ iOS มีให้
 *
 * ⚠️ **ชวนเฉพาะมือถือ/แท็บเล็ต** — เงื่อนไข `(pointer: coarse)` อยู่ใน `pwa.ts` แล้ว
 *    ⇒ คอมโพเนนต์นี้ไม่ต้องรู้เรื่องนั้น · เปิดในคอมจะเงียบสนิท
 *
 * ⚠️ **ไม่ auto-reload ตอนมีเวอร์ชันใหม่** — ให้ผู้ใช้กดเอง กันตัดกลางทาง
 */
import { ref } from 'vue'
import {
  applyUpdate,
  dismissInstall,
  dismissIosHint,
  promptInstall,
  showInstallBanner,
  showIosHint,
  showUpdateBanner,
} from '@/pwa'

const isWorking = ref(false)

async function onInstall() {
  if (isWorking.value) return
  isWorking.value = true
  try {
    // 'accepted' → browser ยิง `appinstalled` ⇒ แบนเนอร์หายเอง · 'dismissed' = ผู้ใช้ปิดเอง
    await promptInstall()
  } finally {
    isWorking.value = false
  }
}
</script>

<template>
  <!-- มีเวอร์ชันใหม่ → สำคัญกว่าชวนติดตั้ง ⇒ แสดงแทนกัน ไม่ซ้อนกัน -->
  <Transition name="prompt">
    <div
      v-if="showUpdateBanner"
      class="banner-anchor pointer-events-none fixed inset-x-0 z-40 px-3"
    >
      <div
        class="pointer-events-auto mx-auto flex w-full max-w-[440px] items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3 shadow-lg shadow-stone-900/5"
      >
        <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-tint text-brand">
          <i class="bi bi-arrow-repeat text-lg"></i>
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-bold text-ink-1">มีเวอร์ชันใหม่</p>
          <p class="mt-0.5 text-[11px] font-medium text-ink-2">อัปเดตเมื่อพร้อม — ระบบจะโหลดหน้าใหม่ให้</p>
        </div>
        <button
          type="button"
          class="inline-flex min-h-11 shrink-0 items-center rounded-xl bg-brand px-3.5 py-2 text-xs font-bold text-white transition-colors hover:bg-brand-strong"
          @click="applyUpdate"
        >
          อัปเดต
        </button>
      </div>
    </div>
  </Transition>

  <Transition name="prompt">
    <div
      v-if="showInstallBanner && !showUpdateBanner"
      class="banner-anchor pointer-events-none fixed inset-x-0 z-40 px-3"
    >
      <div
        class="pointer-events-auto mx-auto flex w-full max-w-[440px] items-center gap-3 rounded-2xl border border-line bg-surface px-4 py-3 shadow-lg shadow-stone-900/5"
      >
        <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand text-white">
          <i class="bi bi-phone text-lg"></i>
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-bold text-ink-1">ติดตั้ง Pixel Stand</p>
          <p class="mt-0.5 text-[11px] font-medium text-ink-2">เพิ่มลงหน้าจอ เปิดได้เร็วเหมือนแอพ</p>
        </div>
        <button
          type="button"
          :disabled="isWorking"
          class="inline-flex min-h-11 shrink-0 items-center rounded-xl bg-brand px-3.5 py-2 text-xs font-bold text-white transition-colors hover:bg-brand-strong disabled:opacity-60"
          @click="onInstall"
        >
          <i v-if="isWorking" class="bi bi-arrow-repeat animate-spin"></i>
          <span v-else>ติดตั้ง</span>
        </button>
        <button
          type="button"
          aria-label="ปิด"
          class="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-canvas hover:text-ink-1"
          @click="dismissInstall"
        >
          <i class="bi bi-x-lg text-xs"></i>
        </button>
      </div>
    </div>
  </Transition>

  <!-- iOS Safari — ไม่มี `beforeinstallprompt` และไม่มี API ติดตั้ง ⇒ ทางเดียวคือสอน -->
  <Transition name="prompt">
    <div
      v-if="showIosHint && !showUpdateBanner"
      class="banner-anchor pointer-events-none fixed inset-x-0 z-40 px-3"
    >
      <div
        class="pointer-events-auto mx-auto flex w-full max-w-[440px] items-start gap-3 rounded-2xl border border-line bg-surface px-4 py-3 shadow-lg shadow-stone-900/5"
      >
        <span class="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand text-white">
          <i class="bi bi-phone text-lg"></i>
        </span>
        <div class="min-w-0 flex-1">
          <p class="text-sm font-bold text-ink-1">ติดตั้ง Pixel Stand</p>
          <p class="mt-0.5 text-[11px] font-medium text-ink-2">เพิ่มลงหน้าจอ เปิดได้เร็วเหมือนแอพ</p>
          <ol class="mt-1.5 space-y-0.5 text-[11px] font-medium text-ink-2">
            <li>1. แตะปุ่ม <i class="bi bi-box-arrow-up text-ink-1"></i> แชร์ ที่แถบล่างจอ</li>
            <li>2. เลือก “เพิ่มไปที่หน้าจอ”</li>
          </ol>
        </div>
        <button
          type="button"
          aria-label="ปิด"
          class="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg text-ink-3 transition-colors hover:bg-canvas hover:text-ink-1"
          @click="dismissIosHint"
        >
          <i class="bi bi-x-lg text-xs"></i>
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* มือถือ: ลอยเหนือขอบล่างโดยเผื่อ safe-area · จอใหญ่: ชิดขอบล่างได้ (ไม่มี tab bar) */
.banner-anchor {
  bottom: calc(env(safe-area-inset-bottom, 0px) + 1rem);
}
@media (min-width: 1024px) {
  .banner-anchor {
    bottom: 1.5rem;
  }
}

/* เด้งขึ้นจากขอบล่างแบบนุ่ม ๆ */
.prompt-enter-active,
.prompt-leave-active {
  transition:
    opacity 0.25s ease,
    transform 0.25s cubic-bezier(0.175, 0.885, 0.32, 1);
}
.prompt-enter-from,
.prompt-leave-to {
  opacity: 0;
  transform: translateY(0.75rem);
}

/* ♿ เคารพผู้ที่ปิดแอนิเมชัน */
@media (prefers-reduced-motion: reduce) {
  .prompt-enter-active,
  .prompt-leave-active {
    transition: none;
  }
  .prompt-enter-from,
  .prompt-leave-to {
    transform: none;
  }
  .animate-spin {
    animation: none;
  }
}
</style>
