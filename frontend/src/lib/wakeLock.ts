/**
 * 🔆 Screen Wake Lock — กันจอดับระหว่างถือโพยบนแสตน
 *
 * ⚠️ เบราว์เซอร์ปล่อย lock เองเมื่อแท็บถูกซ่อน ⇒ ต้องขอใหม่ตอนกลับมาเห็น (visibilitychange)
 * ⚠️ ไม่ supported (Safari รุ่นเก่า/iOS) = `supported=false` — UI ต้องซ่อนสวิตช์ ไม่ใช่กดแล้วเงียบ
 */
import { onUnmounted, ref } from 'vue'

export function useWakeLock() {
  const supported =
    typeof navigator !== 'undefined' && typeof navigator.wakeLock?.request === 'function'

  const active = ref(false)
  const wanted = ref(false)
  let sentinel: WakeLockSentinel | null = null

  async function acquire(): Promise<boolean> {
    if (!supported || !wanted.value) return false
    if (sentinel && !sentinel.released) return true
    try {
      sentinel = await navigator.wakeLock!.request('screen')
      active.value = true
      sentinel.addEventListener('release', () => {
        active.value = false
        sentinel = null
      })
      return true
    } catch {
      // ไม่ได้ (เช่นไม่มี gesture/แบตต่ำ/แท็บถูกซ่อน) — ปล่อยเงียบ ๆ ไม่ใช่ fatal
      active.value = false
      return false
    }
  }

  async function release(): Promise<void> {
    try {
      await sentinel?.release()
    } catch {
      /* ignore */
    }
    sentinel = null
    active.value = false
  }

  async function enable(): Promise<boolean> {
    wanted.value = true
    return acquire()
  }

  async function disable(): Promise<void> {
    wanted.value = false
    await release()
  }

  async function toggle(): Promise<void> {
    if (wanted.value) await disable()
    else await enable()
  }

  function onVisibility(): void {
    if (typeof document !== 'undefined' && document.visibilityState === 'visible') {
      void acquire()
    }
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibility)
  }
  onUnmounted(() => {
    if (typeof document !== 'undefined') {
      document.removeEventListener('visibilitychange', onVisibility)
    }
    void release()
  })

  return { supported, active, wanted, enable, disable, toggle }
}
