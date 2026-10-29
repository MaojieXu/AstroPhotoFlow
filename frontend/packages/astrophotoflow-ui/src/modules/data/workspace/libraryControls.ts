import type { Component, InjectionKey } from 'vue'

export type LibraryControls = { button: Component; input: Component; formItem: Component; dialog: Component; multiSelect: Component; select: Component; textarea: Component; checkbox?: Component; menu?: Component; tabs?: Component; tabsList?: Component; tabsTrigger?: Component; canvasSource?: Component; mediaViewer?: Component }
export const libraryControlsKey: InjectionKey<LibraryControls | undefined> = Symbol('libraryControls')
export type ImportNotice = { taskId: string; category: 'content' | 'preview'; kind: 'success' | 'warning' | 'error'; title: string; description: string }

export type LibraryMenuItem = { label: string; disabled?: boolean } & (
  | { command: () => unknown; radioGroup?: never }
  | { command?: never; radioGroup: { value: string; options: Array<{ value: string; label: string; command: () => unknown }> } }
)
