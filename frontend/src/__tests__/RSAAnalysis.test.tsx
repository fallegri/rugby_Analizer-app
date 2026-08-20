import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';

// Mock recharts to avoid rendering issues in test environment
vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  BarChart: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  CartesianGrid: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
}));

import { RSAAnalysis } from '../components/RSAAnalysis';
import { PlayerMetrics } from '../types';

const mockPlayersWithSprints: PlayerMetrics[] = [
  {
    player_id: 'Player 9',
    total_distance_km: 2.5,
    max_speed_kmh: 28.3,
    avg_speed_kmh: 12.1,
    sprint_count: 3,
    sprints: [
      { start_time: 0, end_time: 2, max_speed: 28.0, distance: 15 },
      { start_time: 10, end_time: 12, max_speed: 26.0, distance: 14 },
      { start_time: 20, end_time: 22, max_speed: 24.0, distance: 13 },
    ],
    route: [
      { x: 10, y: 20, timestamp: 0, speed: 3 },
      { x: 15, y: 25, timestamp: 1, speed: 5 },
    ],
  },
  {
    player_id: 'Player 10',
    total_distance_km: 3.1,
    max_speed_kmh: 25.0,
    avg_speed_kmh: 14.5,
    sprint_count: 1,
    sprints: [
      { start_time: 5, end_time: 7, max_speed: 25.0, distance: 12 },
    ],
    route: [
      { x: 50, y: 35, timestamp: 0, speed: 4 },
      { x: 55, y: 40, timestamp: 1, speed: 6 },
    ],
  },
];

const mockPlayersNoSprints: PlayerMetrics[] = [
  {
    player_id: 'Player 9',
    total_distance_km: 2.5,
    max_speed_kmh: 28.3,
    avg_speed_kmh: 12.1,
    sprint_count: 0,
    sprints: [],
    route: [
      { x: 10, y: 20, timestamp: 0, speed: 3 },
    ],
  },
];

describe('RSAAnalysis', () => {
  it('renders empty state when no players', () => {
    render(<RSAAnalysis players={[]} />);
    expect(screen.getByText(/No hay datos de sprints/i)).toBeInTheDocument();
  });

  it('renders the RSA title', () => {
    render(<RSAAnalysis players={mockPlayersWithSprints} />);
    expect(screen.getByText('RSA - Repeated Sprint Ability')).toBeInTheDocument();
  });

  it('renders player cards with RSA data', () => {
    render(<RSAAnalysis players={mockPlayersWithSprints} />);
    // Player 9 has sprints within 30s window, should show repeated sprint count
    expect(screen.getByTestId('rsa-card-Player 9')).toBeInTheDocument();
    expect(screen.getByTestId('rsa-card-Player 10')).toBeInTheDocument();
  });

  it('displays RSA metrics for player with repeated sprints', () => {
    render(<RSAAnalysis players={mockPlayersWithSprints} />);
    const card = screen.getByTestId('rsa-card-Player 9');
    // Player 9 has 3 sprints within 30s (gaps of 8s and 8s) -> 3 repeated sprints
    expect(card).toHaveTextContent('Sprints Repetidos:');
    expect(card).toHaveTextContent('3');
    expect(card).toHaveTextContent('Recuperacion Prom:');
    expect(card).toHaveTextContent('Degradacion Velocidad:');
  });

  it('shows 0 repeated sprints for player with single sprint', () => {
    render(<RSAAnalysis players={mockPlayersNoSprints} />);
    const card = screen.getByTestId('rsa-card-Player 9');
    expect(card).toHaveTextContent('0');
  });

  it('renders sprint speed chart when player has sprints', () => {
    render(<RSAAnalysis players={mockPlayersWithSprints} />);
    expect(screen.getByText('Velocidad Maxima por Sprint Secuencial')).toBeInTheDocument();
  });
});
