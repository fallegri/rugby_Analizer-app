import React, { useState, useRef, useEffect } from 'react';
import { Send, Bot, User, Loader2 } from 'lucide-react';
import { analyzeWithAI } from '../services/api';
import { useSettingsStore } from '../stores/settingsStore';
import { useAnalysisStore } from '../stores/analysisStore';
import { AIProvider, ChatMessage } from '../types';

export const AIChat: React.FC = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { activeProvider } = useSettingsStore();
  const { results, currentVideo } = useAnalysisStore();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const buildContext = (): string => {
    const parts: string[] = [];
    if (currentVideo) {
      parts.push(`Video: ${currentVideo.filename}, duration: ${currentVideo.duration}s`);
    }
    if (results) {
      parts.push(`Analysis results: ${results.players.length} players tracked`);
      results.players.forEach((p) => {
        parts.push(
          `Player ${p.player_id}: distance=${p.total_distance_km.toFixed(2)}km, max_speed=${p.max_speed_kmh.toFixed(1)}km/h, avg_speed=${p.avg_speed_kmh.toFixed(1)}km/h, sprints=${p.sprint_count}`
        );
      });
    }
    return parts.join('\n');
  };

  const handleSend = async () => {
    if (!input.trim()) return;

    const userMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: input.trim(),
      timestamp: Date.now(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      const context = buildContext();
      const response = await analyzeWithAI(userMessage.content, context);

      const assistantMessage: ChatMessage = {
        id: `msg-${Date.now()}-reply`,
        role: 'assistant',
        content: response.response,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch {
      const errorMessage: ChatMessage = {
        id: `msg-${Date.now()}-error`,
        role: 'assistant',
        content: 'Sorry, I encountered an error processing your request. Please try again.',
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const providerLabel = (p: AIProvider): string => {
    const labels: Record<AIProvider, string> = {
      [AIProvider.NVIDIA]: 'NVIDIA Nemotron',
      [AIProvider.OPENAI]: 'OpenAI GPT',
      [AIProvider.CLAUDE]: 'Anthropic Claude',
      [AIProvider.GEMINI]: 'Google Gemini',
      [AIProvider.OLLAMA]: 'Ollama (Local)',
    };
    return labels[p];
  };

  return (
    <div className="flex flex-col h-full bg-gray-800 rounded-lg overflow-hidden">
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
        <div className="flex items-center gap-2">
          <Bot className="w-5 h-5 text-rugby-gold" />
          <span className="text-white font-medium text-sm">AI Analysis Chat</span>
        </div>
        <span className="text-xs text-gray-400 bg-gray-700 px-2 py-1 rounded">
          {providerLabel(activeProvider)}
        </span>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4 min-h-0">
        {messages.length === 0 && (
          <div className="text-center py-8">
            <Bot className="w-10 h-10 text-gray-600 mx-auto mb-2" />
            <p className="text-gray-400 text-sm">Ask questions about the analysis.</p>
            <p className="text-gray-500 text-xs mt-1">&quot;Analyze player 9 positioning&quot; or &quot;What was the top speed?&quot;</p>
          </div>
        )}
        {messages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : ''}`}>
            {msg.role === 'assistant' && (
              <div className="flex-shrink-0 w-7 h-7 bg-rugby-gold/20 rounded-full flex items-center justify-center">
                <Bot className="w-4 h-4 text-rugby-gold" />
              </div>
            )}
            <div className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${msg.role === 'user' ? 'bg-rugby-gold/20 text-white' : 'bg-gray-700 text-gray-200'}`}>
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
            {msg.role === 'user' && (
              <div className="flex-shrink-0 w-7 h-7 bg-gray-600 rounded-full flex items-center justify-center">
                <User className="w-4 h-4 text-gray-300" />
              </div>
            )}
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-3">
            <div className="w-7 h-7 bg-rugby-gold/20 rounded-full flex items-center justify-center">
              <Bot className="w-4 h-4 text-rugby-gold" />
            </div>
            <div className="bg-gray-700 rounded-lg px-3 py-2">
              <Loader2 className="w-4 h-4 text-gray-400 animate-spin" />
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="p-3 border-t border-gray-700">
        <div className="flex gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyPress}
            placeholder="Ask about the analysis..."
            className="flex-1 bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-sm text-white placeholder-gray-400 focus:outline-none focus:border-rugby-gold"
            disabled={isLoading}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !input.trim()}
            className="px-3 py-2 bg-rugby-gold text-white rounded-lg hover:bg-rugby-gold/80 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>
  );
};

export default AIChat;
