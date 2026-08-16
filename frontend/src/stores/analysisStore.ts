import { create } from 'zustand';
import {
  Video,
  TrackingMode,
  PlayerSelection,
  FieldCalibration,
  AnalysisStatus,
  TrackingResult,
} from '../types';

export interface ProcessingDetails {
  stage: string;
  currentFrame: number;
  totalFrames: number;
  fps: number;
  elapsedTime: number;
  eta: number;
  lastUpdateTimestamp: number;
}

interface AnalysisState {
  currentVideo: Video | null;
  trackingMode: TrackingMode;
  selectedPlayers: PlayerSelection[];
  calibration: FieldCalibration | null;
  processingStatus: AnalysisStatus;
  processingProgress: number;
  processingDetails: ProcessingDetails;
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
  updateProcessingDetails: (details: Partial<ProcessingDetails>) => void;
  setProcessingStatus: (status: AnalysisStatus) => void;
  setResults: (results: TrackingResult | null) => void;
  setSessionId: (id: string | null) => void;
  resetAnalysis: () => void;
}

const initialProcessingDetails: ProcessingDetails = {
  stage: '',
  currentFrame: 0,
  totalFrames: 0,
  fps: 0,
  elapsedTime: 0,
  eta: 0,
  lastUpdateTimestamp: 0,
};

const initialState: AnalysisState = {
  currentVideo: null,
  trackingMode: TrackingMode.SINGLE_PLAYER,
  selectedPlayers: [],
  calibration: null,
  processingStatus: AnalysisStatus.PENDING,
  processingProgress: 0,
  processingDetails: initialProcessingDetails,
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

  updateProcessingDetails: (details) =>
    set((state) => ({
      processingDetails: {
        ...state.processingDetails,
        ...details,
        lastUpdateTimestamp: Date.now(),
      },
    })),

  setProcessingStatus: (status) => set({ processingStatus: status }),

  setResults: (results) => set({ results }),

  setSessionId: (id) => set({ sessionId: id }),

  resetAnalysis: () => set(initialState),
}));
