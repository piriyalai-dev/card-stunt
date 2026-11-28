<script setup lang="ts">
/**
 * 👥 จัดการผู้ใช้ (admin — MANAGE_USERS)
 *
 * สร้าง/แก้ (role · display_name · reset password) / ลบ บัญชี
 * role 3 ระดับ: admin / designer / staff — สิทธิ์ย่อยมาจาก config/roles.json ฝั่ง backend
 */
import { computed, onMounted, ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import AppCard from '@/components/ui/AppCard.vue'
import PageHeader from '@/components/ui/PageHeader.vue'
import { errorMessage } from '@/lib/format'
import * as usersService from '@/services/users'
import type { UserOut, UserRole } from '@/types/domain'

const users = ref<UserOut[]>([])
const loading = ref(true)
const error = ref('')
const actionError = ref('')
const message = ref('')

const ROLE_LABEL: Record<UserRole, string> = {
  admin: 'แอดมิน',
  designer: 'ดีไซเนอร์',
  staff: 'เจ้าหน้าที่',
}

const ROLE_BADGE: Record<UserRole, string> = {
  admin: 'bg-brand-tint text-brand border-brand/20',
  designer: 'bg-ok-soft text-ok-strong border-ok-line',
  staff: 'bg-canvas text-ink-2 border-line',
}

// ── modal ─────────────────────────────────────────────────────────
const modalOpen = ref(false)
const editing = ref<UserOut | null>(null)
const form = ref({ username: '', password: '', display_name: '', role: 'staff' as UserRole })
const saving = ref(false)

function openCreate(): void {
  editing.value = null
  form.value = { username: '', password: '', display_name: '', role: 'staff' }
  actionError.value = ''
  modalOpen.value = true
}

function openEdit(u: UserOut): void {
  editing.value = u
  form.value = { username: u.username, password: '', display_name: u.display_name ?? '', role: u.role }
  actionError.value = ''
  modalOpen.value = true
}

function closeModal(): void {
  modalOpen.value = false
  editing.value = null
}

async function load(): Promise<void> {
  loading.value = true
  error.value = ''
  try {
    users.value = await usersService.listUsers()
  } catch (e) {
    error.value = errorMessage(e)
  } finally {
    loading.value = false
  }
}

async function save(): Promise<void> {
  if (saving.value) return
  saving.value = true
  actionError.value = ''
  try {
    const payload = {
      display_name: form.value.display_name.trim() || null,
      role: form.value.role,
      ...(editing.value ? {} : { username: form.value.username.trim() }),
      ...(form.value.password ? { password: form.value.password } : {}),
    }
    if (editing.value) {
      await usersService.updateUser(editing.value.id, payload)
      message.value = `อัปเดต "${editing.value.username}" แล้ว`
    } else {
      if (!payload.username || !form.value.password) {
        actionError.value = 'ต้องกรอก username และรหัสผ่าน'
        return
      }
      await usersService.createUser(payload as never)
      message.value = `สร้างผู้ใช้ "${payload.username}" แล้ว`
    }
    closeModal()
    await load()
  } catch (e) {
    actionError.value = errorMessage(e)
  } finally {
    saving.value = false
  }
}

async function remove(u: UserOut): Promise<void> {
  if (!window.confirm(`ลบบัญชี "${u.username}"? ทำแล้วย้อนกลับไม่ได้`)) return
  try {
    await usersService.deleteUser(u.id)
    message.value = `ลบ "${u.username}" แล้ว`
    await load()
  } catch (e) {
    actionError.value = errorMessage(e)
  }
}

const isEditing = computed(() => editing.value !== null)

onMounted(load)
</script>

<template>
  <div>
    <PageHeader
      title="จัดการผู้ใช้"
      description="บัญชีผู้ดูแลระบบแปรอักษร — role กำหนดสิทธิ์ย่อยจาก config/roles.json"
    >
      <template #actions>
        <AppButton @click="openCreate">
          <i class="bi bi-person-plus mr-1"></i> เพิ่มผู้ใช้
        </AppButton>
      </template>
    </PageHeader>

    <p v-if="message" class="mb-3 rounded-lg bg-ok-soft px-3 py-2 text-sm text-ok-strong">
      {{ message }}
    </p>
    <p v-if="actionError" class="mb-3 rounded-lg bg-danger-soft px-3 py-2 text-sm text-danger">
      {{ actionError }}
    </p>

    <AppCard>
      <div v-if="loading" class="py-10 text-center text-sm text-ink-2">กำลังโหลด…</div>

      <p v-else-if="error" class="py-10 text-center text-sm text-danger">{{ error }}</p>

      <div v-else-if="users.length === 0" class="py-10 text-center text-sm text-ink-2">
        ยังไม่มีผู้ใช้
      </div>

      <table v-else class="w-full text-sm">
        <thead>
          <tr class="border-b border-line text-left text-xs font-semibold text-ink-3">
            <th class="py-2 pr-3">ผู้ใช้</th>
            <th class="py-2 pr-3">role</th>
            <th class="py-2 pr-3">สถานะ</th>
            <th class="py-2 text-right">จัดการ</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="u in users" :key="u.id" class="border-b border-line last:border-0">
            <td class="py-3 pr-3">
              <div class="font-medium text-ink-1">{{ u.display_name || u.username }}</div>
              <div class="text-xs text-ink-3">@{{ u.username }}</div>
            </td>
            <td class="py-3 pr-3">
              <span
                class="inline-flex rounded-full border px-2 py-0.5 text-xs font-medium"
                :class="ROLE_BADGE[u.role]"
              >
                {{ ROLE_LABEL[u.role] }}
              </span>
            </td>
            <td class="py-3 pr-3 text-xs text-ink-2">
              {{ u.must_change_password ? 'ต้องเปลี่ยนรหัสผ่าน' : 'ปกติ' }}
            </td>
            <td class="py-3 text-right">
              <AppButton variant="text" size="sm" @click="openEdit(u)">แก้ไข</AppButton>
              <AppButton variant="danger" size="sm" @click="remove(u)">ลบ</AppButton>
            </td>
          </tr>
        </tbody>
      </table>
    </AppCard>

    <!-- modal -->
    <div
      v-if="modalOpen"
      class="fixed inset-0 z-50 flex items-center justify-center bg-ink-1/40 p-4"
      @click.self="closeModal"
    >
      <div class="w-full max-w-sm rounded-2xl border border-line bg-surface p-5 shadow-lg">
        <h3 class="text-base font-bold text-ink-1">
          {{ isEditing ? 'แก้ไขผู้ใช้' : 'เพิ่มผู้ใช้' }}
        </h3>

        <label class="mt-4 block text-xs font-semibold text-ink-2">
          Username
          <input
            v-model="form.username"
            :disabled="isEditing"
            type="text"
            class="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm text-ink-1 disabled:opacity-60"
            autocomplete="off"
          />
        </label>

        <label class="mt-3 block text-xs font-semibold text-ink-2">
          ชื่อที่แสดง
          <input
            v-model="form.display_name"
            type="text"
            class="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm text-ink-1"
          />
        </label>

        <label class="mt-3 block text-xs font-semibold text-ink-2">
          Role
          <select
            v-model="form.role"
            class="mt-1 w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink-1"
          >
            <option value="admin">แอดมิน</option>
            <option value="designer">ดีไซเนอร์</option>
            <option value="staff">เจ้าหน้าที่</option>
          </select>
        </label>

        <label class="mt-3 block text-xs font-semibold text-ink-2">
          {{ isEditing ? 'รหัสผ่านใหม่ (ว่าง = ไม่เปลี่ยน)' : 'รหัสผ่าน' }}
          <input
            v-model="form.password"
            type="password"
            class="mt-1 w-full rounded-lg border border-line px-3 py-2 text-sm text-ink-1"
            autocomplete="new-password"
          />
        </label>

        <p v-if="actionError" class="mt-3 text-sm text-danger">{{ actionError }}</p>

        <div class="mt-5 flex justify-end gap-2">
          <AppButton variant="secondary" @click="closeModal">ยกเลิก</AppButton>
          <AppButton :loading="saving" @click="save">{{ isEditing ? 'บันทึก' : 'สร้าง' }}</AppButton>
        </div>
      </div>
    </div>
  </div>
</template>
