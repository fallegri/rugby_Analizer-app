import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import React from 'react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

// Mock konva and react-konva to avoid canvas dependency
vi.mock('react-konva', () => ({
  Stage: ({ children }: { children: React.ReactNode }) => <div data-testid="konva-stage">{children}</div>,
  Layer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  Rect: () => <div />,
  Circle: () => <div />,
  Text: () => <div />,
  Line: () => <div />,
}));

vi.mock('konva', () => ({}));

import App from '../App';
import { TrackingModeSelector } from '../components/TrackingModeSelector';
import { FieldView } from '../components/FieldView';
import { AnalyticsDashboard } from '../components/AnalyticsDashboard';

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
});

const Wrapper: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <QueryClientProvider client={queryClient}>
    <BrowserRouter>
      {children}
    </BrowserRouter>
  </QueryClientProvider>
);

describe('App', () => {
  it('renders the app with header and home page', () => {
    render(<App />);
    const elements = screen.getAllByText('Rugby Analyzer');
    expect(elements.length).toBeGreaterThanOrEqual(1);
  });

  it('renders the home page by default', () => {
    render(<App />);
    expect(screen.getByText(/AI-powered video analysis/i)).toBeInTheDocument();
  });
});

describe('TrackingModeSelector', () => {
  it('renders all tracking modes', () => {
    render(
      <Wrapper>
        <TrackingModeSelector />
      </Wrapper>
    );
    expect(screen.getByText('Single Player')).toBeInTheDocument();
    expect(screen.getByText('Ball Carrier')).toBeInTheDocument();
    expect(screen.getByText('Ball Only')).toBeInTheDocument();
    expect(screen.getByText('Group Tracking')).toBeInTheDocument();
  });
});

describe('FieldView', () => {
  it('renders without players', () => {
    render(
      <Wrapper>
        <FieldView players={[]} />
      </Wrapper>
    );
    expect(screen.getByText('Field View')).toBeInTheDocument();
  });
});

describe('AnalyticsDashboard', () => {
  it('renders empty state when no players', () => {
    render(
      <Wrapper>
        <AnalyticsDashboard players={[]} />
      </Wrapper>
    );
    expect(screen.getByText(/No analytics data/i)).toBeInTheDocument();
  });

  it('renders player metrics when data is provided', () => {
    const mockPlayers = [
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
        ],
      },
    ];

    render(
      <Wrapper>
        <AnalyticsDashboard players={mockPlayers} />
      </Wrapper>
    );
    expect(screen.getByText('Player 9')).toBeInTheDocument();
    expect(screen.getByText('2.50 km')).toBeInTheDocument();
    expect(screen.getByText('28.3 km/h')).toBeInTheDocument();
  });
});
