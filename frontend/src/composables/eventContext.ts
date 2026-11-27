import { inject, provide, type InjectionKey, type Ref } from 'vue'
import type { EventOut } from '@/types/domain'

export interface EventContext {
  event: Ref<EventOut | null>
  reload: () => Promise<void>
}

export const EVENT_CONTEXT: InjectionKey<EventContext> = Symbol('event-context')

export function provideEventContext(ctx: EventContext): void {
  provide(EVENT_CONTEXT, ctx)
}

export function useEventContext(): EventContext | null {
  return inject(EVENT_CONTEXT, null)
}
