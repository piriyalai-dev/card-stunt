import api from './api'
import type {
  ColorCreate,
  ColorOut,
  ColorUpdate,
  PaletteCreate,
  PaletteOut,
} from '@/types/domain'

export async function listPalettes(eventId: number): Promise<PaletteOut[]> {
  return (await api.get(`/api/v1/events/${eventId}/palettes`)) as unknown as PaletteOut[]
}

export async function getPalette(paletteId: number): Promise<PaletteOut> {
  return (await api.get(`/api/v1/palettes/${paletteId}`)) as unknown as PaletteOut
}

export async function createPalette(eventId: number, body: PaletteCreate): Promise<PaletteOut> {
  return (await api.post(`/api/v1/events/${eventId}/palettes`, body)) as unknown as PaletteOut
}

export async function updatePalette(
  paletteId: number,
  body: { name?: string; description?: string | null; is_default?: boolean },
): Promise<PaletteOut> {
  return (await api.patch(`/api/v1/palettes/${paletteId}`, body)) as unknown as PaletteOut
}

export async function deletePalette(paletteId: number): Promise<void> {
  await api.delete(`/api/v1/palettes/${paletteId}`)
}

export async function addColor(paletteId: number, body: ColorCreate): Promise<ColorOut> {
  return (await api.post(
    `/api/v1/palettes/${paletteId}/colors`,
    body,
  )) as unknown as ColorOut
}

export async function updateColor(
  paletteId: number,
  colorId: number,
  body: ColorUpdate,
): Promise<ColorOut> {
  return (await api.patch(
    `/api/v1/palettes/${paletteId}/colors/${colorId}`,
    body,
  )) as unknown as ColorOut
}

/** ⚠️ DELETE ที่มี body — ต้องส่งผ่าน `{ data }` ของ axios */
export async function deleteColor(
  paletteId: number,
  colorId: number,
  replacementColorId: number | null = null,
): Promise<void> {
  await api.delete(`/api/v1/palettes/${paletteId}/colors/${colorId}`, {
    data: { replacement_color_id: replacementColorId },
  })
}
