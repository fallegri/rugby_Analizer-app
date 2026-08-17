import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { PlayType, DetectedPlay } from '../types';

// Mock the store
const mockStore = {
  detectedPlays: [] as DetectedPlay[],
  isDetectingPlays: false,
  sessionId: 'test-session-123',
  setDetectedPlays: vi.fn(),
  setIsDetectingPlays: vi.fn(),
};

vi.mock('../stores/analysisStore', () => ({
  useAnalysisStore: () => mockStore,
}));

vi.mock('../services/api', () => ({
  detectPlays: vi.fn().mockResolvedValue([]),
}));

import { PlaysTimeline } from '../components/PlaysTimeline';

describe('PlaysTimeline', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockStore.detectedPlays = [];
    mockStore.isDetectingPlays = false;
    mockStore.sessionId = 'test-session-123';
  });

  it('renders empty state when no plays detected', () => {
    render(<PlaysTimeline />);
    expect(screen.getByTestId('empty-state')).toBeInTheDocument();
    expect(screen.getByText('No plays detected yet')).toBeInTheDocument();
  });

  it('renders the Detectar Jugadas button', () => {
    render(<PlaysTimeline />);
    expect(screen.getByText('Detectar Jugadas')).toBeInTheDocument();
  });

  it('renders plays when detectedPlays has items', () => {
    mockStore.detectedPlays = [
      {
        play_type: PlayType.TACKLE,
        start_time: 10,
        end_time: 15,
        confidence: 0.85,
        players_involved: ['Player 1', 'Player 7'],
        position: { x: 30, y: 40 },
        description: 'Hard tackle near the ruck',
        ai_explanation: 'Two players converged at high speed indicating a tackle.',
      },
      {
        play_type: PlayType.TRY,
        start_time: 120,
        end_time: 125,
        confidence: 0.95,
        players_involved: ['Player 11'],
        position: { x: 98, y: 35 },
        description: 'Try scored on the right wing',
        ai_explanation: null,
      },
    ];

    render(<PlaysTimeline />);

    expect(screen.getByText('Tackle')).toBeInTheDocument();
    expect(screen.getByText('Try')).toBeInTheDocument();
    expect(screen.getByText('Hard tackle near the ruck')).toBeInTheDocument();
    expect(screen.getByText('Try scored on the right wing')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
    expect(screen.getByText('95%')).toBeInTheDocument();
    expect(screen.getByText('Player 1')).toBeInTheDocument();
    expect(screen.getByText('Player 7')).toBeInTheDocument();
    expect(screen.getByText('Player 11')).toBeInTheDocument();
  });

  it('shows AI explanation when a play card is clicked', () => {
    mockStore.detectedPlays = [
      {
        play_type: PlayType.SCRUM,
        start_time: 45,
        end_time: 60,
        confidence: 0.9,
        players_involved: ['Player 1', 'Player 2'],
        position: { x: 50, y: 34 },
        description: 'Scrum formation detected',
        ai_explanation: 'Eight players formed a tight cluster with low movement speed.',
      },
    ];

    render(<PlaysTimeline />);

    // AI explanation should not be visible initially
    expect(screen.queryByTestId('ai-explanation')).not.toBeInTheDocument();

    // Click the play card to expand it
    const playCard = screen.getByTestId('play-card');
    fireEvent.click(playCard);

    // AI explanation should now be visible
    expect(screen.getByTestId('ai-explanation')).toBeInTheDocument();
    expect(screen.getByText('Eight players formed a tight cluster with low movement speed.')).toBeInTheDocument();
  });

  it('displays time range formatted as mm:ss', () => {
    mockStore.detectedPlays = [
      {
        play_type: PlayType.RUCK,
        start_time: 125,
        end_time: 130,
        confidence: 0.75,
        players_involved: [],
        position: { x: 40, y: 30 },
        description: 'Ruck formed',
        ai_explanation: null,
      },
    ];

    render(<PlaysTimeline />);
    expect(screen.getByText('02:05 - 02:10')).toBeInTheDocument();
  });
});
