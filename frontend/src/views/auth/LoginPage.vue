<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { REDIRECT_QUERY, safeRedirect } from '@/router/redirect'
import AppButton from '@/components/ui/AppButton.vue'

const authStore = useAuthStore()
const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  loading.value = true
  try {
    await authStore.login(username.value, password.value)
    const redirect = safeRedirect(route.query[REDIRECT_QUERY])
    await router.push(redirect || { name: 'admin-home' })
  } catch (e) {
    error.value = (e as Error).message || 'เข้าสู่ระบบไม่สำเร็จ'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-canvas px-4">
    <div class="w-full max-w-sm">
      <div class="text-center mb-8">
        <div class="inline-grid place-items-center w-14 h-14 rounded-2xl bg-brand text-white font-display font-extrabold text-2xl mb-3">P</div>
        <h1 class="font-display text-title-l font-bold text-ink-1">Pixel Stand</h1>
        <p class="text-caption text-ink-2 mt-1">ระบบแปรอักษรกีฬาสี</p>
      </div>

      <form class="bg-surface rounded-card border border-line p-6" @submit.prevent="submit">
        <label class="block text-caption font-semibold text-ink-2 mb-1" for="username">ชื่อผู้ใช้</label>
        <input id="username" v-model="username" class="field mb-4" autocomplete="username" required />

        <label class="block text-caption font-semibold text-ink-2 mb-1" for="password">รหัสผ่าน</label>
        <input id="password" v-model="password" type="password" class="field mb-4" autocomplete="current-password" required />

        <p v-if="error" class="text-caption text-danger mb-3">{{ error }}</p>

        <AppButton type="submit" variant="primary" block :loading="loading">เข้าสู่ระบบ</AppButton>
      </form>
    </div>
  </div>
</template>
