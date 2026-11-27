<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import AppEmptyState from '@/components/ui/AppEmptyState.vue'
import IconButton from '@/components/ui/IconButton.vue'
import StudioCanvas from '@/components/studio/StudioCanvas.vue'
import type { CanvasCellEvent } from '@/components/studio/types'
import { cellToSeat, geometryOf, labelStyleOf, seatLabels } from '@/lib/geometry'
import { errorMessage, formatDateTime, formatNumber } from '@/lib/format'
import {
  EMPTY,
  GridEditor,
  GridHistory,
  colorCounts,
  decodeRle,
  despeckle,
  diffGrids,
  drawEllipse,
  drawRect,
  encodeRle,
  extractRegion,
  floodFill,
  fromApiGrid,
  gridEquals,
  normalizeRegion,
  nudge,
  paintLine,
  paintRegion,
  regionIndices,
  shapeCells,
  toApiGrid,
  type Grid,
  type GridChange,
  type Region,
} from '@/lib/grid'
import { lookupFromColors } from '@/lib/renderer'
import * as palettesService from '@/services/palettes'
import * as standsService from '@/services/stands'
import * as stuntsService from '@/services/stunts'
import type { PaletteOut, RevisionOut, StandOut, StuntOut } from '@/types/domain'

type Side = 'a' | 'b'
type Tool =
  | 'brush'
  | 'eraser'
  | 'bucket'
  | 'eyedropper'
  | 'line'
  | 'rect'
  | 'ellipse'
  | 'select'

const TOOLS: Array<{ key: Tool; label: string; icon: string; shortcut: string }> = [
  { key: 'brush', label: 'พู่กัน', icon: 'bi-brush', shortcut: 'B' },
  { key: 'eraser', label: 'ยางลบ', icon: 'bi-eraser', shortcut: 'E' },
  { key: 'bucket', label: 'เทสี', icon: 'bi-paint-bucket', shortcut: 'G' },
  { key: 'eyedropper', label: 'ดูดสี', icon: 'bi-eyedropper', shortcut: 'I' },
  { key: 'line', label: 'เส้นตรง', icon: 'bi-slash-lg', shortcut: 'L' },
  { key: 'rect', label: 'สี่เหลี่ยม', icon: 'bi-square', shortcut: 'R' },
  { key: 'ellipse', label: 'วงรี', icon: 'bi-circle', shortcut: 'O' },
  { key: 'select', label: 'เลือก', icon: 'bi-bounding-box', shortcut: 'M' },
]

const route = useRoute()
const router = useRouter()
const stuntId = computed(() => Number(route.params.stuntId))

const stunt = ref<StuntOut | null>(null)
const stand = ref<StandOut | null>(null)
const palettes = ref<PaletteOut[]>([])
const loading = ref(true)
const error = ref('')
const message = ref('')

const gridW = ref(0)
const gridH = ref(0)
const gridA = shallowRef<Grid>(new Int32Array(0))
const gridB = shallowRef<Grid>(new Int32Array(0))
const side = ref<Side>('a')
const revision = ref(0)
const countsTick = ref(0)

const historyA = new GridHistory()
const historyB = new GridHistory()
const historyTick = ref(0)

const dirty = ref(false)
const saving = ref(false)
const savedAt = ref<string | null>(null)

const tool = ref<Tool>('brush')
const brushSize = ref(1)
const selectedColorId = ref<number | null>(null)
const showGrid = ref(true)
const distanceMode = ref(false)

const hoverCell = ref<{ x: number; y: number; inside: boolean } | null>(null)

const preview = ref<number[] | null>(null)
const previewHex = ref<string | null>(null)

const selection = ref<Region | null>(null)
interface ClipboardState {
  paletteId: number
  w: number
  h: number
  values: Int32Array
}
const clipboard = ref<ClipboardState | null>(null)

const canvasRef = ref<{ fit: () => void; zoomBy: (factor: number) => void } | null>(null)

const referenceImage = shallowRef<HTMLImageElement | null>(null)
const referenceName = ref('')
const referenceFile = ref<File | null>(null)
const referenceUrl = ref<string | null>(null)
const showReference = ref(true)
const referenceOpacity = ref(0.35)

const showTextPanel = ref(false)
const textValue = ref('ข้อความ')
const textSize = ref(32)
const textBold = ref(true)

const showRevisions = ref(false)
const revisions = ref<RevisionOut[]>([])

interface DraftPayload {
  w: number
  h: number
  a: string
  b: string
  at: number
}
const draftBanner = ref<DraftPayload | null>(null)
const draftSavedAt = ref<string | null>(null)

// ── derived ──────────────────────────────────────────────────────
const paletteId = computed(() =>
  side.value === 'a' ? stunt.value?.palette_a_id : stunt.value?.palette_b_id,
)
const palette = computed(() => palettes.value.find((p) => p.id === paletteId.value) ?? null)
const colors = computed(() => palette.value?.colors ?? [])
const lookup = computed(() => lookupFromColors(colors.value))
const canEdit = computed(() => !!palette.value && colors.value.length > 0)
const canUseSideB = computed(() => !!stunt.value?.palette_b_id)

const geometry = computed(() => (stand.value ? geometryOf(stand.value) : null))
/** fallback สำหรับ template ก่อนข้อมูลโหลดครบ (ไม่ควรถูกใช้เมื่อ v-else-if ผ่าน) */
const displayGeometry = computed(() =>
  geometry.value ?? {
    rows: 1,
    cols: 1,
    subRows: 1,
    subCols: 1,
    rowDirection: 'top_to_bottom' as const,
    colDirection: 'left_to_right' as const,
  },
)
const labelsSpec = computed(() =>
  stand.value
    ? labelStyleOf(stand.value)
    : { rowStyle: 'alpha' as const, colStyle: 'numeric' as const, rowPrefix: '', colPrefix: '' },
)
const blocked = computed(
  () =>
    new Set(
      (stand.value?.blocked_seats ?? []).map((s) => `${s.row},${s.col}`),
    ),
)

function currentGrid(): Grid {
  return side.value === 'a' ? gridA.value : gridB.value
}

function historyFor(target: Side): GridHistory {
  return target === 'a' ? historyA : historyB
}

const canUndo = computed(() => {
  // อ่าน tick เพื่อให้ computed ถูก invalidate เมื่อประวัติ/ด้านเปลี่ยน
  if (historyTick.value < 0) return false
  return historyFor(side.value).canUndo
})
const canRedo = computed(() => {
  if (historyTick.value < 0) return false
  return historyFor(side.value).canRedo
})

const selectedColor = computed(
  () => colors.value.find((c) => c.id === selectedColorId.value) ?? null,
)

const counts = computed(() => {
  // ผูก dependency กับ tick/ด้าน — ไม่นับใหม่ทุก pointermove (ดู `countsTick`)
  if (countsTick.value < 0) return new Map<number, number>()
  return colorCounts(side.value === 'a' ? gridA.value : gridB.value)
})

const filled = computed(() => {
  let sum = 0
  for (const value of counts.value.values()) sum += value
  return sum
})

const totalCells = computed(() => gridW.value * gridH.value)
const emptyCells = computed(() => totalCells.value - filled.value)

const colorUsage = computed(() =>
  colors.value.map((c) => ({ color: c, count: counts.value.get(c.id) ?? 0 })),
)

const hoverDetail = computed(() => {
  const h = hoverCell.value
  const g = geometry.value
  const st = stand.value
  if (!h?.inside || !g || !st) return null
  const ref = cellToSeat(h.y, h.x, g)
  const labels = seatLabels(ref.seatRow, ref.seatCol, labelStyleOf(st))
  const value = currentGrid()[h.y * gridW.value + h.x]!
  const color = colors.value.find((c) => c.id === value) ?? null
  return { labels, ref, color }
})

// ── load ─────────────────────────────────────────────────────────
async function load() {
  loading.value = true
  error.value = ''
  try {
    const st = await stuntsService.getStunt(stuntId.value)
    stunt.value = st
    stand.value = await standsService.getStand(st.stand_id)
    palettes.value = await palettesService.listPalettes(st.event_id)
    gridW.value = st.grid_width
    gridH.value = st.grid_height
    textSize.value = Math.max(8, Math.floor(st.grid_height / 2))

    const grid = await stuntsService.getGrid(st.id)
    gridA.value = fromApiGrid(grid.grid_data_a, grid.grid_width, grid.grid_height)
    gridB.value = fromApiGrid(grid.grid_data_b, grid.grid_width, grid.grid_height)
    revision.value += 1
    countsTick.value += 1

    side.value = st.palette_a_id ? 'a' : st.palette_b_id ? 'b' : 'a'
    syncSelectedColor()

    const pending = takePendingImport()
    if (pending) {
      // 🔑 งานที่ยังไม่บันทึก (draft) ต้องมาก่อน แล้ว import ทับเป็นอีก 1 undo step
      //    ⇒ ผู้ใช้ไม่เสียสิ่งที่วาดไว้ก่อนไปหน้าแปลงรูป
      restoreDraftSilently()
      applyGridReplacement(pending.side, pending.grid, '')
      localStorage.removeItem(draftKey.value)
      draftBanner.value = null
      message.value = 'นำเข้าจากตัวแปลงเป็นพิกเซลแล้ว'
    } else {
      readDraft()
    }
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  void load()
  window.addEventListener('keydown', onKeyDown)
  window.addEventListener('beforeunload', onBeforeUnload)
})

onBeforeUnmount(() => {
  if (dirty.value) persistDraft()
  window.removeEventListener('keydown', onKeyDown)
  window.removeEventListener('beforeunload', onBeforeUnload)
  if (draftTimer) window.clearTimeout(draftTimer)
  if (referenceUrl.value) URL.revokeObjectURL(referenceUrl.value)
})

function syncSelectedColor() {
  if (!colors.value.some((c) => c.id === selectedColorId.value)) {
    selectedColorId.value = colors.value[0]?.id ?? null
  }
}

watch(paletteId, () => {
  syncSelectedColor()
  countsTick.value += 1
  revision.value += 1
})

watch(side, () => {
  syncSelectedColor()
  countsTick.value += 1
  revision.value += 1
  preview.value = null
  selection.value = null
  moving = null
  selectStart = null
})

// ── pending import / draft ──────────────────────────────────────
const pendingKey = (id: number) => `pixelstand:pending-import:${id}`

function takePendingImport(): { side: Side; grid: Grid } | null {
  const key = pendingKey(stuntId.value)
  const raw = sessionStorage.getItem(key)
  if (!raw) return null
  sessionStorage.removeItem(key)
  try {
    const data = JSON.parse(raw) as {
      side?: Side
      width?: number
      height?: number
      rle?: string
    }
    const target = data.side === 'b' ? 'b' : 'a'
    if (data.width !== gridW.value || data.height !== gridH.value || !data.rle) {
      message.value = 'ผลลัพธ์จากตัวแปลงมีขนาดไม่ตรงกับกริด — ไม่ได้นำเข้า'
      return null
    }
    if (target === 'b' && !canUseSideB.value) {
      message.value = 'ด้าน B ไม่มีชุดสี — ไม่ได้นำเข้าผลลัพธ์'
      return null
    }
    const grid = decodeRle(data.rle, gridW.value * gridH.value)
    if (!grid) {
      message.value = 'ข้อมูลจากตัวแปลงเสียหาย — ไม่ได้นำเข้า'
      return null
    }
    return { side: target, grid }
  } catch {
    return null
  }
}

function applyGridReplacement(target: Side, next: Grid, label: string, activate = true) {
  const grid = target === 'a' ? gridA.value : gridB.value
  if (grid.length !== next.length) return
  const editor = new GridEditor(grid)
  for (let i = 0; i < grid.length; i += 1) {
    if (grid[i] !== next[i]) editor.set(i, next[i]!)
  }
  const change = sanitizeBlocked(editor.commit(), grid)
  if (!change) return
  if (activate) side.value = target
  historyFor(target).push(change)
  historyTick.value += 1
  countsTick.value += 1
  revision.value += 1
  dirty.value = true
  scheduleDraftSave()
  message.value = label
}

const draftKey = computed(() => (stunt.value ? `pixelstand:draft:${stunt.value.id}` : ''))
let draftTimer: number | undefined

function decodeDraft(data: DraftPayload): { a: Grid; b: Grid } | null {
  if (data.w !== gridW.value || data.h !== gridH.value) return null
  const a = decodeRle(data.a, data.w * data.h)
  const b = decodeRle(data.b, data.w * data.h)
  return a && b ? { a, b } : null
}

function readDraft() {
  const key = draftKey.value
  if (!key) return
  const raw = localStorage.getItem(key)
  if (!raw) return
  try {
    const data = JSON.parse(raw) as DraftPayload
    const decoded = decodeDraft(data)
    if (!decoded) {
      localStorage.removeItem(key)
      return
    }
    if (gridEquals(decoded.a, gridA.value) && gridEquals(decoded.b, gridB.value)) {
      localStorage.removeItem(key)
      return
    }
    draftBanner.value = data
  } catch {
    localStorage.removeItem(key)
  }
}

/**
 * กู้ draft เงียบ ๆ ก่อน import จาก converter — ไม่ต้องมี banner
 * (ผู้ใช้ไม่ได้ขอ "กู้คืน" แต่การทิ้งงานที่วาดไว้เพื่อรับ import คือสิ่งที่ไม่ควรเกิด)
 */
function restoreDraftSilently(): boolean {
  const key = draftKey.value
  if (!key) return false
  const raw = localStorage.getItem(key)
  if (!raw) return false
  try {
    const data = JSON.parse(raw) as DraftPayload
    const decoded = decodeDraft(data)
    if (!decoded) return false
    let applied = false
    if (!gridEquals(decoded.a, gridA.value)) {
      applyGridReplacement('a', decoded.a, '', false)
      applied = true
    }
    if (!gridEquals(decoded.b, gridB.value)) {
      applyGridReplacement('b', decoded.b, '', false)
      applied = true
    }
    return applied
  } catch {
    return false
  }
}

function persistDraft() {
  if (!stunt.value || !dirty.value) return
  try {
    const payload: DraftPayload = {
      w: gridW.value,
      h: gridH.value,
      a: encodeRle(gridA.value),
      b: encodeRle(gridB.value),
      at: Date.now(),
    }
    localStorage.setItem(draftKey.value, JSON.stringify(payload))
    draftSavedAt.value = new Date().toISOString()
  } catch {
    /* localStorage เต็ม/ถูกปิด — ไม่ทำให้งานหลักล้ม */
  }
}

function scheduleDraftSave() {
  if (draftTimer) window.clearTimeout(draftTimer)
  draftTimer = window.setTimeout(persistDraft, 900)
}

function restoreDraft() {
  const data = draftBanner.value
  if (!data) return
  const a = decodeRle(data.a, gridW.value * gridH.value)
  const b = decodeRle(data.b, gridW.value * gridH.value)
  if (!a || !b) {
    draftBanner.value = null
    localStorage.removeItem(draftKey.value)
    return
  }
  applyGridReplacement('a', a, 'กู้คืนแบบร่างแล้ว', false)
  if (!gridEquals(b, gridB.value)) applyGridReplacement('b', b, 'กู้คืนแบบร่างด้าน B แล้ว', false)
  draftBanner.value = null
  localStorage.removeItem(draftKey.value)
}

function discardDraft() {
  draftBanner.value = null
  localStorage.removeItem(draftKey.value)
}

async function revertUnsaved() {
  if (!stunt.value) return
  if (!window.confirm('ทิ้งการแก้ไขที่ยังไม่บันทึกและโหลด grid จากเซิร์ฟเวอร์?')) return
  saving.value = true
  error.value = ''
  try {
    const grid = await stuntsService.getGrid(stunt.value.id)
    gridA.value = fromApiGrid(grid.grid_data_a, grid.grid_width, grid.grid_height)
    gridB.value = fromApiGrid(grid.grid_data_b, grid.grid_width, grid.grid_height)
    historyA.clear()
    historyB.clear()
    historyTick.value += 1
    countsTick.value += 1
    revision.value += 1
    dirty.value = false
    draftBanner.value = null
    draftSavedAt.value = null
    localStorage.removeItem(draftKey.value)
    message.value = 'โหลดจากเซิร์ฟเวอร์แล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── history helpers ─────────────────────────────────────────────
function sanitizeBlocked(
  change: GridChange | null,
  grid: Grid = currentGrid(),
): GridChange | null {
  if (!change) return null
  const g = geometry.value
  if (!g || blocked.value.size === 0) return change
  const keep: number[] = []
  for (let i = 0; i < change.indices.length; i += 1) {
    const index = change.indices[i]!
    const x = index % gridW.value
    const y = (index - x) / gridW.value
    const ref = cellToSeat(y, x, g)
    if (blocked.value.has(`${ref.seatRow},${ref.seatCol}`)) {
      grid[index] = change.before[i]!
    } else {
      keep.push(i)
    }
  }
  if (keep.length === change.indices.length) return change
  if (keep.length === 0) return null
  return {
    indices: Int32Array.from(keep, (i) => change.indices[i]!),
    before: Int32Array.from(keep, (i) => change.before[i]!),
    after: Int32Array.from(keep, (i) => change.after[i]!),
  }
}

function commitChange(change: GridChange | null) {
  const safe = sanitizeBlocked(change)
  if (!safe) return
  historyFor(side.value).push(safe)
  historyTick.value += 1
  countsTick.value += 1
  revision.value += 1
  dirty.value = true
  scheduleDraftSave()
}

function undo() {
  if (historyFor(side.value).undo(currentGrid())) {
    historyTick.value += 1
    countsTick.value += 1
    revision.value += 1
    dirty.value = true
    scheduleDraftSave()
  }
}

function redo() {
  if (historyFor(side.value).redo(currentGrid())) {
    historyTick.value += 1
    countsTick.value += 1
    revision.value += 1
    dirty.value = true
    scheduleDraftSave()
  }
}

// ── pointer tools ───────────────────────────────────────────────
interface Stroke {
  tool: Tool
  editor: GridEditor | null
  last: { x: number; y: number }
  start: { x: number; y: number }
}
let stroke: Stroke | null = null

// ── selection / clipboard ───────────────────────────────────────
let selectStart: { x: number; y: number } | null = null
interface MoveState {
  before: Grid
  source: Region
  values: Int32Array
  startX: number
  startY: number
}
let moving: MoveState | null = null

function insideRegion(x: number, y: number, region: Region): boolean {
  return x >= region.x && x < region.x + region.w && y >= region.y && y < region.y + region.h
}

function clampCellX(x: number): number {
  return Math.max(0, Math.min(gridW.value - 1, x))
}
function clampCellY(y: number): number {
  return Math.max(0, Math.min(gridH.value - 1, y))
}

function startSelection(event: CanvasCellEvent) {
  const grid = currentGrid()
  const sel = selection.value
  if (sel && insideRegion(event.x, event.y, sel)) {
    moving = {
      before: grid.slice(),
      source: sel,
      values: extractRegion(grid, gridW.value, sel),
      startX: event.x,
      startY: event.y,
    }
    return
  }
  moving = null
  selectStart = { x: event.x, y: event.y }
  selection.value = { x: event.x, y: event.y, w: 1, h: 1 }
  revision.value += 1
}

function moveSelection(event: CanvasCellEvent) {
  const x = clampCellX(event.x)
  const y = clampCellY(event.y)
  if (moving) {
    const dx = x - moving.startX
    const dy = y - moving.startY
    const grid = currentGrid()
    grid.set(moving.before)
    for (const index of regionIndices(moving.source, gridW.value)) grid[index] = EMPTY
    const editor = new GridEditor(grid)
    paintRegion(
      editor,
      gridW.value,
      gridH.value,
      moving.source.x + dx,
      moving.source.y + dy,
      moving.source,
      moving.values,
    )
    selection.value = normalizeRegion(
      moving.source.x + dx,
      moving.source.y + dy,
      moving.source.x + dx + moving.source.w - 1,
      moving.source.y + dy + moving.source.h - 1,
      gridW.value,
      gridH.value,
    )
    revision.value += 1
    return
  }
  if (selectStart) {
    selection.value = normalizeRegion(
      selectStart.x,
      selectStart.y,
      x,
      y,
      gridW.value,
      gridH.value,
    )
    revision.value += 1
  }
}

function finishSelection(event: CanvasCellEvent) {
  if (moving) {
    const before = moving.before
    moving = null
    commitChange(diffGrids(before, currentGrid()))
    return
  }
  if (selectStart) {
    selection.value = normalizeRegion(
      selectStart.x,
      selectStart.y,
      clampCellX(event.x),
      clampCellY(event.y),
      gridW.value,
      gridH.value,
    )
    selectStart = null
    revision.value += 1
  }
}

function copySelection() {
  const sel = selection.value
  const p = palette.value
  if (!sel || !p) return
  clipboard.value = {
    paletteId: p.id,
    w: sel.w,
    h: sel.h,
    values: extractRegion(currentGrid(), gridW.value, sel),
  }
  message.value = `คัดลอก ${sel.w}×${sel.h} ช่องแล้ว`
}

function cutSelection() {
  const sel = selection.value
  if (!sel || !palette.value) return
  copySelection()
  const editor = new GridEditor(currentGrid())
  for (const index of regionIndices(sel, gridW.value)) editor.set(index, EMPTY)
  commitChange(editor.commit())
  message.value = `ตัด ${sel.w}×${sel.h} ช่องแล้ว`
}

function pasteClipboard() {
  const clip = clipboard.value
  const p = palette.value
  if (!clip) return
  if (!p || clip.paletteId !== p.id) {
    error.value = 'คลิปบอร์ดมาจากชุดสีอื่น — สลับไปด้าน/ชุดสีเดิมก่อนจึงจะวางได้'
    return
  }
  const allowed = new Set(colors.value.map((c) => c.id))
  if (Array.from(clip.values).some((v) => v !== EMPTY && !allowed.has(v))) {
    error.value = 'สีในคลิปบอร์ดไม่อยู่ในชุดสีนี้แล้ว — คัดลอกใหม่'
    return
  }
  tool.value = 'select'
  const sel = selection.value
  const x = sel?.x ?? Math.floor((gridW.value - clip.w) / 2)
  const y = sel?.y ?? Math.floor((gridH.value - clip.h) / 2)
  const editor = new GridEditor(currentGrid())
  paintRegion(
    editor,
    gridW.value,
    gridH.value,
    x,
    y,
    { x: 0, y: 0, w: clip.w, h: clip.h },
    clip.values,
  )
  commitChange(editor.commit())
  selection.value = normalizeRegion(
    x,
    y,
    x + clip.w - 1,
    y + clip.h - 1,
    gridW.value,
    gridH.value,
  )
  revision.value += 1
  message.value = 'วางแล้ว — กด Undo ได้'
}

function deleteSelection() {
  const sel = selection.value
  if (!sel) return
  const editor = new GridEditor(currentGrid())
  for (const index of regionIndices(sel, gridW.value)) editor.set(index, EMPTY)
  commitChange(editor.commit())
}

function clearSelection() {
  selection.value = null
  moving = null
  selectStart = null
  revision.value += 1
}

function pickColor(event: CanvasCellEvent) {
  const value = currentGrid()[event.y * gridW.value + event.x]!
  if (value !== EMPTY) {
    selectedColorId.value = value
    tool.value = 'brush'
  }
}

function onCellDown(event: CanvasCellEvent) {
  if (!canEdit.value || !event.inside || gridW.value === 0) return
  if (tool.value === 'eyedropper' || event.altKey) {
    pickColor(event)
    return
  }
  if (tool.value === 'select') {
    startSelection(event)
    return
  }
  const value = tool.value === 'eraser' ? EMPTY : selectedColorId.value ?? EMPTY
  if (tool.value === 'brush' || tool.value === 'eraser') {
    const editor = new GridEditor(currentGrid())
    paintLine(editor, gridW.value, gridH.value, event.x, event.y, event.x, event.y, value, brushSize.value)
    stroke = { tool: tool.value, editor, last: { x: event.x, y: event.y }, start: { x: event.x, y: event.y } }
    revision.value += 1
    return
  }
  if (tool.value === 'bucket') {
    const editor = new GridEditor(currentGrid())
    commitChange(floodFill(editor, gridW.value, gridH.value, event.x, event.y, value))
    return
  }
  stroke = {
    tool: tool.value,
    editor: null,
    last: { x: event.x, y: event.y },
    start: { x: event.x, y: event.y },
  }
  updatePreview(event.x, event.y)
}

function onCellMove(event: CanvasCellEvent) {
  if (tool.value === 'select') {
    moveSelection(event)
    return
  }
  if (!stroke) return
  if (!event.inside) return
  if (stroke.tool === 'brush' || stroke.tool === 'eraser') {
    const value = stroke.tool === 'eraser' ? EMPTY : selectedColorId.value ?? EMPTY
    paintLine(
      stroke.editor!,
      gridW.value,
      gridH.value,
      stroke.last.x,
      stroke.last.y,
      event.x,
      event.y,
      value,
      brushSize.value,
    )
    stroke.last = { x: event.x, y: event.y }
    revision.value += 1
  } else {
    stroke.last = { x: event.x, y: event.y }
    updatePreview(event.x, event.y)
  }
}

function onCellUp(event: CanvasCellEvent) {
  if (tool.value === 'select') {
    finishSelection(event)
    return
  }
  if (!stroke) return
  const active = stroke
  stroke = null
  if (active.tool === 'brush' || active.tool === 'eraser') {
    commitChange(active.editor!.commit())
    return
  }
  const end = event.inside ? event : active.last
  const editor = new GridEditor(currentGrid())
  const value = selectedColorId.value ?? EMPTY
  if (active.tool === 'line') {
    paintLine(editor, gridW.value, gridH.value, active.start.x, active.start.y, end.x, end.y, value, brushSize.value)
  } else if (active.tool === 'rect') {
    drawRect(editor, gridW.value, gridH.value, active.start.x, active.start.y, end.x, end.y, value, false)
  } else if (active.tool === 'ellipse') {
    drawEllipse(editor, gridW.value, gridH.value, active.start.x, active.start.y, end.x, end.y, value, false)
  }
  preview.value = null
  previewHex.value = null
  commitChange(editor.commit())
}

function updatePreview(x: number, y: number) {
  if (!stroke) return
  if (stroke.tool !== 'line' && stroke.tool !== 'rect' && stroke.tool !== 'ellipse') return
  preview.value = shapeCells(
    stroke.tool,
    gridW.value,
    gridH.value,
    stroke.start.x,
    stroke.start.y,
    x,
    y,
  )
  previewHex.value = selectedColor.value?.hex ?? '#000000'
  revision.value += 1
}

// ── whole-sheet ops ─────────────────────────────────────────────
function replaceWholeGrid(next: Grid) {
  const grid = currentGrid()
  const editor = new GridEditor(grid)
  for (let i = 0; i < grid.length; i += 1) {
    if (grid[i] !== next[i]) editor.set(i, next[i]!)
  }
  commitChange(editor.commit())
}

function shift(dx: number, dy: number) {
  if (!canEdit.value) return
  replaceWholeGrid(nudge(currentGrid(), gridW.value, gridH.value, dx, dy))
}

function runDespeckle() {
  if (!canEdit.value) return
  const editor = new GridEditor(currentGrid())
  commitChange(despeckle(editor, gridW.value, gridH.value))
  message.value = 'ลบจุดเดี่ยวแล้ว (กด Undo ได้)'
}

function clearGrid() {
  if (!canEdit.value) return
  if (!window.confirm('ล้างพิกเซลทั้งแผ่น? (กด Undo ได้)')) return
  replaceWholeGrid(new Int32Array(gridW.value * gridH.value).fill(EMPTY))
}

function applyText() {
  if (!canEdit.value) return
  const colorId = selectedColorId.value
  if (!colorId) return
  const canvas = document.createElement('canvas')
  canvas.width = gridW.value
  canvas.height = gridH.value
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  const family = '"Noto Sans Thai", Tahoma, sans-serif'
  const weight = textBold.value ? '700' : '400'
  let size = Math.max(6, textSize.value)
  ctx.font = `${weight} ${size}px ${family}`
  const text = textValue.value || ' '
  const measured = ctx.measureText(text).width
  const maxWidth = gridW.value * 0.92
  if (measured > maxWidth) {
    size = Math.max(6, Math.floor((size * maxWidth) / measured))
    ctx.font = `${weight} ${size}px ${family}`
  }
  ctx.fillStyle = '#FFFFFF'
  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillText(text, gridW.value / 2, gridH.value / 2)
  const data = ctx.getImageData(0, 0, gridW.value, gridH.value).data
  const editor = new GridEditor(currentGrid())
  for (let i = 0; i < gridW.value * gridH.value; i += 1) {
    if (data[i * 4 + 3]! > 96) editor.set(i, colorId)
  }
  commitChange(editor.commit())
  showTextPanel.value = false
  message.value = 'เพิ่มข้อความแล้ว (กด Undo ได้)'
}

// ── save ────────────────────────────────────────────────────────
async function save() {
  if (!stunt.value || !canEdit.value || saving.value || !dirty.value) return
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const body: {
      grid_data_a: Array<number | null>
      grid_data_b?: Array<number | null>
      note: string
    } = {
      grid_data_a: toApiGrid(gridA.value),
      note: `Studio ${new Date().toLocaleString('th-TH')}`,
    }
    if (stunt.value.palette_b_id) body.grid_data_b = toApiGrid(gridB.value)
    const updated = await stuntsService.saveGrid(stunt.value.id, body)
    stunt.value = updated
    dirty.value = false
    savedAt.value = new Date().toISOString()
    draftSavedAt.value = null
    localStorage.removeItem(draftKey.value)
    draftBanner.value = null
    message.value = 'บันทึกขึ้นเซิร์ฟเวอร์แล้ว'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── revisions ───────────────────────────────────────────────────
async function openRevisions() {
  if (!stunt.value) return
  try {
    revisions.value = await stuntsService.listRevisions(stunt.value.id)
    showRevisions.value = true
  } catch (e) {
    error.value = errorMessage(e)
  }
}

async function restoreRevision(rev: RevisionOut) {
  if (!stunt.value) return
  if (!window.confirm(`ย้อนกลับไป revision #${rev.revision_no}? สถานะปัจจุบันจะถูกเก็บเป็น revision ใหม่`)) {
    return
  }
  saving.value = true
  error.value = ''
  try {
    await stuntsService.restoreRevision(stunt.value.id, rev.id)
    const grid = await stuntsService.getGrid(stunt.value.id)
    gridA.value = fromApiGrid(grid.grid_data_a, grid.grid_width, grid.grid_height)
    gridB.value = fromApiGrid(grid.grid_data_b, grid.grid_width, grid.grid_height)
    historyA.clear()
    historyB.clear()
    historyTick.value += 1
    countsTick.value += 1
    revision.value += 1
    dirty.value = false
    draftBanner.value = null
    localStorage.removeItem(draftKey.value)
    showRevisions.value = false
    message.value = `ย้อนกลับไป revision #${rev.revision_no} แล้ว`
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── reference image ─────────────────────────────────────────────
function onReferenceFile(domEvent: Event) {
  const input = domEvent.target as HTMLInputElement
  const file = input.files?.[0]
  if (!file) return
  if (!file.type.startsWith('image/')) {
    error.value = 'ไฟล์ต้องเป็นรูปภาพ'
    return
  }
  if (referenceUrl.value) URL.revokeObjectURL(referenceUrl.value)
  referenceFile.value = file
  referenceName.value = file.name
  const url = URL.createObjectURL(file)
  referenceUrl.value = url
  const img = new Image()
  img.onload = () => {
    referenceImage.value = img
    showReference.value = true
  }
  img.src = url
  input.value = ''
}

async function saveReference() {
  if (!stunt.value || !referenceFile.value) return
  saving.value = true
  error.value = ''
  try {
    await stuntsService.uploadReference(stunt.value.id, referenceFile.value)
    message.value = 'บันทึกภาพอ้างอิงแล้ว (การแสดงผลหลังรีโหลดจะมา Phase 5)'
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

// ── keyboard ────────────────────────────────────────────────────
function isTypingTarget(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null
  if (!el) return false
  const tag = el.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || el.isContentEditable
}

function onKeyDown(event: KeyboardEvent) {
  if (isTypingTarget(event.target)) return
  const mod = event.ctrlKey || event.metaKey
  const key = event.key.toLowerCase()
  if (mod && key === 'z') {
    event.preventDefault()
    if (event.shiftKey) redo()
    else undo()
    return
  }
  if (mod && key === 'y') {
    event.preventDefault()
    redo()
    return
  }
  if (mod && key === 's') {
    event.preventDefault()
    void save()
    return
  }
  if (mod && key === 'c' && selection.value) {
    event.preventDefault()
    copySelection()
    return
  }
  if (mod && key === 'x' && selection.value) {
    event.preventDefault()
    cutSelection()
    return
  }
  if (mod && key === 'v' && clipboard.value) {
    event.preventDefault()
    pasteClipboard()
    return
  }
  if (mod) return

  if ((event.key === 'Delete' || event.key === 'Backspace') && selection.value) {
    event.preventDefault()
    deleteSelection()
    return
  }
  if (event.key === 'Escape') {
    clearSelection()
    return
  }

  const shortcut: Record<string, Tool> = {
    b: 'brush',
    e: 'eraser',
    g: 'bucket',
    i: 'eyedropper',
    l: 'line',
    r: 'rect',
    o: 'ellipse',
    m: 'select',
  }
  if (shortcut[key]) {
    tool.value = shortcut[key]!
    return
  }
  if (key === 'p') {
    distanceMode.value = !distanceMode.value
    return
  }
  if (key === 't') {
    showTextPanel.value = true
    return
  }
  if (key === '0') {
    canvasRef.value?.fit()
    return
  }
  if (key === '+' || key === '=') {
    canvasRef.value?.zoomBy(1.2)
    return
  }
  if (key === '-') {
    canvasRef.value?.zoomBy(1 / 1.2)
    return
  }
  if (event.key.startsWith('Arrow')) {
    event.preventDefault()
    const step = event.shiftKey ? 5 : 1
    if (event.key === 'ArrowUp') shift(0, -step)
    if (event.key === 'ArrowDown') shift(0, step)
    if (event.key === 'ArrowLeft') shift(-step, 0)
    if (event.key === 'ArrowRight') shift(step, 0)
  }
}

function onBeforeUnload(event: BeforeUnloadEvent) {
  if (!dirty.value) return
  event.preventDefault()
  event.returnValue = ''
}

function backToStunts() {
  if (dirty.value) persistDraft()
  if (!stunt.value) return
  void router.push({ name: 'event-stunts', params: { eventId: stunt.value.event_id } })
}

function openConverter() {
  if (dirty.value) persistDraft()
  if (!stunt.value) return
  void router.push({ name: 'stunt-convert', params: { stuntId: stunt.value.id } })
}

function setTool(next: Tool) {
  tool.value = next
  if (next !== 'line' && next !== 'rect' && next !== 'ellipse') {
    preview.value = null
  }
}
</script>

<template>
  <div class="space-y-3">
    <!-- แถบหัว -->
    <div class="flex flex-wrap items-center gap-2">
      <AppButton variant="secondary" size="sm" @click="backToStunts">
        <template #icon><i class="bi bi-arrow-left" aria-hidden="true" /></template>
        กลับไปฉาก
      </AppButton>
      <div class="min-w-0">
        <h2 class="font-display text-title-m font-bold truncate">
          Pixel Studio
          <span v-if="stunt" class="text-ink-2">· {{ stunt.code }} {{ stunt.title }}</span>
        </h2>
        <p class="text-caption text-ink-2">
          {{ gridW }} × {{ gridH }} = {{ formatNumber(totalCells) }} ช่อง
          <span v-if="dirty" class="text-warn">· ยังไม่บันทึก</span>
          <span v-else-if="savedAt" class="text-ok-strong">· บันทึกแล้ว {{ formatDateTime(savedAt) }}</span>
        </p>
      </div>

      <div class="ml-auto inline-flex rounded-control border border-line bg-surface p-0.5">
        <button
          type="button"
          class="h-9 rounded-lg px-3 text-[13px] font-semibold"
          :class="side === 'a' ? 'bg-brand-tint text-brand' : 'text-ink-2'"
          @click="side = 'a'"
        >
          ด้าน A
        </button>
        <button
          type="button"
          class="h-9 rounded-lg px-3 text-[13px] font-semibold disabled:opacity-40"
          :class="side === 'b' ? 'bg-brand-tint text-brand' : 'text-ink-2'"
          :disabled="!canUseSideB"
          @click="side = 'b'"
        >
          ด้าน B
        </button>
      </div>

      <AppButton size="sm" :loading="saving" :disabled="!canEdit || !dirty" @click="save">
        <template #icon><i class="bi bi-cloud-arrow-up" aria-hidden="true" /></template>
        บันทึก
      </AppButton>
    </div>

    <p v-if="error" class="rounded-control border border-danger/30 bg-danger-soft px-3 py-2 text-caption text-danger">
      {{ error }}
    </p>
    <p v-if="message" class="rounded-control border border-ok-line bg-ok-soft px-3 py-2 text-caption text-ok-strong">
      {{ message }}
    </p>

    <!-- draft ที่ยังไม่บันทึก -->
    <div
      v-if="draftBanner"
      class="flex flex-wrap items-center gap-2 rounded-control border border-warn/30 bg-warn-soft px-3 py-2 text-caption text-warn"
    >
      <i class="bi bi-clock-history" aria-hidden="true" />
      พบแบบร่างที่ยังไม่บันทึก ({{ formatDateTime(new Date(draftBanner.at).toISOString()) }})
      <AppButton size="sm" variant="secondary" class="ml-auto" @click="restoreDraft">กู้คืน</AppButton>
      <AppButton size="sm" variant="text" @click="discardDraft">ทิ้ง</AppButton>
    </div>

    <div v-if="loading" class="h-72 rounded-card border border-line bg-surface skeleton-shimmer" />

    <AppEmptyState
      v-else-if="!canEdit"
      icon="bi-palette"
      title="ฉากนี้ยังไม่มีชุดสีที่ใช้ได้"
      description="กลับไปหน้าแก้ไขฉากเพื่อกำหนดชุดสี A (และ B ถ้าต้องการ) ก่อนเปิด Studio"
    >
      <AppButton size="sm" @click="backToStunts">กลับไปแก้ไขฉาก</AppButton>
    </AppEmptyState>

    <template v-else>
      <!-- แถบเครื่องมือ -->
      <AppCard :padded="true">
        <div class="flex flex-wrap items-center gap-1.5">
          <IconButton
            v-for="item in TOOLS"
            :key="item.key"
            :icon="item.icon"
            :label="`${item.label} (${item.shortcut})`"
            :active="tool === item.key"
            @click="setTool(item.key)"
          />
          <span class="mx-1 h-6 w-px bg-line" aria-hidden="true" />
          <label class="flex items-center gap-1.5 text-caption text-ink-2">
            ขนาด
            <select v-model.number="brushSize" class="field !w-16 !py-1.5">
              <option v-for="n in 8" :key="n" :value="n">{{ n }}</option>
            </select>
          </label>
          <span class="mx-1 h-6 w-px bg-line" aria-hidden="true" />
          <IconButton icon="bi-arrow-counterclockwise" label="Undo (Ctrl+Z)" :disabled="!canUndo" @click="undo" />
          <IconButton icon="bi-arrow-clockwise" label="Redo (Ctrl+Shift+Z)" :disabled="!canRedo" @click="redo" />
          <span class="mx-1 h-6 w-px bg-line" aria-hidden="true" />
          <IconButton icon="bi-arrow-up" label="เลื่อนทั้งแผ่นขึ้น (ลูกศร)" @click="shift(0, -1)" />
          <IconButton icon="bi-arrow-down" label="เลื่อนทั้งแผ่นลง" @click="shift(0, 1)" />
          <IconButton icon="bi-arrow-left" label="เลื่อนทั้งแผ่นซ้าย" @click="shift(-1, 0)" />
          <IconButton icon="bi-arrow-right" label="เลื่อนทั้งแผ่นขวา" @click="shift(1, 0)" />
          <span class="mx-1 h-6 w-px bg-line" aria-hidden="true" />
          <IconButton icon="bi-zoom-out" label="ย่อ (ลูกศร -)" @click="canvasRef?.zoomBy(1 / 1.2)" />
          <IconButton icon="bi-zoom-in" label="ขยาย (ลูกศร +)" @click="canvasRef?.zoomBy(1.2)" />
          <IconButton icon="bi-arrows-fullscreen" label="พอดีจอ (0)" @click="canvasRef?.fit()" />
          <IconButton
            icon="bi-grid-3x3"
            label="แสดง/ซ่อนกริด"
            :active="showGrid"
            @click="showGrid = !showGrid"
          />
          <IconButton
            icon="bi-binoculars"
            label="ทดสอบมองไกล (P)"
            :active="distanceMode"
            @click="distanceMode = !distanceMode"
          />
          <IconButton icon="bi-fonts" label="เพิ่มข้อความ (T)" @click="showTextPanel = !showTextPanel" />
          <span class="mx-1 h-6 w-px bg-line" aria-hidden="true" />
          <IconButton
            icon="bi-clipboard"
            label="คัดลอกที่เลือก (Ctrl+C)"
            :disabled="!selection"
            @click="copySelection"
          />
          <IconButton
            icon="bi-scissors"
            label="ตัดที่เลือก (Ctrl+X)"
            :disabled="!selection"
            @click="cutSelection"
          />
          <IconButton
            icon="bi-clipboard-plus"
            label="วาง (Ctrl+V)"
            :disabled="!clipboard"
            @click="pasteClipboard"
          />
          <IconButton
            icon="bi-x-square"
            label="ลบที่เลือก (Delete)"
            :disabled="!selection"
            @click="deleteSelection"
          />
          <span class="mx-1 h-6 w-px bg-line" aria-hidden="true" />
          <IconButton icon="bi-magic" label="ลบจุดเดี่ยว" @click="runDespeckle" />
          <IconButton icon="bi-trash3" label="ล้างทั้งแผ่น" danger @click="clearGrid" />
          <AppButton size="sm" variant="secondary" class="ml-auto" @click="openConverter">
            <template #icon><i class="bi bi-image" aria-hidden="true" /></template>
            แปลงรูป
          </AppButton>
        </div>
      </AppCard>

      <div class="grid gap-3 lg:grid-cols-[minmax(0,1fr)_300px]">
        <!-- canvas -->
        <AppCard :padded="false" class="overflow-hidden">
          <div class="h-[58vh] min-h-[340px]">
            <StudioCanvas
              ref="canvasRef"
              :grid="currentGrid()"
              :revision="revision"
              :width="gridW"
              :height="gridH"
              :lookup="lookup"
              :geometry="displayGeometry"
              :labels="labelsSpec"
              :blocked="blocked"
              :show-grid="showGrid"
              :distance-mode="distanceMode"
              :reference="referenceImage"
              :show-reference="showReference"
              :reference-opacity="referenceOpacity"
              :preview="preview"
              :preview-hex="previewHex"
              :selection="tool === 'select' ? selection : null"
              @cell-down="onCellDown"
              @cell-move="onCellMove"
              @cell-up="onCellUp"
              @hover="hoverCell = $event"
            />
          </div>
        </AppCard>

        <!-- side panel -->
        <div class="space-y-3">
          <AppCard :padded="true">
            <h3 class="mb-1 text-caption font-bold text-ink-2">พิกัด</h3>
            <template v-if="hoverDetail">
              <p class="font-semibold">
                {{ hoverDetail.labels.row }} · {{ hoverDetail.labels.col }}
              </p>
              <p class="text-caption text-ink-2">
                ช่องย่อย {{ hoverDetail.ref.subRow + 1 }},{{ hoverDetail.ref.subCol + 1 }}
                · {{ hoverDetail.color ? `${hoverDetail.color.code} ${hoverDetail.color.name_th}` : 'ว่าง' }}
              </p>
            </template>
            <p v-else class="text-caption text-ink-3">ชี้เมาส์/นิ้วบนผังเพื่อดูพิกัด</p>
          </AppCard>

          <AppCard :padded="true">
            <div class="mb-2 flex items-center justify-between">
              <h3 class="text-caption font-bold text-ink-2">
                ชุดสี {{ side.toUpperCase() }}
              </h3>
              <span class="text-[11px] text-ink-3">{{ palette?.name }}</span>
            </div>
            <div class="grid grid-cols-3 gap-1.5">
              <button
                v-for="color in colors"
                :key="color.id"
                type="button"
                class="flex h-10 items-center justify-center rounded-control border text-[12px] font-bold transition"
                :class="selectedColorId === color.id ? 'ring-2 ring-brand ring-offset-1' : 'border-line'"
                :style="{ backgroundColor: color.hex, color: color.text_color }"
                :title="`${color.code} · ${color.name_th}`"
                @click="selectedColorId = color.id"
              >
                {{ color.code }}
              </button>
            </div>
            <div class="mt-2 text-caption text-ink-2">
              เลือกอยู่:
              <span class="font-semibold text-ink-1">
                {{ selectedColor ? `${selectedColor.code} · ${selectedColor.name_th}` : '—' }}
              </span>
            </div>
          </AppCard>

          <AppCard :padded="true">
            <div class="mb-2 flex items-center justify-between">
              <h3 class="text-caption font-bold text-ink-2">จำนวนช่อง</h3>
              <span class="text-[11px]" :class="emptyCells > 0 ? 'text-warn' : 'text-ok-strong'">
                ว่าง {{ formatNumber(emptyCells) }}
              </span>
            </div>
            <div class="space-y-1">
              <div
                v-for="row in colorUsage"
                :key="row.color.id"
                class="flex items-center gap-2 text-caption"
              >
                <span class="h-3.5 w-3.5 rounded border border-line" :style="{ backgroundColor: row.color.hex }" aria-hidden="true" />
                <span class="font-mono text-[11px]">{{ row.color.code }}</span>
                <span class="min-w-0 flex-1 truncate text-ink-3">{{ row.color.name_th }}</span>
                <span class="tabular-nums text-ink-2">{{ formatNumber(row.count) }}</span>
              </div>
            </div>
          </AppCard>

          <AppCard v-if="showTextPanel" :padded="true">
            <h3 class="mb-2 text-caption font-bold text-ink-2">เพิ่มข้อความ</h3>
            <div class="space-y-2">
              <input v-model="textValue" class="field" placeholder="ข้อความ" />
              <label class="flex items-center gap-2 text-caption text-ink-2">
                ขนาด
                <input v-model.number="textSize" type="range" min="8" :max="gridH" class="w-full accent-brand" />
                <span class="w-8 text-right tabular-nums">{{ textSize }}</span>
              </label>
              <label class="flex items-center gap-2 text-sm">
                <input v-model="textBold" type="checkbox" class="h-4 w-4" /> ตัวหนา
              </label>
              <div class="flex gap-2">
                <AppButton size="sm" @click="applyText">วาดข้อความ</AppButton>
                <AppButton size="sm" variant="secondary" @click="showTextPanel = false">ปิด</AppButton>
              </div>
              <p class="text-[11px] text-ink-3">ใช้สีที่เลือกอยู่ · ผลลัพธ์เป็น 1 ขั้น undo</p>
            </div>
          </AppCard>

          <AppCard :padded="true">
            <h3 class="mb-2 text-caption font-bold text-ink-2">ภาพอ้างอิง</h3>
            <label class="flex items-center gap-2 text-sm">
              <input v-model="showReference" type="checkbox" class="h-4 w-4" :disabled="!referenceImage" />
              แสดงภาพอ้างอิง
            </label>
            <label class="mt-1 flex items-center gap-2 text-caption text-ink-2">
              <span class="shrink-0 whitespace-nowrap">ความทึบ</span>
              <input v-model.number="referenceOpacity" type="range" min="0.05" max="1" step="0.05" class="w-full accent-brand" :disabled="!referenceImage" />
            </label>
            <div class="mt-2 flex flex-wrap gap-1.5">
              <label class="inline-flex h-9 cursor-pointer items-center gap-1 rounded-control border border-line bg-surface px-2 text-[12px] font-semibold hover:bg-canvas">
                <i class="bi bi-image" aria-hidden="true" />
                เลือกภาพ
                <input type="file" accept="image/*" class="hidden" @change="onReferenceFile" />
              </label>
              <AppButton
                size="sm"
                variant="secondary"
                :disabled="!referenceFile"
                :loading="saving"
                @click="saveReference"
              >
                บันทึกเป็นภาพอ้างอิง
              </AppButton>
            </div>
            <p v-if="referenceName" class="mt-1 truncate text-[11px] text-ink-3">{{ referenceName }}</p>
          </AppCard>

          <AppCard :padded="true">
            <h3 class="mb-2 text-caption font-bold text-ink-2">ประวัติ</h3>
            <div class="flex flex-wrap gap-1.5">
              <AppButton size="sm" variant="secondary" @click="openRevisions">ดู revisions</AppButton>
              <AppButton
                size="sm"
                variant="secondary"
                :disabled="!dirty"
                :loading="saving"
                @click="revertUnsaved"
              >
                ทิ้งการแก้ไขที่ยังไม่บันทึก
              </AppButton>
            </div>
            <p class="mt-1 text-[11px] text-ink-3">
              แบบร่างสำรองอัตโนมัติ:
              {{ draftSavedAt ? formatDateTime(draftSavedAt) : 'ยังไม่มี' }}
            </p>
          </AppCard>
        </div>
      </div>

      <!-- revisions -->
      <AppCard v-if="showRevisions" :padded="true">
        <div class="mb-2 flex items-center justify-between">
          <h3 class="font-display text-title-m font-bold">Revisions</h3>
          <AppButton size="sm" variant="secondary" @click="showRevisions = false">ปิด</AppButton>
        </div>
        <p v-if="revisions.length === 0" class="text-caption text-ink-2">ยังไม่มี revision</p>
        <ul v-else class="divide-y divide-line">
          <li v-for="rev in revisions" :key="rev.id" class="flex flex-wrap items-center gap-2 py-2">
            <span class="font-semibold">#{{ rev.revision_no }}</span>
            <span class="text-caption text-ink-2">{{ formatDateTime(rev.created_at) }}</span>
            <span class="text-caption text-ink-3">{{ rev.grid_width }}×{{ rev.grid_height }}</span>
            <span v-if="rev.note" class="min-w-0 flex-1 truncate text-caption text-ink-3">{{ rev.note }}</span>
            <AppButton size="sm" variant="secondary" class="ml-auto" :loading="saving" @click="restoreRevision(rev)">
              ย้อนกลับ
            </AppButton>
          </li>
        </ul>
      </AppCard>

      <p v-if="distanceMode" class="text-caption text-ink-2">
        โหมดทดสอบมองไกล: ซ่อนกริด + เบลอเล็กน้อย — กด P อีกครั้งเพื่อกลับ
      </p>
    </template>
  </div>
</template>
