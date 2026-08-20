import React, { useState, useMemo } from 'react';
import { Users } from 'lucide-react';
import { PlayerMetrics } from '../types';

interface PlayerComparisonProps {
  players: PlayerMetrics[];
}

interface MetricDefinition {
  key: string;
  label: string;
  unit: string;
  getValue: (player: PlayerMetrics) => number;
  higherIsBetter: boolean;
}

const METRICS: MetricDefinition[] = [
  {
    key: 'distance',
    label: 'Distancia Total',
    unit: 'km',
    getValue: (p) => p.total_distance_km,
    higherIsBetter: true,
  },
  {
    key: 'max_speed',
    label: 'Velocidad Maxima',
    unit: 'km/h',
    getValue: (p) => p.max_speed_kmh,
    higherIsBetter: true,
  },
  {
    key: 'avg_speed',
    label: 'Velocidad Promedio',
    unit: 'km/h',
    getValue: (p) => p.avg_speed_kmh,
    higherIsBetter: true,
  },
  {
    key: 'sprints',
    label: 'Sprints',
    unit: '',
    getValue: (p) => p.sprint_count,
    higherIsBetter: true,
  },
  {
    key: 'active_time',
    label: 'Tiempo Activo',
    unit: 's',
    getValue: (p) => {
      if (!p.route || p.route.length < 2) return 0;
      return p.route[p.route.length - 1].timestamp - p.route[0].timestamp;
    },
    higherIsBetter: true,
  },
];

export const PlayerComparison: React.FC<PlayerComparisonProps> = ({ players }) => {
  const [playerAId, setPlayerAId] = useState<string>('');
  const [playerBId, setPlayerBId] = useState<string>('');

  const playerA = useMemo(() => players.find((p) => p.player_id === playerAId), [players, playerAId]);
  const playerB = useMemo(() => players.find((p) => p.player_id === playerBId), [players, playerBId]);

  const rankings = useMemo(() => {
    return METRICS.map((metric) => {
      const sorted = [...players].sort((a, b) => {
        const diff = metric.getValue(b) - metric.getValue(a);
        return metric.higherIsBetter ? diff : -diff;
      });
      return { metric, sorted };
    });
  }, [players]);

  if (players.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg p-6 text-center">
        <Users className="w-12 h-12 text-gray-600 mx-auto mb-3" />
        <p className="text-gray-400">No hay datos de jugadores para comparar.</p>
      </div>
    );
  }

  return (
    <div className="bg-gray-800 rounded-lg p-4 space-y-4">
      <h3 className="text-white font-semibold flex items-center gap-2">
        <Users className="w-5 h-5" />
        Comparativa de Jugadores
      </h3>

      {/* Dropdowns */}
      <div className="flex gap-4">
        <div className="flex-1">
          <label className="text-xs text-gray-400 block mb-1">Jugador A</label>
          <select
            value={playerAId}
            onChange={(e) => setPlayerAId(e.target.value)}
            className="w-full bg-gray-700 text-white border border-gray-600 rounded px-3 py-2 text-sm"
            data-testid="player-a-select"
          >
            <option value="">Seleccionar jugador</option>
            {players.map((p) => (
              <option key={p.player_id} value={p.player_id}>
                {p.player_id}
              </option>
            ))}
          </select>
        </div>
        <div className="flex-1">
          <label className="text-xs text-gray-400 block mb-1">Jugador B</label>
          <select
            value={playerBId}
            onChange={(e) => setPlayerBId(e.target.value)}
            className="w-full bg-gray-700 text-white border border-gray-600 rounded px-3 py-2 text-sm"
            data-testid="player-b-select"
          >
            <option value="">Seleccionar jugador</option>
            {players.map((p) => (
              <option key={p.player_id} value={p.player_id}>
                {p.player_id}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Comparison Table */}
      {playerA && playerB && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm" data-testid="comparison-table">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-gray-400 py-2 px-2">Metrica</th>
                <th className="text-center text-gray-400 py-2 px-2">{playerA.player_id}</th>
                <th className="text-center text-gray-400 py-2 px-2">{playerB.player_id}</th>
              </tr>
            </thead>
            <tbody>
              {METRICS.map((metric) => {
                const valA = metric.getValue(playerA);
                const valB = metric.getValue(playerB);
                const aWins = metric.higherIsBetter ? valA > valB : valA < valB;
                const bWins = metric.higherIsBetter ? valB > valA : valB < valA;
                return (
                  <tr key={metric.key} className="border-b border-gray-700/50">
                    <td className="text-gray-300 py-2 px-2">{metric.label}</td>
                    <td className={`text-center py-2 px-2 font-medium ${aWins ? 'text-green-400' : 'text-white'}`}>
                      {valA.toFixed(2)} {metric.unit}
                    </td>
                    <td className={`text-center py-2 px-2 font-medium ${bWins ? 'text-green-400' : 'text-white'}`}>
                      {valB.toFixed(2)} {metric.unit}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Rankings */}
      {players.length > 1 && (
        <div className="space-y-3">
          <h4 className="text-white font-medium text-sm">Ranking por Metrica</h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {rankings.map(({ metric, sorted }) => (
              <div key={metric.key} className="bg-gray-700/50 rounded p-3">
                <p className="text-xs text-gray-400 mb-1">{metric.label}</p>
                <ol className="space-y-0.5">
                  {sorted.map((player, idx) => (
                    <li key={player.player_id} className="text-xs flex justify-between">
                      <span className={idx === 0 ? 'text-green-400 font-medium' : 'text-gray-300'}>
                        {idx + 1}. {player.player_id}
                      </span>
                      <span className="text-gray-400">
                        {metric.getValue(player).toFixed(2)} {metric.unit}
                      </span>
                    </li>
                  ))}
                </ol>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default PlayerComparison;
