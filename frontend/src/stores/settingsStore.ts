import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { AIProvider, YoloModel } from '../types';

interface SettingsState {
  activeProvider: AIProvider;
  apiKeys: Record<string, string>;
  theme: 'light' | 'dark';
  yoloModel: YoloModel;
  enablePose: boolean;
  teamAColor: [number, number, number] | null;
  teamBColor: [number, number, number] | null;
}

interface SettingsActions {
  setProvider: (provider: AIProvider) => void;
  setApiKey: (provider: string, key: string) => void;
  toggleTheme: () => void;
  setYoloModel: (model: YoloModel) => void;
  setEnablePose: (enabled: boolean) => void;
  setTeamAColor: (color: [number, number, number] | null) => void;
  setTeamBColor: (color: [number, number, number] | null) => void;
}

export const useSettingsStore = create<SettingsState & SettingsActions>()(
  persist(
    (set) => ({
      activeProvider: AIProvider.NVIDIA,
      apiKeys: {},
      theme: 'dark',
      yoloModel: YoloModel.YOLOV8S,
      enablePose: false,
      teamAColor: null,
      teamBColor: null,

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

      setEnablePose: (enabled) => set({ enablePose: enabled }),

      setTeamAColor: (color) => set({ teamAColor: color }),

      setTeamBColor: (color) => set({ teamBColor: color }),
    }),
    {
      name: 'rugby-analyzer-settings',
    }
  )
);
