import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AIProvider, YoloModel } from '../types';

interface SettingsState {
  activeProvider: AIProvider;
  apiKeys: Record<string, string>;
  theme: 'light' | 'dark';
  yoloModel: YoloModel;
}

interface SettingsActions {
  setProvider: (provider: AIProvider) => void;
  setApiKey: (provider: string, key: string) => void;
  toggleTheme: () => void;
  setYoloModel: (model: YoloModel) => void;
}

export const useSettingsStore = create<SettingsState & SettingsActions>()(
  persist(
    (set) => ({
      activeProvider: AIProvider.NVIDIA,
      apiKeys: {},
      theme: 'dark',
      yoloModel: YoloModel.YOLOV8S,

      setProvider: (provider) => set({ activeProvider: provider }),

      setApiKey: (provider, key) =>
        set((state) => ({
          apiKeys: { ...state.apiKeys, [provider]: key },
        })),

      toggleTheme: () =>
        set((state) => ({
          theme: state.theme === 'dark' ? 'light' : 'dark',
        })),

      setYoloModel: (model) => set({ yoloModel: model }),
    }),
    {
      name: 'rugby-analyzer-settings',
    }
  )
);
