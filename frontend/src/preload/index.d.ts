import { ElectronAPI } from '@electron-toolkit/preload'

/** API for controlling the native window from the renderer process */
interface WindowControls {
  /** Minimize the application window */
  minimize: () => void
  /** Toggle maximize/restore of the application window */
  maximize: () => void
  /** Close the application window */
  close: () => void
}

declare global {
  interface Window {
    electron: ElectronAPI & { windowControls: WindowControls }
  }
}
