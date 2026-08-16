import React from 'react';
import { User, Users, Circle, Target } from 'lucide-react';
import { TrackingMode } from '../types';
import { useAnalysisStore } from '../stores/analysisStore';

interface ModeOption {
  mode: TrackingMode;
  label: string;
  description: string;
  icon: React.ReactNode;
}

const MODE_OPTIONS: ModeOption[] = [
  {
    mode: TrackingMode.SINGLE_PLAYER,
    label: 'Single Player',
    description: 'Track a specific player throughout the video',
    icon: <User className="w-6 h-6" />,
  },
  {
    mode: TrackingMode.BALL_CARRIER,
    label: 'Ball Carrier',
    description: 'Automatically follow the player carrying the ball',
    icon: <Target className="w-6 h-6" />,
  },
  {
    mode: TrackingMode.BALL_ONLY,
    label: 'Ball Only',
    description: 'Track the rugby ball position throughout play',
    icon: <Circle className="w-6 h-6" />,
  },
  {
    mode: TrackingMode.GROUP_TRACKING,
    label: 'Group Tracking',
    description: 'Track multiple players simultaneously',
    icon: <Users className="w-6 h-6" />,
  },
];

export const TrackingModeSelector: React.FC = () => {
  const { trackingMode, setMode } = useAnalysisStore();

  return (
    <div className="flex gap-2 flex-wrap">
      {MODE_OPTIONS.map(({ mode, label, description, icon }) => (
        <button
          key={mode}
          onClick={() => setMode(mode)}
          className={`
            flex items-center gap-3 px-4 py-3 rounded-lg border transition-all text-left
            ${
              trackingMode === mode
                ? 'border-rugby-gold bg-rugby-gold/10 text-white'
                : 'border-gray-600 bg-gray-800 text-gray-300 hover:border-gray-400'
            }
          `}
        >
          <div className={trackingMode === mode ? 'text-rugby-gold' : 'text-gray-400'}>
            {icon}
          </div>
          <div>
            <p className="font-medium text-sm">{label}</p>
            <p className="text-xs text-gray-400">{description}</p>
          </div>
        </button>
      ))}
    </div>
  );
};

export default TrackingModeSelector;
