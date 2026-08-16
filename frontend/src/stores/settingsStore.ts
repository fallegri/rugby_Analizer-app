import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AIProvider } from '../types';

interface SettingsState {
  activeProvider: AIProvider;
  apiKeys: Record<string, string>;
  theme: 'light' | 'dark';
}

interface SettingsActions {
  setProvider: (provider: AIProvider) => void;
  setApiKey: (provider: string, key: string) => void;
  toggleTheme: () => void;
}

export const useSettingsStore = create<SettingsState & SettingsActions>()(
  persist(
    (set) => ({
      activeProvider: AIProvider.NVIDIA,
      apiKeys: {},
      theme: 'dark',

      setProvider: (provider) => set({ activeProvider: provider }),

      setApiKey: (provider, key) =>
        set((state) => ({
          apiKeys: { ...state.apiKeys, [provider]: key },
        })),

      toggleTheme: () =>
        set((state) => ({
          theme: state.theme === 'dark' ? 'light' : 'dark',
        })),
    }),
    {
      name: 'rugby-analyzer-settings',
    }
  )
);
