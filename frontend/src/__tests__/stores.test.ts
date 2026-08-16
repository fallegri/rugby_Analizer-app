import { describe, it, expect, beforeEach } from 'vitest';
import { useAnalysisStore } from '../stores/analysisStore';
import { useSettingsStore } from '../stores/settingsStore';
import { TrackingMode, AIProvider, AnalysisStatus, PlayerSelection, Video, VideoStatus } from '../types';

describe('analysisStore', () => {
  beforeEach(() => {
    useAnalysisStore.setState(useAnalysisStore.getInitialState());
  });

  it('should have correct initial state', () => {
    const state = useAnalysisStore.getState();
    expect(state.currentVideo).toBeNull();
    expect(state.trackingMode).toBe(TrackingMode.SINGLE_PLAYER);
    expect(state.selectedPlayers).toEqual([]);
    expect(state.calibration).toBeNull();
    expect(state.processingStatus).toBe(AnalysisStatus.PENDING);
    expect(state.processingProgress).toBe(0);
    expect(state.results).toBeNull();
  });

  it('should set video', () => {
    const video: Video = {
      id: 'test-1',
      filename: 'test.mp4',
      file_path: '/path/test.mp4',
      duration: 120,
      width: 1920,
      height: 1080,
      fps: 30,
      status: VideoStatus.UPLOADED,
      created_at: '2024-01-01',
      updated_at: '2024-01-01',
    };
    useAnalysisStore.getState().setVideo(video);
    expect(useAnalysisStore.getState().currentVideo).toEqual(video);
  });

  it('should set tracking mode and clear players', () => {
    const player: PlayerSelection = { id: 'p1', x: 100, y: 200, width: 50, height: 80, label: 'P1' };
    useAnalysisStore.getState().addPlayer(player);
    expect(useAnalysisStore.getState().selectedPlayers).toHaveLength(1);

    useAnalysisStore.getState().setMode(TrackingMode.GROUP_TRACKING);
    expect(useAnalysisStore.getState().trackingMode).toBe(TrackingMode.GROUP_TRACKING);
    expect(useAnalysisStore.getState().selectedPlayers).toEqual([]);
  });

  it('should add and remove players', () => {
    const player1: PlayerSelection = { id: 'p1', x: 100, y: 200, width: 50, height: 80, label: 'P1' };
    const player2: PlayerSelection = { id: 'p2', x: 300, y: 400, width: 50, height: 80, label: 'P2' };

    useAnalysisStore.getState().addPlayer(player1);
    useAnalysisStore.getState().addPlayer(player2);
    expect(useAnalysisStore.getState().selectedPlayers).toHaveLength(2);

    useAnalysisStore.getState().removePlayer('p1');
    expect(useAnalysisStore.getState().selectedPlayers).toHaveLength(1);
    expect(useAnalysisStore.getState().selectedPlayers[0].id).toBe('p2');
  });

  it('should update processing progress', () => {
    useAnalysisStore.getState().updateProgress(50);
    expect(useAnalysisStore.getState().processingProgress).toBe(50);
  });

  it('should set processing status', () => {
    useAnalysisStore.getState().setProcessingStatus(AnalysisStatus.PROCESSING);
    expect(useAnalysisStore.getState().processingStatus).toBe(AnalysisStatus.PROCESSING);
  });

  it('should reset analysis', () => {
    useAnalysisStore.getState().setMode(TrackingMode.BALL_ONLY);
    useAnalysisStore.getState().updateProgress(75);
    useAnalysisStore.getState().resetAnalysis();

    const state = useAnalysisStore.getState();
    expect(state.trackingMode).toBe(TrackingMode.SINGLE_PLAYER);
    expect(state.processingProgress).toBe(0);
  });
});

describe('settingsStore', () => {
  beforeEach(() => {
    useSettingsStore.setState({
      activeProvider: AIProvider.NVIDIA,
      apiKeys: {},
      theme: 'dark',
    });
  });

  it('should have correct initial state', () => {
    const state = useSettingsStore.getState();
    expect(state.activeProvider).toBe(AIProvider.NVIDIA);
    expect(state.apiKeys).toEqual({});
    expect(state.theme).toBe('dark');
  });

  it('should set provider', () => {
    useSettingsStore.getState().setProvider(AIProvider.OPENAI);
    expect(useSettingsStore.getState().activeProvider).toBe(AIProvider.OPENAI);
  });

  it('should set API key', () => {
    useSettingsStore.getState().setApiKey('NVIDIA', 'test-key-123');
    expect(useSettingsStore.getState().apiKeys['NVIDIA']).toBe('test-key-123');
  });

  it('should toggle theme', () => {
    expect(useSettingsStore.getState().theme).toBe('dark');
    useSettingsStore.getState().toggleTheme();
    expect(useSettingsStore.getState().theme).toBe('light');
    useSettingsStore.getState().toggleTheme();
    expect(useSettingsStore.getState().theme).toBe('dark');
  });

  it('should preserve other API keys when setting new one', () => {
    useSettingsStore.getState().setApiKey('NVIDIA', 'key1');
    useSettingsStore.getState().setApiKey('OPENAI', 'key2');
    expect(useSettingsStore.getState().apiKeys).toEqual({
      NVIDIA: 'key1',
      OPENAI: 'key2',
    });
  });
});
