import React, { useState } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Settings as SettingsIcon, Sun, Moon } from 'lucide-react';
import { HomePage } from './pages/HomePage';
import { AnalysisPage } from './pages/AnalysisPage';
import { Settings } from './components/Settings';
import { useSettingsStore } from './stores/settingsStore';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 30000,
    },
  },
});

const AppLayout: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [settingsOpen, setSettingsOpen] = useState(false);
  const { theme, toggleTheme } = useSettingsStore();

  return (
    <div className={`min-h-screen ${theme === 'dark' ? 'bg-rugby-dark text-white' : 'bg-gray-100 text-gray-900'}`}>
      <header className="sticky top-0 z-40 bg-gray-900/95 backdrop-blur border-b border-gray-700">
        <div className="max-w-[1920px] mx-auto px-4 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="w-8 h-8 bg-rugby-gold rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-sm">RA</span>
            </div>
            <span className="text-white font-semibold text-lg hidden sm:block">Rugby Analyzer</span>
          </Link>
          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} mode`}
            >
              {theme === 'dark' ? <Sun className="w-5 h-5 text-gray-300" /> : <Moon className="w-5 h-5 text-gray-300" />}
            </button>
            <button
              onClick={() => setSettingsOpen(true)}
              className="flex items-center gap-2 px-3 py-1.5 bg-rugby-gold/20 hover:bg-rugby-gold/30 border border-rugby-gold/50 rounded-lg transition-colors"
              title="Configuración IA"
            >
              <SettingsIcon className="w-4 h-4 text-rugby-gold" />
              <span className="text-sm font-medium text-rugby-gold hidden sm:inline">Configuración IA</span>
            </button>
          </div>
        </div>
      </header>
      <main className="max-w-[1920px] mx-auto">{children}</main>
      <Settings isOpen={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
};

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppLayout>
          <Routes>
            <Route path="/" element={<HomePage />} />
            <Route path="/analysis/:videoId" element={<AnalysisPage />} />
          </Routes>
        </AppLayout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
