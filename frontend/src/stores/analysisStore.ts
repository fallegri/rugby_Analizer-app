import { create } from 'zustand';
import {
  Video,
  TrackingMode,
  PlayerSelection,
  FieldCalibration,
  AnalysisStatus,
  TrackingResult,
} from '../types';

interface AnalysisState {
  currentVideo: Video | null;
  trackingMode: TrackingMode;
  selectedPlayers: PlayerSelection[];
  calibration: FieldCalibration | null;
  processingStatus: AnalysisStatus;
  processingProgress: number;
  results: TrackingResult | null;
  sessionId: string | null;
}

interface AnalysisActions {
  setVideo: (video: Video | null) => void;
  setMode: (mode: TrackingMode) => void;
  addPlayer: (player: PlayerSelection) => void;
  removePlayer: (playerId: string) => void;
  setCalibration: (calibration: FieldCalibration | null) => void;
  updateProgress: (progress: number) => void;
  setProcessingStatus: (status: AnalysisStatus) => void;
  setResults: (results: TrackingResult | null) => void;
  setSessionId: (id: string | null) => void;
  resetAnalysis: () => void;
}

const initialState: AnalysisState = {
  currentVideo: null,
  trackingMode: TrackingMode.SINGLE_PLAYER,
  selectedPlayers: [],
  calibration: null,
  processingStatus: AnalysisStatus.PENDING,
  processingProgress: 0,
  results: null,
  sessionId: null,
};

export const useAnalysisStore = create<AnalysisState & AnalysisActions>()((set) => ({
  ...initialState,

  setVideo: (video) => set({ currentVideo: video }),

  setMode: (mode) => set({ trackingMode: mode, selectedPlayers: [] }),

  addPlayer: (player) =>
    set((state) => ({
      selectedPlayers: [...state.selectedPlayers, player],
    })),

  removePlayer: (playerId) =>
    set((state) => ({
      selectedPlayers: state.selectedPlayers.filter((p) => p.id !== playerId),
    })),

  setCalibration: (calibration) => set({ calibration }),

  updateProgress: (progress) => set({ processingProgress: progress }),

  setProcessingStatus: (status) => set({ processingStatus: status }),

  setResults: (results) => set({ results }),

  setSessionId: (id) => set({ sessionId: id }),

  resetAnalysis: () => set(initialState),
}));
