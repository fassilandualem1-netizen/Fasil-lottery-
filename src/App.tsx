import React, { useState, useEffect } from 'react';
import { TelegramProvider } from './context/TelegramContext';
import { AuthProvider, useAuth } from './context/AuthContext';
import { useTelegram } from './hooks/useTelegram';
import { HomeLobby } from './pages/HomeLobby';
import { GamesPage } from './pages/Games';
import { WalletPage } from './pages/Wallet';
import { SupportPage } from './pages/Support';
import { BottomNav, NavTab } from './components/layout/BottomNav';
import { AuthModal } from './components/auth/AuthModal';
import { TransactionHistory } from './components/wallet/TransactionHistory';
import { AdminDashboard } from './components/admin/AdminDashboard';
import { LoopGameType } from './types';

// Import All 7 Interactive Games
import { AviatorGame } from './games/AviatorGame';
import { KenoGame } from './games/KenoGame';
import { VirtualSportsGame } from './games/VirtualSportsGame';
import { MinesGame } from './games/MinesGame';
import { CoinflipGame } from './games/CoinflipGame';
import { DiceGame } from './games/DiceGame';
import { ColorWheelGame } from './games/ColorWheelGame';

import { ArrowLeft } from 'lucide-react';

function DashboardView() {
  const { isAdmin: isTgAdmin } = useTelegram();
  const { isAdmin: isAuthAdmin } = useAuth();
  const isAdmin = isTgAdmin || isAuthAdmin;

  const [activeTab, setActiveTab] = useState<NavTab>('home');
  const [selectedGame, setSelectedGame] = useState<LoopGameType | null>(null);

  // Role-Based Initialization: Default to admin tab if Admin ID 8488592165
  useEffect(() => {
    if (isAdmin) {
      setActiveTab('admin');
    }
  }, [isAdmin]);

  // Auth Modal state
  const [authModalOpen, setAuthModalOpen] = useState(false);
  const [authModalTab, setAuthModalTab] = useState<'login' | 'register'>('login');

  const handleOpenAuth = (tab: 'login' | 'register') => {
    setAuthModalTab(tab);
    setAuthModalOpen(true);
  };

  const handleSelectGame = (gameId: LoopGameType) => {
    setSelectedGame(gameId);
  };

  const handleOpenDepositFromHome = () => {
    setActiveTab('wallet');
    setSelectedGame(null);
  };

  const handleTabChange = (tab: NavTab) => {
    if (tab === 'admin' && !isAdmin) {
      setActiveTab('home');
      return;
    }
    setActiveTab(tab);
    setSelectedGame(null);
  };

  const renderActiveGame = () => {
    switch (selectedGame) {
      case 'aviator':
        return <AviatorGame onClose={() => setSelectedGame(null)} />;
      case 'keno':
        return <KenoGame />;
      case 'virtual_sport':
        return <VirtualSportsGame />;
      case 'mines':
        return <MinesGame />;
      case 'coinflip':
        return <CoinflipGame />;
      case 'dice':
        return <DiceGame />;
      case 'color_wheel':
        return <ColorWheelGame />;
      default:
        return <AviatorGame onClose={() => setSelectedGame(null)} />;
    }
  };

  return (
    <div className="w-full max-w-[100vw] min-h-screen bg-slate-950 text-slate-100 flex flex-col relative select-none overflow-x-hidden">
      {/* Active Game View Overlay */}
      {selectedGame ? (
        <div className="w-full max-w-md mx-auto min-h-screen flex flex-col p-3 space-y-3 pb-24">
          <div className="flex items-center justify-between border-b border-[#232d48] pb-2">
            <button
              onClick={() => setSelectedGame(null)}
              className="px-3 py-1.5 bg-[#151c2e] border border-[#232d48] hover:border-amber-400 text-amber-400 rounded-xl text-xs font-bold flex items-center space-x-1 transition-all"
            >
              <ArrowLeft className="w-4 h-4" />
              <span>Back to Lobby</span>
            </button>
            <div className="text-right">
              <span className="text-xs font-black uppercase text-amber-400 tracking-wider">
                {selectedGame.replace('_', ' ')}
              </span>
              <p className="text-[10px] text-slate-400">Yegna Bet Arena</p>
            </div>
          </div>

          {/* Render Game */}
          <div className="flex-1">
            {renderActiveGame()}
          </div>
        </div>
      ) : activeTab === 'admin' && isAdmin ? (
        /* ADMIN DASHBOARD VIEW */
        <div className="w-full max-w-md mx-auto min-h-screen p-4 space-y-4 pb-24">
          <AdminDashboard />
        </div>
      ) : activeTab === 'games' ? (
        /* GAMES CATALOG VIEW */
        <GamesPage onSelectGame={handleSelectGame} />
      ) : activeTab === 'wallet' ? (
        /* WALLET VIEW */
        <WalletPage onOpenAuth={handleOpenAuth} />
      ) : activeTab === 'history' ? (
        /* HISTORY VIEW */
        <div className="w-full max-w-md mx-auto min-h-screen p-4 space-y-4 pb-24">
          <TransactionHistory />
        </div>
      ) : activeTab === 'support' ? (
        /* SUPPORT VIEW */
        <SupportPage />
      ) : (
        /* HOME LOBBY (DEFAULT FOR REGULAR USERS) */
        <HomeLobby
          onSelectGame={handleSelectGame}
          onOpenAuth={handleOpenAuth}
          onOpenDeposit={handleOpenDepositFromHome}
          onViewAllGames={() => setActiveTab('games')}
        />
      )}

      {/* BOTTOM NAVIGATION BAR */}
      <BottomNav activeTab={activeTab} onTabChange={handleTabChange} />

      {/* AUTH MODAL */}
      <AuthModal
        isOpen={authModalOpen}
        onClose={() => setAuthModalOpen(false)}
        defaultTab={authModalTab}
      />
    </div>
  );
}

export default function App() {
  return (
    <TelegramProvider>
      <AuthProvider>
        <DashboardView />
      </AuthProvider>
    </TelegramProvider>
  );
}
