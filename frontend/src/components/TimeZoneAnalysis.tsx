import React, { useState, useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from 'recharts';
import { Clock } from 'lucide-react';
import { PlayerMetrics } from '../types';

interface TimeZoneAnalysisProps {
  players: PlayerMetrics[];
}

const PLAYER_COLORS = [
  '#ef4444', '#3b82f6', '#10b981', '#f59e0b', '#8b5cf6',
  '#ec4899', '#06b6d4', '#84cc16', '#f97316', '#6366f1',
];

interface SegmentData {
  segment: string;
  segmentIndex: number;
  startTime: number;
  endTime: number;
  [key: string]: string | number; // player metrics
}

export const TimeZoneAnalysis: React.FC<TimeZoneAnalysisProps> = ({ players }) => {
  const [segmentDuration, setSegmentDuration] = useState<number>(5);

  const { chartData, summaryData } = useMemo(() => {
    if (players.length === 0) {
      return { chartData: [] as SegmentData[], summaryData: [] as SegmentData[] };
    }

    // Find overall time range
    let minTime = Infinity;
    let maxTime = -Infinity;
    for (const player of players) {
      if (player.route && player.route.length > 0) {
        const first = player.route[0].timestamp;
        const last = player.route[player.route.length - 1].timestamp;
        if (first < minTime) minTime = first;
        if (last > maxTime) maxTime = last;
      }
    }

    if (minTime === Infinity || maxTime === -Infinity) {
      return { chartData: [] as SegmentData[], summaryData: [] as SegmentData[] };
    }

    const totalDuration = maxTime - minTime;
    const numSegments = Math.max(1, Math.ceil(totalDuration / segmentDuration));
    const data: SegmentData[] = [];

    for (let seg = 0; seg < numSegments; seg++) {
      const segStart = minTime + seg * segmentDuration;
      const segEnd = Math.min(segStart + segmentDuration, maxTime);

      const entry: SegmentData = {
        segment: `${(seg * segmentDuration).toFixed(0)}s-${((seg + 1) * segmentDuration).toFixed(0)}s`,
        segmentIndex: seg,
        startTime: segStart,
        endTime: segEnd,
      };

      for (const player of players) {
        // Filter route points within this segment
        const segPoints = (player.route || []).filter(
          (pt) => pt.timestamp >= segStart && pt.timestamp <= segEnd
        );

        // Compute distance in this segment
        let distance = 0;
        for (let i = 1; i < segPoints.length; i++) {
          const dx = segPoints[i].x - segPoints[i - 1].x;
          const dy = segPoints[i].y - segPoints[i - 1].y;
          distance += Math.sqrt(dx * dx + dy * dy);
        }

        // Compute average speed in this segment
        const avgSpeed =
          segPoints.length > 0
            ? segPoints.reduce((sum, pt) => sum + pt.speed * 3.6, 0) / segPoints.length
            : 0;

        entry[`${player.player_id}_dist`] = +(distance / 1000).toFixed(4);
        entry[`${player.player_id}_speed`] = +avgSpeed.toFixed(1);
      }

      data.push(entry);
    }

    return { chartData: data, summaryData: data };
  }, [players, segmentDuration]);

  if (players.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 text-center">
        <Clock className="w-12 h-12 text-gray-600 mx-auto mb-3" />
        <p className="text-gray-400">No hay datos para analisis por zonas de tiempo.</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-white font-semibold flex items-center gap-2">
          <Clock className="w-5 h-5" />
          Analisis por Zonas de Tiempo
        </h3>
        <div className="flex items-center gap-2">
          <label className="text-xs text-gray-400">Duracion segmento (s):</label>
          <input
            type="number"
            min={1}
            max={300}
            value={segmentDuration}
            onChange={(e) => setSegmentDuration(Math.max(1, parseInt(e.target.value) || 1))}
            className="w-16 bg-gray-700 text-white border border-gray-600 rounded px-2 py-1 text-sm"
            data-testid="segment-duration-input"
          />
        </div>
      </div>

      {/* Bar Chart - Avg Speed per segment */}
      {chartData.length > 0 && (
        <div>
          <h4 className="text-gray-300 text-sm mb-2">Velocidad Promedio por Periodo (km/h)</h4>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
              <XAxis dataKey="segment" stroke="#9ca3af" fontSize={10} />
              <YAxis stroke="#9ca3af" fontSize={10} />
              <Tooltip contentStyle={{ backgroundColor: '#1f2937', border: 'none', borderRadius: 8 }} />
              <Legend />
              {players.map((player, idx) => (
                <Bar
                  key={player.player_id}
                  dataKey={`${player.player_id}_speed`}
                  name={player.player_id}
                  fill={PLAYER_COLORS[idx % PLAYER_COLORS.length]}
                  opacity={0.8}
                />
              ))}
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {/* Summary Table */}
      {summaryData.length > 0 && (
        <div className="overflow-x-auto">
          <h4 className="text-gray-300 text-sm mb-2">Resumen por Segmento</h4>
          <table className="w-full text-xs" data-testid="time-zone-table">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-gray-400 py-2 px-2">Periodo</th>
                {players.map((p) => (
                  <th key={p.player_id} className="text-center text-gray-400 py-2 px-1" colSpan={2}>
                    {p.player_id}
                  </th>
                ))}
              </tr>
              <tr className="border-b border-gray-700/50">
                <th className="text-left text-gray-500 py-1 px-2"></th>
                {players.map((p) => (
                  <React.Fragment key={p.player_id}>
                    <th className="text-center text-gray-500 py-1 px-1">Dist(km)</th>
                    <th className="text-center text-gray-500 py-1 px-1">Vel(km/h)</th>
                  </React.Fragment>
                ))}
              </tr>
            </thead>
            <tbody>
              {summaryData.map((row) => (
                <tr key={row.segment} className="border-b border-gray-700/30">
                  <td className="text-gray-300 py-1 px-2">{row.segment}</td>
                  {players.map((p) => (
                    <React.Fragment key={p.player_id}>
                      <td className="text-center text-white py-1 px-1">
                        {(row[`${p.player_id}_dist`] as number)?.toFixed(4) || '0'}
                      </td>
                      <td className="text-center text-white py-1 px-1">
                        {(row[`${p.player_id}_speed`] as number)?.toFixed(1) || '0'}
                      </td>
                    </React.Fragment>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

export default TimeZoneAnalysis;
