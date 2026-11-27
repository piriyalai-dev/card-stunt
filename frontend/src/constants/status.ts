import type { EventStatus, StuntStatus } from '@/types/domain'

/** ป้ายสถานะ Event — สีมาจาก token เท่านั้น (ห้าม hex ในเทมเพลต) */
export const EVENT_STATUS: Record<EventStatus, { label: string; className: string }> = {
  draft: { label: 'ฉบับร่าง', className: 'bg-canvas text-ink-2 border-line' },
  active: { label: 'ใช้งานอยู่', className: 'bg-ok-tint text-ok-strong border-ok-line' },
  archived: { label: 'เก็บถาวร', className: 'bg-warn-soft text-warn border-warn/30' },
}

export const STUNT_STATUS: Record<StuntStatus, { label: string; className: string }> = {
  draft: { label: 'ฉบับร่าง', className: 'bg-canvas text-ink-2 border-line' },
  ready: { label: 'พร้อม', className: 'bg-warn-soft text-warn border-warn/30' },
  published: { label: 'เผยแพร่', className: 'bg-ok-tint text-ok-strong border-ok-line' },
}
