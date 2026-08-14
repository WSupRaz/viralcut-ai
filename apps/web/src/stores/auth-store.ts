"use client";

import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { User } from "@/types/api";

interface AuthState {
  token: string | null;
  user: User | null;
  /** False until zustand-persist finishes rehydrating from localStorage.
   *  Without this gate, the dashboard layout's "no token -> redirect to
   *  /sign-in" effect can fire before rehydration completes, logging the
   *  user out on every page reload. */
  hasHydrated: boolean;
  setAuth: (token: string, user: User) => void;
  clearAuth: () => void;
  setHasHydrated: (value: boolean) => void;
}

// Captured from the initializer (which runs before hydration starts) so the
// post-rehydration callback can flip the flag without referencing the store
// const -- referencing `useAuthStore` there is a temporal-dead-zone error
// (the callback fires during create(), before the const is assigned).
let markHydrated: (() => void) | null = null;

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => {
      markHydrated = () => set({ hasHydrated: true });
      return {
        token: null,
        user: null,
        hasHydrated: false,
        setAuth: (token, user) => set({ token, user }),
        clearAuth: () => set({ token: null, user: null }),
        setHasHydrated: (value) => set({ hasHydrated: value }),
      };
    },
    {
      name: "viralcut-auth",
      storage: createJSONStorage(() => localStorage),
      onRehydrateStorage: () => () => {
        // Fires after hydration whether or not anything was stored.
        markHydrated?.();
      },
    }
  )
);
