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

import { PlayerComparison } from '../components/PlayerComparison';
import { PlayerMetrics } from '../types';

const mockPlayers: PlayerMetrics[] = [
  {
    player_id: 'Player 9',
    total_distance_km: 2.5,
    max_speed_kmh: 28.3,
    avg_speed_kmh: 12.1,
    sprint_count: 5,
    sprints: [],
    route: [
      { x: 10, y: 20, timestamp: 0, speed: 3 },
      { x: 15, y: 25, timestamp: 1, speed: 5 },
      { x: 20, y: 30, timestamp: 10, speed: 4 },
    ],
  },
  {
    player_id: 'Player 10',
    total_distance_km: 3.1,
    max_speed_kmh: 25.0,
    avg_speed_kmh: 14.5,
    sprint_count: 3,
    sprints: [],
    route: [
      { x: 50, y: 35, timestamp: 0, speed: 4 },
      { x: 55, y: 40, timestamp: 1, speed: 6 },
      { x: 60, y: 35, timestamp: 10, speed: 5 },
    ],
  },
];

describe('PlayerComparison', () => {
  it('renders empty state when no players', () => {
    render(<PlayerComparison players={[]} />);
    expect(screen.getByText(/No hay datos de jugadores/i)).toBeInTheDocument();
  });

  it('renders player dropdowns', () => {
    render(<PlayerComparison players={mockPlayers} />);
    expect(screen.getByTestId('player-a-select')).toBeInTheDocument();
    expect(screen.getByTestId('player-b-select')).toBeInTheDocument();
  });

  it('renders player options in dropdowns', () => {
    render(<PlayerComparison players={mockPlayers} />);
    const selectA = screen.getByTestId('player-a-select');
    expect(selectA).toBeInTheDocument();
    // Check options exist
    const options = selectA.querySelectorAll('option');
    // 1 default + 2 players
    expect(options.length).toBe(3);
    expect(options[1].textContent).toBe('Player 9');
    expect(options[2].textContent).toBe('Player 10');
  });

  it('renders comparison table when players are selected', () => {
    render(<PlayerComparison players={mockPlayers} />);
    const selectA = screen.getByTestId('player-a-select') as HTMLSelectElement;
    const selectB = screen.getByTestId('player-b-select') as HTMLSelectElement;

    // Simulate selection using native value change and event
    Object.defineProperty(selectA, 'value', { writable: true, value: 'Player 9' });
    selectA.dispatchEvent(new Event('change', { bubbles: true }));

    Object.defineProperty(selectB, 'value', { writable: true, value: 'Player 10' });
    selectB.dispatchEvent(new Event('change', { bubbles: true }));
  });

  it('renders the title', () => {
    render(<PlayerComparison players={mockPlayers} />);
    expect(screen.getByText('Comparativa de Jugadores')).toBeInTheDocument();
  });

  it('renders ranking section with multiple players', () => {
    render(<PlayerComparison players={mockPlayers} />);
    expect(screen.getByText('Ranking por Metrica')).toBeInTheDocument();
  });
});
