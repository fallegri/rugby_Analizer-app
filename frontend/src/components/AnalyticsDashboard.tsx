import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';
import { Activity, Gauge, Route, Zap } from 'lucide-react';
import { PlayerMetrics } from '../types';

interface AnalyticsDashboardProps {
  players: PlayerMetrics[];
}

const PLAYER_COLORS = [
  '#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];

export const AnalyticsDashboard: React.FC<AnalyticsDashboardProps> = ({ players }) => {
  if (players.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 text-center">
        <Activity className="w-12 h-12 text-gray-600 mx-auto mb-3" />
        <p className="text-gray-400">No analytics data yet. Process a video to see results.</p>
      </div>
    );
  }

  // Build speed-over-time chart data
  const speedChartData = players[0]?.route?.map((_pt, i) => ({
    time: players[0].route[i].timestamp.toFixed(1),
    ...players.reduce((acc, player) => {
      const point = player.route?.[i];
      return { ...acc, [player.player_id]: point ? +(point.speed * 3.6).toFixed(1) : 0 };
    }, {} as Record<string, number>),
  })) || [];

  // Build distance accumulation data
  const distanceData = players[0]?.route?.map((_pt, i) => {
    const entry: Record<string, number | string> = { index: i };
    players.forEach((player) => {
      let dist = 0;
      for (let j = 1; j <= i && j < (player.route?.length || 0); j++) {
        const prev = player.route[j - 1];
        const curr = player.route[j];
        dist += Math.sqrt(Math.pow(curr.x - prev.x, 2) + Math.pow(curr.y - prev.y, 2));
      }
      entry[player.player_id] = +(dist / 1000).toFixed(3);
    });
    return entry;
  }) || [];

  return (
    <div className="space-y-4">
      {/* Metrics cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
        {players.map((player, idx) => (
          <div key={player.player_id} className="bg-gray-800 rounded-lg p-4 border-l-4" style={{ borderColor: PLAYER_COLORS[idx % PLAYER_COLORS.length] }}>
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-white">{player.player_id}</span>
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: PLAYER_COLORS[idx % PLAYER_COLORS.length] }} />
            </div>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div className="flex items-center gap-1">
                <Route className="w-3 h-3 text-gray-400" />
                <span className="text-gray-400">Distance:</span>
                <span className="text-white font-medium">{player.total_distance_km.toFixed(2)} km</span>
              </div>
              <div className="flex items-center gap-1">
                <Gauge className="w-3 h-3 text-gray-400" />
                <span className="text-gray-400">Max:</span>
                <span className="text-white font-medium">{player.max_speed_kmh.toFixed(1)} km/h</span>
              </div>
              <div className="flex items-center gap-1">
                <Activity className="w-3 h-3 text-gray-400" />
                <span className="text-gray-400">Avg:</span>
                <span className="text-white font-medium">{player.avg_speed_kmh.toFixed(1)} km/h</span>
              </div>
              <div className="flex items-center gap-1">
                <Zap className="w-3 h-3 text-gray-400" />
                <span className="text-gray-400">Sprints:</span>
                <span className="text-white font-medium">{player.sprint_count}</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Speed over time chart */}
      {speedChartData.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h4 className="text-white font-medium mb-3">Speed Over Time (km/h)</h4>
          <ResponsiveContainer width="100%" height={200}>
            <LineChart data={speedChartData.filter((_d, i) => i % 5 === 0)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="time" stroke="#9ca3af" fontSize={10} />
              <YAxis stroke="#9ca3af" fontSize={10} />
              <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: 8 }} />
              {players.map((player, idx) => (
                <Line key={player.player_id} type="monotone" dataKey={player.player_id} stroke={PLAYER_COLORS[idx % PLAYER_COLORS.length]} strokeWidth={2} dot={false} />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Distance accumulation chart */}
      {distanceData.length > 0 && (
        <div className="bg-gray-800 rounded-lg p-4">
          <h4 className="text-white font-medium mb-3">Distance Accumulation (km)</h4>
          <ResponsiveContainer width="100%" height={200}>
            <AreaChart data={distanceData.filter((_d, i) => i % 5 === 0)}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="index" stroke="#9ca3af" fontSize={10} />
              <YAxis stroke="#9ca3af" fontSize={10} />
              <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: 8 }} />
              {players.map((player, idx) => (
                <Area key={player.player_id} type="monotone" dataKey={player.player_id} stroke={PLAYER_COLORS[idx % PLAYER_COLORS.length]} fill={PLAYER_COLORS[idx % PLAYER_COLORS.length]} fillOpacity={0.1} strokeWidth={2} />
              ))}
            </AreaChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
};

export default AnalyticsDashboard;
