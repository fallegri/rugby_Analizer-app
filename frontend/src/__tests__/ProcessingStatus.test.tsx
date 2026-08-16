import { describe, it, expect, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ProcessingStatus } from '../components/ProcessingStatus';
import { useAnalysisStore } from '../stores/analysisStore';

describe('ProcessingStatus', () => {
  beforeEach(() => {
    useAnalysisStore.setState(useAnalysisStore.getInitialState());
  });

  it('renders with initial state showing 0% progress', () => {
    render(<ProcessingStatus />);
    expect(screen.getByTestId('processing-status')).toBeInTheDocument();
    expect(screen.getByTestId('progress-percentage')).toHaveTextContent('0.0%');
    expect(screen.getByTestId('frame-counter')).toHaveTextContent('0/0');
  });

  it('renders progress with stage and frame info', () => {
    useAnalysisStore.setState({
      processingProgress: 45.5,
      processingDetails: {
        stage: 'Detectando jugadores',
        currentFrame: 150,
        totalFrames: 330,
        fps: 12.5,
        elapsedTime: 12,
        eta: 14.4,
        lastUpdateTimestamp: Date.now(),
      },
    });

    render(<ProcessingStatus />);
    expect(screen.getByTestId('progress-percentage')).toHaveTextContent('45.5%');
    expect(screen.getByTestId('frame-counter')).toHaveTextContent('150/330');
    expect(screen.getByTestId('fps-display')).toHaveTextContent('12.5');
    expect(screen.getAllByText('Detectando jugadores').length).toBeGreaterThanOrEqual(1);
  });

  it('renders component with onRetry prop', () => {
    const mockRetry = () => {};
    useAnalysisStore.setState({
      processingProgress: 25,
      processingDetails: {
        stage: 'Tracking',
        currentFrame: 80,
        totalFrames: 330,
        fps: 0,
        elapsedTime: 35,
        eta: 0,
        lastUpdateTimestamp: Date.now() - 31000,
      },
    });

    render(<ProcessingStatus onRetry={mockRetry} />);
    expect(screen.getByTestId('processing-status')).toBeInTheDocument();
  });

  it('displays elapsed time and ETA correctly', () => {
    useAnalysisStore.setState({
      processingProgress: 60,
      processingDetails: {
        stage: 'Calibrando cancha',
        currentFrame: 200,
        totalFrames: 330,
        fps: 15.0,
        elapsedTime: 65,
        eta: 43,
        lastUpdateTimestamp: Date.now(),
      },
    });

    render(<ProcessingStatus />);
    expect(screen.getByTestId('time-display')).toHaveTextContent('1m 5s');
    expect(screen.getByTestId('time-display')).toHaveTextContent('43s');
  });

  it('displays fps information', () => {
    useAnalysisStore.setState({
      processingProgress: 30,
      processingDetails: {
        stage: 'Detectando jugadores',
        currentFrame: 100,
        totalFrames: 330,
        fps: 22.3,
        elapsedTime: 4.5,
        eta: 10.3,
        lastUpdateTimestamp: Date.now(),
      },
    });

    render(<ProcessingStatus />);
    expect(screen.getByTestId('fps-display')).toHaveTextContent('22.3');
  });
});
