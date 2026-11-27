// Screen Wake Lock API (Living Standard — ยังไม่อยู่ใน lib.dom ของ TS บางรุ่น)
export {}

declare global {
  interface WakeLockSentinel extends EventTarget {
    readonly released: boolean
    release(): Promise<void>
  }

  interface WakeLock {
    request(type: 'screen'): Promise<WakeLockSentinel>
  }

  interface Navigator {
    wakeLock?: WakeLock
  }
}
