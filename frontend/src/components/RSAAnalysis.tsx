import React, { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import { Zap } from 'lucide-react';
import { PlayerMetrics, SprintSegment, RSAMetrics } from '../types';

interface RSAAnalysisProps {
  players: PlayerMetrics[];
}

const PLAYER_COLORS = [
  '#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];

const WINDOW_SECONDS = 30;

/**
 * Compute RSA metrics from a player's sprint data on the client side.
 */
function computeRSA(sprints: SprintSegment[]): RSAMetrics {
  if (!sprints || sprints.length < 2) {
    return {
      repeated_sprint_count: 0,
      avg_recovery_time_s: 0,
      max_recovery_time_s: 0,
      min_recovery_time_s: 0,
      speed_degradation_percent: 0,
      sprint_clusters: [],
    };
  }

  // Sort sprints by start_time
  const sorted = [...sprints].sort((a, b) => a.start_time - b.start_time);

  // Group consecutive sprints where gap < WINDOW_SECONDS
  const clusters: SprintSegment[][] = [];
  let currentCluster: SprintSegment[] = [sorted[0]];

  for (let i = 1; i < sorted.length; i++) {
    const gap = sorted[i].start_time - sorted[i - 1].end_time;
    if (gap < WINDOW_SECONDS) {
      currentCluster.push(sorted[i]);
    } else {
      clusters.push(currentCluster);
      currentCluster = [sorted[i]];
    }
  }
  clusters.push(currentCluster);

  // Filter clusters with 2+ sprints
  const rsaClusters = clusters.filter((c) => c.length >= 2);

  if (rsaClusters.length === 0) {
    return {
      repeated_sprint_count: 0,
      avg_recovery_time_s: 0,
      max_recovery_time_s: 0,
      min_recovery_time_s: 0,
      speed_degradation_percent: 0,
      sprint_clusters: [],
    };
  }

  const repeatedSprintCount = rsaClusters.reduce((sum, c) => sum + c.length, 0);

  // Compute recovery times
  const recoveryTimes: number[] = [];
  for (const cluster of rsaClusters) {
    for (let i = 1; i < cluster.length; i++) {
      recoveryTimes.push(cluster[i].start_time - cluster[i - 1].end_time);
    }
  }

  const avgRecovery = recoveryTimes.length > 0 ? recoveryTimes.reduce((a, b) => a + b, 0) / recoveryTimes.length : 0;
  const maxRecovery = recoveryTimes.length > 0 ? Math.max(...recoveryTimes) : 0;
  const minRecovery = recoveryTimes.length > 0 ? Math.min(...recoveryTimes) : 0;

  // Compute speed degradation
  const degradations: number[] = [];
  for (const cluster of rsaClusters) {
    const firstSpeed = cluster[0].max_speed;
    const lastSpeed = cluster[cluster.length - 1].max_speed;
    if (firstSpeed > 0) {
      degradations.push(((firstSpeed - lastSpeed) / firstSpeed) * 100);
    }
  }
  const speedDegradation = degradations.length > 0 ? degradations.reduce((a, b) => a + b, 0) / degradations.length : 0;

  return {
    repeated_sprint_count: repeatedSprintCount,
    avg_recovery_time_s: avgRecovery,
    max_recovery_time_s: maxRecovery,
    min_recovery_time_s: minRecovery,
    speed_degradation_percent: speedDegradation,
    sprint_clusters: rsaClusters.map((cluster) => ({
      sprints: cluster,
      window_start: cluster[0].start_time,
      window_end: cluster[cluster.length - 1].end_time,
    })),
  };
}

export const RSAAnalysis: React.FC<RSAAnalysisProps> = ({ players }) => {
  const rsaData = useMemo(() => {
    return players.map((player, idx) => ({
      player,
      color: PLAYER_COLORS[idx % PLAYER_COLORS.length],
      rsa: computeRSA(player.sprints),
    }));
  }, [players]);

  // Build sprint speed chart data per player (for the first player with sprints)
  const sprintSpeedChartData = useMemo(() => {
    const playerWithSprints = players.find((p) => p.sprints && p.sprints.length > 1);
    if (!playerWithSprints) return [];
    return playerWithSprints.sprints.map((sprint, idx) => ({
      sprint: `Sprint ${idx + 1}`,
      max_speed: +sprint.max_speed.toFixed(1),
    }));
  }, [players]);

  if (players.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 text-center">
        <Zap className="w-12 h-12 text-gray-600 mx-auto mb-3" />
        <p className="text-gray-400">No hay datos de sprints para analisis RSA.</p>
      </div>
    );
  }

  const hasAnyRSA = rsaData.some((d) => d.rsa.repeated_sprint_count > 0);

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-4">
      <h3 className="text-white font-semibold flex items-center gap-2">
        <Zap className="w-5 h-5" />
        RSA - Repeated Sprint Ability
      </h3>

      {/* Per-player RSA cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {rsaData.map(({ player, color, rsa }) => (
          <div
            key={player.player_id}
            className="bg-gray-700/50 rounded-lg p-3 border-l-4"
            style={{ borderColor: color }}
            data-testid={`rsa-card-${player.player_id}`}
          >
            <p className="text-white font-medium text-sm mb-2">{player.player_id}</p>
            <div className="grid grid-cols-2 gap-2 text-xs">
              <div>
                <span className="text-gray-400">Sprints Repetidos:</span>
                <span className="text-white ml-1 font-medium">{rsa.repeated_sprint_count}</span>
              </div>
              <div>
                <span className="text-gray-400">Recuperacion Prom:</span>
                <span className="text-white ml-1 font-medium">{rsa.avg_recovery_time_s.toFixed(1)}s</span>
              </div>
              <div>
                <span className="text-gray-400">Recuperacion Min:</span>
                <span className="text-white ml-1 font-medium">{rsa.min_recovery_time_s.toFixed(1)}s</span>
              </div>
              <div>
                <span className="text-gray-400">Recuperacion Max:</span>
                <span className="text-white ml-1 font-medium">{rsa.max_recovery_time_s.toFixed(1)}s</span>
              </div>
              <div className="col-span-2">
                <span className="text-gray-400">Degradacion Velocidad:</span>
                <span className={`ml-1 font-medium ${rsa.speed_degradation_percent > 10 ? 'text-red-400' : 'text-green-400'}`}>
                  {rsa.speed_degradation_percent.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Sprint Speed Chart */}
      {sprintSpeedChartData.length > 0 && (
        <div>
          <h4 className="text-gray-300 text-sm mb-2">Velocidad Maxima por Sprint Secuencial</h4>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={sprintSpeedChartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="sprint" stroke="#9ca3af" fontSize={10} />
              <YAxis stroke="#9ca3af" fontSize={10} unit=" km/h" />
              <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: 8 }} />
              <Bar dataKey="max_speed" name="Vel. Max" fill="#f59e0b" opacity={0.8} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {!hasAnyRSA && players.some((p) => p.sprints && p.sprints.length > 0) && (
        <p className="text-gray-400 text-sm text-center">
          No se detectaron sprints repetidos (gap &lt; 30s entre sprints consecutivos).
        </p>
      )}
    </div>
  );
};

export default RSAAnalysis;
