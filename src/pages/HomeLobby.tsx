import React, { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTelegram } from '../hooks/useTelegram';
import { collection, query, where, onSnapshot, limit } from 'firebase/firestore';
import { db } from '../firebase/config';
import { LoopGameType, MultiplayerBet } from '../types';
import { 
  Coins, 
  LogIn, 
  LogOut, 
  Plus, 
  Rocket, 
  Trophy, 
  Users, 
  Flame, 
  Zap, 
  ChevronRight,
  TrendingUp,
  Award,
  ShieldCheck,
  Gamepad2
} from 'lucide-react';

interface HomeLobbyProps {
  onSelectGame: (gameId: LoopGameType) => void;
  onOpenAuth: (tab: 'login' | 'register') => void;
  onOpenDeposit: () => void;
  onViewAllGames: () => void;
}

interface GameCardConfig {
  id: LoopGameType;
  title: string;
  category: string;
  tagline: string;
  badge: string;
  gradient: string;
  accentBorder: string;
  icon: React.FC<{ className?: string }>;
}

// Top 2 Hot Featured Games for Home Dashboard
const HOT_GAMES: GameCardConfig[] = [
  {
    id: 'aviator',
    title: 'Aviator',
    category: 'Crash Game',
    tagline: 'Cash out before the plane crashes!',
    badge: 'HOT • Up to 1000x',
    gradient: 'from-red-600/30 via-amber-500/10 to-slate-900',
    accentBorder: 'border-red-500/40 hover:border-red-400',
    icon: Rocket,
  },
  {
    id: 'virtual_sport',
    title: 'Virtual Sport',
    category: 'Football League',
    tagline: 'Fast-paced simulated match bets',
    badge: 'HOT • Live Odds',
    gradient: 'from-emerald-600/30 via-teal-500/10 to-slate-900',
    accentBorder: 'border-emerald-500/40 hover:border-emerald-400',
    icon: Trophy,
  },
];

export const HomeLobby: React.FC<HomeLobbyProps> = ({
  onSelectGame,
  onOpenAuth,
  onOpenDeposit,
  onViewAllGames,
}) => {
  const { user: tgUser, haptic } = useTelegram();
  const { user, userData, balance, logout } = useAuth();

  // Real-Time Winners Ticker State (100% Firestore Query)
  const [liveWinners, setLiveWinners] = useState<MultiplayerBet[]>([]);
  const [winnersLoading, setWinnersLoading] = useState<boolean>(true);

  // Real-Time Player Counts State (100% Firestore Query)
  const [playerCounts, setPlayerCounts] = useState<Record<string, number>>({
    aviator: 0,
    virtual_sport: 0,
  });

  // 1. Listen for Real-Time Winning Tickets in Firestore
  useEffect(() => {
    setWinnersLoading(true);
    const betsRef = collection(db, 'loop_bets');
    const q = query(betsRef, where('status', '==', 'WON'), limit(15));

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const winningBets: MultiplayerBet[] = [];
        snapshot.forEach((docSnap) => {
          winningBets.push({ id: docSnap.id, ...docSnap.data() } as MultiplayerBet);
        });

        winningBets.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());
        setLiveWinners(winningBets);
        setWinnersLoading(false);
      },
      (error) => {
        console.warn('Real-time winners ticker listener notice:', error.message);
        setWinnersLoading(false);
      }
    );

    return () => unsubscribe();
  }, []);

  // 2. Listen for Real-Time Active Players per Game in Firestore
  useEffect(() => {
    const betsRef = collection(db, 'loop_bets');
    const q = query(betsRef, limit(50));

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const counts: Record<string, Set<string>> = {
          aviator: new Set(),
          virtual_sport: new Set(),
        };

        snapshot.forEach((docSnap) => {
          const bet = docSnap.data() as MultiplayerBet;
          if (bet.gameId && counts[bet.gameId]) {
            counts[bet.gameId].add(bet.userId || bet.id);
          }
        });

        setPlayerCounts({
          aviator: counts.aviator ? counts.aviator.size : 0,
          virtual_sport: counts.virtual_sport ? counts.virtual_sport.size : 0,
        });
      },
      (error) => {
        console.warn('Real-time player count listener notice:', error.message);
      }
    );

    return () => unsubscribe();
  }, []);

  const handleGameClick = (gameId: LoopGameType) => {
    haptic?.impact('medium');
    onSelectGame(gameId);
  };

  return (
    <div className="w-full max-w-[100vw] overflow-x-hidden min-h-screen bg-slate-950 text-white font-sans flex flex-col space-y-3.5 pb-24">
      {/* 1. MINIMAL STICKY HEADER */}
      <header className="sticky top-0 z-40 bg-[#0d1322]/95 backdrop-blur-md border-b border-[#232d48] px-4 py-2.5 shadow-xl">
        <div className="flex items-center justify-between max-w-md mx-auto">
          {/* Logo & Brand */}
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-amber-500 to-amber-300 flex items-center justify-center text-slate-950 font-black text-base shadow-lg shadow-amber-500/20">
              <Coins className="w-4 h-4" />
            </div>
            <div>
              <h1 className="text-sm font-black tracking-wider gold-gradient-text uppercase leading-none">
                YEGNA BET
              </h1>
              <p className="text-[9px] text-slate-400 font-medium">Telegram Casino</p>
            </div>
          </div>

          {/* User Auth Info & Balance Pill */}
          <div className="flex items-center space-x-2">
            {user ? (
              <div className="flex items-center space-x-1.5">
                {/* Balance Badge */}
                <div className="bg-[#151c2e] border border-amber-500/30 rounded-xl px-2.5 py-1 text-right flex flex-col justify-center">
                  <div className="text-[9px] text-slate-400 uppercase font-semibold leading-none">
                    ID: <span className="text-amber-400">{userData?.sixDigitId || 'YG-GUEST'}</span>
                  </div>
                  <div className="text-xs font-black text-amber-400 leading-tight">
                    {balance.toFixed(2)} <span className="text-[9px]">ETB</span>
                  </div>
                </div>

                {/* Small '+' Deposit Icon Button */}
                <button
                  onClick={() => {
                    haptic?.impact('light');
                    onOpenDeposit();
                  }}
                  className="w-8 h-8 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-slate-950 rounded-xl shadow-md font-extrabold transition-all flex items-center justify-center shrink-0"
                  title="Deposit Funds"
                >
                  <Plus className="w-4 h-4" />
                </button>

                {/* Logout Button */}
                <button
                  onClick={() => {
                    haptic?.impact('light');
                    logout();
                  }}
                  className="p-1.5 bg-red-500/10 border border-red-500/30 text-red-400 hover:bg-red-500/20 rounded-xl transition-all"
                  title="Logout"
                >
                  <LogOut className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-1.5">
                <button
                  onClick={() => {
                    haptic?.impact('light');
                    onOpenAuth('login');
                  }}
                  className="px-2.5 py-1.5 bg-[#151c2e] border border-[#232d48] text-slate-200 hover:text-amber-400 text-xs font-bold rounded-xl flex items-center space-x-1 transition-all"
                >
                  <LogIn className="w-3.5 h-3.5" />
                  <span>Login</span>
                </button>
                <button
                  onClick={() => {
                    haptic?.impact('light');
                    onOpenAuth('register');
                  }}
                  className="px-3 py-1.5 bg-amber-500 hover:bg-amber-400 text-slate-950 text-xs font-bold rounded-xl shadow-md transition-all"
                >
                  Register
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* MAIN CONTAINER */}
      <main className="w-full max-w-md mx-auto px-4 space-y-3.5">
        {/* 2. COMPACT PROMO BANNER */}
        <div className="bg-gradient-to-r from-[#151c2e] via-[#1a233a] to-[#151c2e] border border-amber-500/30 rounded-2xl p-3.5 shadow-xl flex items-center justify-between">
          <div className="space-y-1">
            <div className="flex items-center space-x-1.5">
              <span className="px-2 py-0.5 rounded-full bg-amber-500/20 border border-amber-500/40 text-amber-400 text-[9px] font-extrabold uppercase">
                PROVABLY FAIR
              </span>
              <span className="text-[10px] text-emerald-400 font-bold flex items-center space-x-0.5">
                <ShieldCheck className="w-3 h-3" />
                <span>Instant Telebirr</span>
              </span>
            </div>
            <h2 className="text-xs font-black text-slate-100 tracking-wide">
              Ethiopia's Premier Telegram Casino
            </h2>
            <p className="text-[10px] text-slate-400">
              7 Instant Games • Real-Time Multiplayer Seed
            </p>
          </div>
          <button
            onClick={() => {
              haptic?.impact('light');
              onViewAllGames();
            }}
            className="px-3 py-2 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-xs rounded-xl shadow-lg flex items-center space-x-1 shrink-0 transition-all"
          >
            <Gamepad2 className="w-3.5 h-3.5" />
            <span>Games Catalog</span>
          </button>
        </div>

        {/* 3. REAL-TIME WINNERS TICKER (100% FIRESTORE QUERY) */}
        <section className="bg-[#151c2e]/90 border border-amber-500/20 rounded-2xl p-3 shadow-xl space-y-2 relative overflow-hidden">
          <div className="flex items-center justify-between border-b border-[#232d48] pb-1.5">
            <div className="flex items-center space-x-1.5">
              <Flame className="w-3.5 h-3.5 text-amber-400 animate-pulse" />
              <h2 className="text-[11px] font-black text-amber-400 uppercase tracking-wider">
                Live Winners Ticker
              </h2>
            </div>
            <span className="text-[9px] text-slate-400 font-mono">100% Verified Wins</span>
          </div>

          {winnersLoading ? (
            <div className="py-2.5 text-center text-xs text-slate-500 flex items-center justify-center space-x-2">
              <span className="w-2 h-2 rounded-full bg-amber-400 animate-ping" />
              <span>Streaming live tickets...</span>
            </div>
          ) : liveWinners.length === 0 ? (
            <div className="py-2.5 px-2 text-center text-xs text-slate-400 bg-[#0b0f19] rounded-xl border border-[#232d48] flex items-center justify-center space-x-2">
              <Award className="w-4 h-4 text-amber-400 shrink-0" />
              <span>No live wins yet. Be the first to win!</span>
            </div>
          ) : (
            <div className="flex items-center space-x-2 overflow-x-auto no-scrollbar py-0.5">
              {liveWinners.map((win) => (
                <div
                  key={win.id}
                  className="shrink-0 bg-[#0b0f19] border border-emerald-500/30 rounded-xl px-2.5 py-1.5 flex items-center space-x-2 shadow-md"
                >
                  <div className="w-5 h-5 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400 text-[9px] font-bold">
                    <TrendingUp className="w-3 h-3" />
                  </div>
                  <div>
                    <div className="text-[10px] font-bold text-slate-200">
                      {win.sixDigitId || win.displayName || 'Player'}
                    </div>
                    <div className="text-[9px] text-slate-400 capitalize">
                      {win.gameId.replace('_', ' ')}
                    </div>
                  </div>
                  <div className="text-right pl-1">
                    <div className="text-xs font-black text-emerald-400">
                      +{win.payout.toFixed(2)} ETB
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* 4. TOP 2 HOT FEATURED GAMES */}
        <section className="space-y-2.5">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5">
              <Zap className="w-4 h-4 text-amber-400" />
              <h2 className="text-xs font-black text-slate-100 uppercase tracking-wider">
                Hot Featured Arena
              </h2>
            </div>
            <button
              onClick={() => {
                haptic?.impact('light');
                onViewAllGames();
              }}
              className="text-[10px] text-amber-400 hover:text-amber-300 font-bold flex items-center space-x-0.5"
            >
              <span>View All 7 Games</span>
              <ChevronRight className="w-3 h-3" />
            </button>
          </div>

          <div className="grid grid-cols-2 gap-3">
            {HOT_GAMES.map((game) => {
              const Icon = game.icon;
              const activeCount = playerCounts[game.id] || 0;

              return (
                <div
                  key={game.id}
                  onClick={() => handleGameClick(game.id)}
                  className={`group relative bg-gradient-to-br ${game.gradient} bg-[#151c2e] border ${game.accentBorder} rounded-2xl p-3.5 flex flex-col justify-between shadow-xl cursor-pointer hover:scale-[1.02] active:scale-95 transition-all duration-200 space-y-3`}
                >
                  {/* Top Badge & Icon Row */}
                  <div className="flex items-center justify-between">
                    <div className="w-9 h-9 rounded-xl bg-slate-900/80 border border-slate-700/50 flex items-center justify-center text-amber-400 shadow-lg group-hover:text-amber-300">
                      <Icon className="w-4 h-4" />
                    </div>
                    <span className="px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[9px] font-black tracking-tight">
                      {game.badge}
                    </span>
                  </div>

                  {/* Title & Description */}
                  <div>
                    <h3 className="text-sm font-black text-slate-100 group-hover:text-amber-400 transition-colors">
                      {game.title}
                    </h3>
                    <p className="text-[10px] text-slate-400 line-clamp-2 mt-0.5 leading-tight">
                      {game.tagline}
                    </p>
                  </div>

                  {/* Real-time Player Count & Play Trigger */}
                  <div className="pt-2 border-t border-[#232d48] flex items-center justify-between">
                    <div className="flex items-center space-x-1 text-[10px] text-slate-400 font-medium">
                      <Users className="w-3 h-3 text-emerald-400" />
                      <span>{activeCount} Live</span>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        handleGameClick(game.id);
                      }}
                      className="px-2.5 py-1 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black text-[10px] rounded-lg shadow-md flex items-center space-x-0.5 transition-all"
                    >
                      <span>PLAY</span>
                      <ChevronRight className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>

          {/* Catalog Banner CTA */}
          <div 
            onClick={() => {
              haptic?.impact('light');
              onViewAllGames();
            }}
            className="w-full py-3 px-4 bg-[#151c2e] border border-[#232d48] hover:border-amber-500/40 rounded-2xl flex items-center justify-between cursor-pointer shadow-lg transition-all"
          >
            <div className="flex items-center space-x-3">
              <div className="w-8 h-8 rounded-xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                <Gamepad2 className="w-4 h-4" />
              </div>
              <div>
                <div className="text-xs font-bold text-slate-100">Explore Full Game Library</div>
                <div className="text-[10px] text-slate-400">Mines, Classic Dice, Color Wheel, Keno & Coinflip</div>
              </div>
            </div>
            <ChevronRight className="w-4 h-4 text-amber-400" />
          </div>
        </section>
      </main>
    </div>
  );
};

export default HomeLobby;
