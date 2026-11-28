import { ref } from 'vue'

/**
 * access token สั้น (นาที) — เก็บใน memory เท่านั้น ไม่ใช่ localStorage ไม่ใช่ cookie
 * ⇒ XSS อ่านไม่เจอ (refresh token ที่อายุยาวกว่าอยู่ใน httpOnly cookie ฝั่ง backend)
 * ใช้ `ref` ร่วมกันระหว่าง store (reactivity) กับ axios interceptor (อ่าน token)
 */
export const accessToken = ref<string | null>(null)
