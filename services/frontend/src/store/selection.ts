import { create } from 'zustand'

interface SelectionState {
  /** Ids of the currently selected samples. */
  selected: Set<string>
  /** Whether the grid is in selection mode (toggled from the toolbar). */
  selectMode: boolean
  /** Last tile the user acted on — anchor for shift-click range selection. */
  lastClicked: string | null
  toggle: (id: string) => void
  add: (ids: string[]) => void
  clear: () => void
  /** Enter/leave selection mode. Leaving also drops the current selection. */
  setSelectMode: (on: boolean) => void
  setLastClicked: (id: string | null) => void
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selected: new Set<string>(),
  selectMode: false,
  lastClicked: null,
  toggle: (id) =>
    set((s) => {
      const next = new Set(s.selected)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return { selected: next }
    }),
  add: (ids) =>
    set((s) => {
      const next = new Set(s.selected)
      for (const id of ids) next.add(id)
      return { selected: next }
    }),
  clear: () => set({ selected: new Set<string>(), lastClicked: null }),
  setSelectMode: (on) =>
    set(() =>
      on
        ? { selectMode: true }
        : { selectMode: false, selected: new Set<string>(), lastClicked: null },
    ),
  setLastClicked: (id) => set({ lastClicked: id }),
}))
