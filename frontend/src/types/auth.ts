// Auth types — ตรงกับ backend `models/user_schemas.py::UserOut`
export interface AuthUser {
  id: number
  username: string
  display_name: string | null
  role: string | null // admin / designer / staff
  is_admin: boolean
  permissions: string[]
  must_change_password: boolean // บัญชี seed: บังคับเปลี่ยนรหัสครั้งแรก
}
