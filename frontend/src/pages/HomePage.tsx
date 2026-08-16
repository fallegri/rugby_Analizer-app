import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Video as VideoIcon, Activity, Zap, Target } from 'lucide-react';
import { VideoUpload } from '../components/VideoUpload';
import { Video } from '../types';

interface RecentAnalysis {
  id: string;
  filename: string;
  date: string;
}

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const [recentAnalyses] = useState<RecentAnalysis[]>(() => {
    try {
      const stored = localStorage.getItem('rugby-recent-analyses');
      return stored ? JSON.parse(stored) : [];
    } catch {
      return [];
    }
  });

  const handleUploadComplete = (video: Video) => {
    const recent: RecentAnalysis = {
      id: video.id,
      filename: video.filename,
      date: new Date().toISOString(),
    };
    const updated = [recent, ...recentAnalyses.slice(0, 9)];
    localStorage.setItem('rugby-recent-analyses', JSON.stringify(updated));
    navigate(`/analysis/${video.id}`);
  };

  const features = [
    { icon: <Target className="w-8 h-8 text-rugby-gold" />, title: 'Player Tracking', description: 'Track individual players or groups with YOLO-powered detection' },
    { icon: <Activity className="w-8 h-8 text-rugby-gold" />, title: 'Performance Analytics', description: 'Distance, speed, sprints, and route analysis with field mapping' },
    { icon: <Zap className="w-8 h-8 text-rugby-gold" />, title: 'AI Game Analysis', description: 'Ask AI about player positioning, tactics, and performance' },
  ];

  return (
    <div className="min-h-screen flex flex-col items-center px-4 py-12">
      <div className="text-center mb-12 max-w-2xl">
        <h1 className="text-5xl font-bold text-white mb-4">Rugby Analyzer</h1>
        <p className="text-xl text-gray-300">
          AI-powered video analysis for rugby. Track players, measure performance, and gain tactical insights.
        </p>
      </div>

      <div className="w-full max-w-xl mb-12">
        <VideoUpload onUploadComplete={handleUploadComplete} />
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 max-w-4xl mb-12">
        {features.map((feature) => (
          <div key={feature.title} className="bg-gray-800/50 border border-gray-700 rounded-xl p-6 text-center">
            <div className="flex justify-center mb-3">{feature.icon}</div>
            <h3 className="text-white font-semibold mb-2">{feature.title}</h3>
            <p className="text-gray-400 text-sm">{feature.description}</p>
          </div>
        ))}
      </div>

      {recentAnalyses.length > 0 && (
        <div className="w-full max-w-xl">
          <h2 className="text-lg font-semibold text-white mb-3">Recent Analyses</h2>
          <div className="space-y-2">
            {recentAnalyses.map((analysis) => (
              <button
                key={analysis.id}
                onClick={() => navigate(`/analysis/${analysis.id}`)}
                className="w-full flex items-center gap-3 px-4 py-3 bg-gray-800 border border-gray-700 rounded-lg hover:border-gray-500 transition-colors text-left"
              >
                <VideoIcon className="w-5 h-5 text-rugby-gold flex-shrink-0" />
                <div className="flex-1 min-w-0">
                  <p className="text-white text-sm truncate">{analysis.filename}</p>
                  <p className="text-xs text-gray-400">{new Date(analysis.date).toLocaleDateString()}</p>
                </div>
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default HomePage;
