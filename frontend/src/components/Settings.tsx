import React, { useState } from 'react';
import { X, Save, Eye, EyeOff, Sun, Moon } from 'lucide-react';
import { AIProvider, YoloModel } from '../types';
import { useSettingsStore } from '../stores/settingsStore';
import { switchProvider, updateAIConfig } from '../services/api';

interface SettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

const PROVIDERS = [
  { id: AIProvider.NVIDIA, label: 'NVIDIA Nemotron', description: 'Default - fast inference' },
  { id: AIProvider.OPENAI, label: 'OpenAI GPT', description: 'GPT-4 and variants' },
  { id: AIProvider.CLAUDE, label: 'Anthropic Claude', description: 'Claude models' },
  { id: AIProvider.GEMINI, label: 'Google Gemini', description: 'Gemini models' },
  { id: AIProvider.OLLAMA, label: 'Ollama (Local)', description: 'Local LLM inference' },
];

const YOLO_MODELS = [
  { id: YoloModel.YOLOV8N, label: 'YOLOv8n', description: 'Rapido' },
  { id: YoloModel.YOLOV8S, label: 'YOLOv8s', description: 'Balanceado' },
  { id: YoloModel.YOLOV8M, label: 'YOLOv8m', description: 'Preciso' },
  { id: YoloModel.YOLOV8L, label: 'YOLOv8l', description: 'Maxima precision' },
];

export const Settings: React.FC<SettingsProps> = ({ isOpen, onClose }) => {
  const { activeProvider, apiKeys, theme, yoloModel, enablePose, setProvider, setApiKey, toggleTheme, setYoloModel, setEnablePose } = useSettingsStore();
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});
  const [isSaving, setIsSaving] = useState(false);

  if (!isOpen) return null;

  const handleProviderChange = async (provider: AIProvider) => {
    setProvider(provider);
    try {
      await switchProvider(provider);
    } catch {
      // Store updated locally regardless
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    try {
      await updateAIConfig(apiKeys);
    } catch {
      // Settings saved locally regardless
    } finally {
      setIsSaving(false);
      onClose();
    }
  };

  const toggleKeyVisibility = (provider: string) => {
    setShowKeys((prev) => ({ ...prev, [provider]: !prev[provider] }));
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-gray-800 rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-white">Configuración IA</h2>
          <button onClick={onClose} className="p-1 hover:bg-gray-700 rounded">
            <X className="w-5 h-5 text-gray-400" />
          </button>
        </div>

        <div className="p-4 space-y-6">
          <div>
            <label className="text-sm font-medium text-gray-300 mb-2 block">Theme</label>
            <button
              onClick={toggleTheme}
              className="flex items-center gap-3 px-4 py-2 bg-gray-700 rounded-lg hover:bg-gray-600 transition-colors"
            >
              {theme === 'dark' ? (
                <><Moon className="w-4 h-4 text-rugby-gold" /><span className="text-gray-300 text-sm">Dark Mode</span></>
              ) : (
                <><Sun className="w-4 h-4 text-yellow-400" /><span className="text-gray-300 text-sm">Light Mode</span></>
              )}
            </button>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-300 mb-2 block">Detection Model</label>
            <div className="space-y-2">
              {YOLO_MODELS.map(({ id, label, description }) => (
                <button
                  key={id}
                  onClick={() => setYoloModel(id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-colors ${
                    yoloModel === id ? 'border-rugby-gold bg-rugby-gold/10' : 'border-gray-600 hover:border-gray-400'
                  }`}
                >
                  <div className={`w-3 h-3 rounded-full border-2 ${yoloModel === id ? 'border-rugby-gold bg-rugby-gold' : 'border-gray-500'}`} />
                  <div>
                    <p className="text-sm text-white font-medium">{label}</p>
                    <p className="text-xs text-gray-400">{description}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-300 mb-2 block">Pose Detection (Skeleton)</label>
            <button
              onClick={() => setEnablePose(!enablePose)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-colors ${
                enablePose ? 'border-rugby-gold bg-rugby-gold/10' : 'border-gray-600 hover:border-gray-400'
              }`}
            >
              <div className={`w-10 h-5 rounded-full relative transition-colors ${enablePose ? 'bg-rugby-gold' : 'bg-gray-600'}`}>
                <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${enablePose ? 'translate-x-5' : 'translate-x-0.5'}`} />
              </div>
              <div>
                <p className="text-sm text-white font-medium">{enablePose ? 'Enabled' : 'Disabled'}</p>
                <p className="text-xs text-gray-400">Enables posture detection for better tackle/play analysis</p>
              </div>
            </button>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-300 mb-2 block">AI Provider</label>
            <div className="space-y-2">
              {PROVIDERS.map(({ id, label, description }) => (
                <button
                  key={id}
                  onClick={() => handleProviderChange(id)}
                  className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-colors ${
                    activeProvider === id ? 'border-rugby-gold bg-rugby-gold/10' : 'border-gray-600 hover:border-gray-400'
                  }`}
                >
                  <div className={`w-3 h-3 rounded-full border-2 ${activeProvider === id ? 'border-rugby-gold bg-rugby-gold' : 'border-gray-500'}`} />
                  <div>
                    <p className="text-sm text-white font-medium">{label}</p>
                    <p className="text-xs text-gray-400">{description}</p>
                  </div>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="text-sm font-medium text-gray-300 mb-2 block">API Keys</label>
            <div className="space-y-3">
              {PROVIDERS.filter((p) => p.id !== AIProvider.OLLAMA).map(({ id, label }) => (
                <div key={id}>
                  <label className="text-xs text-gray-400 mb-1 block">{label}</label>
                  <div className="flex gap-2">
                    <input
                      type={showKeys[id] ? 'text' : 'password'}
                      value={apiKeys[id] || ''}
                      onChange={(e) => setApiKey(id, e.target.value)}
                      placeholder={`Enter ${label} API key`}
                      className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-500 focus:outline-none focus:border-rugby-gold"
                    />
                    <button onClick={() => toggleKeyVisibility(id)} className="px-2 hover:bg-gray-600 rounded-lg">
                      {showKeys[id] ? <EyeOff className="w-4 h-4 text-gray-400" /> : <Eye className="w-4 h-4 text-gray-400" />}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="p-4 border-t border-gray-700">
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="w-full py-2 bg-rugby-gold text-white font-medium rounded-lg hover:bg-rugby-gold/80 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            <Save className="w-4 h-4" />
            {isSaving ? 'Guardando...' : 'Guardar Configuración'}
          </button>
        </div>
      </div>
    </div>
  );
};

export default Settings;
