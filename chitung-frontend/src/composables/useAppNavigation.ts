import { inject, type InjectionKey, type Ref } from 'vue'

export type AppPage =
  | 'workbench'
  | 'pending-confirmations'
  | 'hazard-ledger'
  | 'visual-patrol'
  | 'smart-form'
  | 'shanshan-doc'
  | 'yaoyao-structured-input'

export const navigateKey: InjectionKey<(page: AppPage) => void> = Symbol('navigate')
export const confirmationsRefreshKey: InjectionKey<Ref<number>> = Symbol('confirmationsRefresh')

export function useAppNavigation() {
  const navigate = inject(navigateKey)
  const confirmationsRefresh = inject(confirmationsRefreshKey)

  function goTo(page: AppPage) {
    navigate?.(page)
  }

  function goToPendingConfirmations() {
    if (confirmationsRefresh) {
      confirmationsRefresh.value += 1
    }
    navigate?.('pending-confirmations')
  }

  return { goTo, goToPendingConfirmations }
}
