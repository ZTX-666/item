export {}

declare global {
  interface ChitungDesktopRuntime {
    platform: string
    version: string
    centerUrl: string
    logDir: string
  }

  interface Window {
    chitungDesktop?: {
      getRuntime: () => Promise<ChitungDesktopRuntime>
      openPath: (targetPath: string) => Promise<{ ok: boolean; error?: string }>
      showInFolder: (targetPath: string) => Promise<{ ok: boolean; error?: string }>
      restartServices: () => Promise<{ ok: boolean; error?: string; logDir?: string }>
    }
  }
}
