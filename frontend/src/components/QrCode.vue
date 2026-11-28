<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import QRCode from 'qrcode'

/**
 * 🔳 QR code จาก string — เรนเดอร์เป็น `<img>` data URL (ใช้ lib `qrcode`)
 *
 * สีเข้ม/อ่อนตรงกับ design token (`ink-1` บนขาว) เพื่อให้เครื่องสแกนอ่านง่าย
 */
const props = defineProps<{
  value: string
  size?: number
}>()

const dataUrl = ref('')

async function render(): Promise<void> {
  if (!props.value) {
    dataUrl.value = ''
    return
  }
  try {
    dataUrl.value = await QRCode.toDataURL(props.value, {
      width: props.size ?? 160,
      margin: 1,
      color: { dark: '#1F2328', light: '#FFFFFF' },
    })
  } catch {
    dataUrl.value = ''
  }
}

onMounted(render)
watch(() => props.value, render)
</script>

<template>
  <img
    v-if="dataUrl"
    :src="dataUrl"
    :width="size ?? 160"
    :height="size ?? 160"
    alt="QR code"
    class="rounded-control border border-line"
  />
</template>
