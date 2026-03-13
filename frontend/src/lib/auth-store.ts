'use client';

import { create } from 'zustand';
import { persist } from 'zustand/middleware';

import type { User } from '@/lib/types';

type AuthState = {
  token: string | null;
  user: User | null;
  setToken: (token: string | null) => void;
  setUser: (user: User | null) => void;
  logout: () => void;
};

function syncTokenStorage(token: string | null) {
  if (typeof window === 'undefined') {
    return;
  }

  if (token) {
    window.localStorage.setItem('token', token);
  } else {
    window.localStorage.removeItem('token');
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      setToken: (token) => {
        syncTokenStorage(token);
        set({ token });
      },
      setUser: (user) => set({ user }),
      logout: () => {
        syncTokenStorage(null);
        set({ token: null, user: null });
      },
    }),
    {
      name: 'kurisu-auth',
      partialize: (state) => ({
        token: state.token,
        user: state.user,
      }),
    },
  ),
);
