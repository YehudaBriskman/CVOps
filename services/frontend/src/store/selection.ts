import { create } from 'zustand'

interface SelectionState {
  selected: Set<string>
  toggle: (id: string) => void
  add: (ids: string[]) => void
  clear: () => void
}

export const useSelectionStore = create<SelectionState>((set) => ({
  selected: new Set<string>(),
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
  clear: () => set({ selected: new Set<string>() }),
}))
