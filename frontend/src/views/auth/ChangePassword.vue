<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import * as authService from '@/services/auth'
import AppButton from '@/components/ui/AppButton.vue'

const authStore = useAuthStore()
const router = useRouter()

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  if (newPassword.value !== confirmPassword.value) {
    error.value = 'รหัสผ่านใหม่ไม่ตรงกัน'
    return
  }
  loading.value = true
  try {
    await authService.changePassword(oldPassword.value, newPassword.value)
    // เปลี่ยนรหัส = revoke ทุก session (token_version bump) → ต้องเข้าสู่ระบบใหม่ด้วยรหัสใหม่
    await authStore.logout()
    await router.push({ name: 'login' })
  } catch (e) {
    error.value = (e as Error).message || 'เปลี่ยนรหัสผ่านไม่สำเร็จ'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="max-w-md">
    <h2 class="font-display text-title-m font-bold mb-1">เปลี่ยนรหัสผ่าน</h2>
    <p class="text-body text-ink-2 mb-6">บัญชีที่ระบบสร้างให้ต้องเปลี่ยนรหัสผ่านก่อนเข้าใช้งานครั้งแรก</p>

    <form class="bg-surface rounded-card border border-line p-6" @submit.prevent="submit">
      <label class="block text-caption font-semibold text-ink-2 mb-1" for="old">รหัสผ่านเดิม</label>
      <input id="old" v-model="oldPassword" type="password" class="field mb-4" autocomplete="current-password" required />

      <label class="block text-caption font-semibold text-ink-2 mb-1" for="new">รหัสผ่านใหม่</label>
      <input id="new" v-model="newPassword" type="password" class="field mb-4" autocomplete="new-password" required />

      <label class="block text-caption font-semibold text-ink-2 mb-1" for="confirm">ยืนยันรหัสผ่านใหม่</label>
      <input id="confirm" v-model="confirmPassword" type="password" class="field mb-4" autocomplete="new-password" required />

      <p v-if="error" class="text-caption text-danger mb-3">{{ error }}</p>

      <AppButton type="submit" variant="primary" block :loading="loading">บันทึกรหัสผ่านใหม่</AppButton>
    </form>
  </div>
</template>
