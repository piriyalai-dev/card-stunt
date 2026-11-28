<script setup lang="ts">
/**
 * 🕵️ บันทึกการใช้งาน (admin — VIEW_AUDIT_LOG)
 *
 * รายการ audit_logs — กรองตาม action / service / status / entity + ค้นหาข้อความ
 * โหลดเพิ่มแบบ cursor (สร้างเวลา DESC)
 */
import { computed, onMounted, ref, watch } from 'vue'
import AppCard from '@/components/ui/AppCard.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { errorMessage, formatDateTime } from '@/lib/format'
import * as auditService from '@/services/audit'
import type { AuditLogOptions, AuditLogOut } from '@/types/domain'

const items = ref<AuditLogOut[]>([])
const options = ref<AuditLogOptions>({ actions: [], statuses: [], entity_types: [], service_names: [] })
const loading = ref(true)
const loadingMore = ref(false)
const error = ref('')
const nextCursor = ref<string | null>(null)
const hasMore = ref(false)

// filters
const q = ref('')
const action = ref('')
const serviceName = ref('')
const status = ref('')
const entityType = ref('')

const STATUS_BADGE: Record<string, string> = {
  success: 'bg-ok-soft text-ok-strong border-ok-line',
  error: 'bg-danger-soft text-danger border-danger/30',
}

function statusClass(s: string): string {
  return STATUS_BADGE[s] ?? 'bg-canvas text-ink-2 border-line'
}

function statusLabel(s: string): string {
  return s === 'success' ? 'สำเร็จ' : s === 'error' ? 'ล้มเหลว' : s
}

/** แสดง diff ของค่าเก่า/ใหม่ — บีบ JSON ให้อ่านได้ใน 1–2 บรรทัด */
function jsonText(v: unknown): string {
  if (v === null || v === undefined) return ''
  try {
    return typeof v === 'string' ? v : JSON.stringify(v)
  } catch {
    return String(v)
  }
}

const hasFilters = computed(
  () => !!(q.value || action.value || serviceName.value || status.value || entityType.value),
)

async function load(reset = true): Promise<void> {
  if (reset) {
    loading.value = true
    items.value = []
    nextCursor.value = null
    hasMore.value = false
  } else {
    loadingMore.value = true
  }
  error.value = ''
  try {
    const page = await auditService.listAuditLogs({
      q: q.value || undefined,
      action: action.value || undefined,
      service_name: serviceName.value || undefined,
      status: status.value || undefined,
      entity_type: entityType.value || undefined,
      cursor: nextCursor.value ?? undefined,
    })
    items.value = reset ? page.items : [...items.value, ...page.items]
    nextCursor.value = page.next_cursor
    hasMore.value = page.has_more
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
    loadingMore.value = false
  }
}

async function loadOptions(): Promise<void> {
  try {
    options.value = await auditService.getAuditOptions()
  } catch {
    /* options เป็นของเสริม — โหลดไม่ได้ก็ยังกรองผ่านช่องค้นหาได้ */
  }
}

watch([q, action, serviceName, status, entityType], () => void load(true))

onMounted(() => {
  void loadOptions()
  void load(true)
})
</script>

<template>
  <div>
    <PageHeader title="บันทึกการใช้งาน" description="ทุกการสร้าง/แก้ไข/ลบ — กรองและค้นหาย้อนหลังได้" />

    <AppCard>
      <!-- filters -->
      <div class="mb-3 flex flex-wrap gap-2">
        <input
          v-model="q"
          type="search"
          placeholder="ค้นหา actor / entity / endpoint…"
          class="min-w-[200px] flex-1 rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink-1"
        />
        <select v-model="action" class="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink-1">
          <option value="">ทุก action</option>
          <option v-for="a in options.actions" :key="a" :value="a">{{ a }}</option>
        </select>
        <select v-model="serviceName" class="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink-1">
          <option value="">ทุก service</option>
          <option v-for="s in options.service_names" :key="s" :value="s">{{ s }}</option>
        </select>
        <select v-model="status" class="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink-1">
          <option value="">ทุกสถานะ</option>
          <option v-for="s in options.statuses" :key="s" :value="s">{{ statusLabel(s) }}</option>
        </select>
        <select v-model="entityType" class="rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink-1">
          <option value="">ทุกชนิดข้อมูล</option>
          <option v-for="t in options.entity_types" :key="t" :value="t">{{ t }}</option>
        </select>
      </div>

      <div v-if="loading" class="py-10 text-center text-sm text-ink-2">กำลังโหลด…</div>

      <p v-else-if="error" class="py-10 text-center text-sm text-danger">{{ error }}</p>

      <p v-else-if="items.length === 0" class="py-10 text-center text-sm text-ink-2">
        {{ hasFilters ? 'ไม่มีรายการที่ตรงกับตัวกรอง' : 'ยังไม่มีบันทึก' }}
      </p>

      <ul v-else class="divide-y divide-line">
        <li v-for="log in items" :key="log.id" class="py-3">
          <div class="flex items-start gap-2">
            <span
              class="mt-0.5 inline-flex shrink-0 rounded-full border px-2 py-0.5 text-[11px] font-medium"
              :class="statusClass(log.status)"
            >
              {{ statusLabel(log.status) }}
            </span>
            <div class="min-w-0 flex-1">
              <p class="text-sm text-ink-1">
                <span class="font-semibold">{{ log.action }}</span>
                <span v-if="log.entity_type" class="text-ink-3"> · {{ log.entity_type }}#{{ log.entity_id }}</span>
              </p>
              <p class="mt-0.5 text-xs text-ink-3">
                {{ log.service_name }} · {{ log.actor_identifier }} · {{ formatDateTime(log.created_at) }}
                <span v-if="log.execution_time_ms != null"> · {{ log.execution_time_ms }} ms</span>
              </p>
              <p v-if="log.error_detail" class="mt-0.5 text-xs text-danger">{{ log.error_detail }}</p>
              <div
                v-if="jsonText(log.new_values) || jsonText(log.old_values)"
                class="mt-1 space-y-0.5 font-mono text-[11px] text-ink-3"
              >
                <div v-if="jsonText(log.old_values)">− {{ jsonText(log.old_values) }}</div>
                <div v-if="jsonText(log.new_values)">+ {{ jsonText(log.new_values) }}</div>
              </div>
            </div>
          </div>
        </li>
      </ul>

      <div v-if="hasMore" class="mt-3 flex justify-center">
        <button
          type="button"
          :disabled="loadingMore"
          class="inline-flex min-h-11 items-center rounded-xl border border-line bg-surface px-4 text-sm font-semibold text-ink-1 transition-colors hover:bg-canvas disabled:opacity-60"
          @click="load(false)"
        >
          <i v-if="loadingMore" class="bi bi-arrow-repeat mr-1 animate-spin"></i>
          โหลดเพิ่มเติม
        </button>
      </div>
    </AppCard>
  </div>
</template>
