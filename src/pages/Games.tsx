import React, { useEffect, useState } from 'react';
import { useTelegram } from '../hooks/useTelegram';
import { collection, query, limit, onSnapshot } from 'firebase/firestore';
import { db } from '../firebase/config';
import { LoopGameType, MultiplayerBet } from '../types';
import { 
  Rocket, 
  Trophy, 
  Dices, 
  Sparkles, 
  Bomb, 
  Dice5, 
  Disc, 
  Users, 
  Zap, 
  ChevronRight,
  Gamepad2,
  Filter
} from 'lucide-react';

interface GamesPageProps {
  onSelectGame: (gameId: LoopGameType) => void;
}

type CategoryType = 'All' | 'Crash' | 'Table' | 'Instant';

interface FullGameConfig {
  id: LoopGameType;
  title: string;
  category: CategoryType;
  categoryLabel: string;
  tagline: string;
  badge: string;
  gradient: string;
  accentBorder: string;
  icon: React.FC<{ className?: string }>;
}

const ALL_GAMES: FullGameConfig[] = [
  {
    id: 'aviator',
    title: 'Aviator',
    category: 'Crash',
    categoryLabel: 'Crash Game',
    tagline: 'Cash out before the plane crashes!',
    badge: 'Up to 1000x',
    gradient: 'from-red-600/30 via-amber-500/10 to-slate-900',
    accentBorder: 'border-red-500/40 hover:border-red-400',
    icon: Rocket,
  },
  {
    id: 'virtual_sport',
    title: 'Virtual Sport',
    category: 'Table',
    categoryLabel: 'Football League',
    tagline: 'Fast-paced simulated match bets',
    badge: 'Live Odds',
    gradient: 'from-emerald-600/30 via-teal-500/10 to-slate-900',
    accentBorder: 'border-emerald-500/40 hover:border-emerald-400',
    icon: Trophy,
  },
  {
    id: 'keno',
    title: 'Keno',
    category: 'Instant',
    categoryLabel: 'Number Lottery',
    tagline: 'Pick numbers & match the 20-ball draw',
    badge: '100x Jackpot',
    gradient: 'from-purple-600/30 via-indigo-500/10 to-slate-900',
    accentBorder: 'border-purple-500/40 hover:border-purple-400',
    icon: Dices,
  },
  {
    id: 'coinflip',
    title: 'Coinflip',
    category: 'Instant',
    categoryLabel: 'Instant 50/50',
    tagline: 'Heads or Tails for instant 1.96x payout',
    badge: 'Instant Win',
    gradient: 'from-amber-600/30 via-yellow-500/10 to-slate-900',
    accentBorder: 'border-amber-500/40 hover:border-amber-400',
    icon: Sparkles,
  },
  {
    id: 'mines',
    title: 'Mines',
    category: 'Instant',
    categoryLabel: 'Minesweeper',
    tagline: 'Find diamonds, avoid hidden bombs!',
    badge: 'Multi-Step',
    gradient: 'from-cyan-600/30 via-blue-500/10 to-slate-900',
    accentBorder: 'border-cyan-500/40 hover:border-cyan-400',
    icon: Bomb,
  },
  {
    id: 'dice',
    title: 'Classic Dice',
    category: 'Instant',
    categoryLabel: 'Roll Over/Under',
    tagline: 'Set win chance & roll slider',
    badge: 'Custom Odds',
    gradient: 'from-rose-600/30 via-pink-500/10 to-slate-900',
    accentBorder: 'border-rose-500/40 hover:border-rose-400',
    icon: Dice5,
  },
  {
    id: 'color_wheel',
    title: 'Color Wheel',
    category: 'Table',
    categoryLabel: 'CSS Roulette',
    tagline: 'Bet Red, Black, Green or Gold sectors',
    badge: '14x Multiplier',
    gradient: 'from-violet-600/30 via-fuchsia-500/10 to-slate-900',
    accentBorder: 'border-violet-500/40 hover:border-violet-400',
    icon: Disc,
  },
];

export const GamesPage: React.FC<GamesPageProps> = ({ onSelectGame }) => {
  const { haptic } = useTelegram();
  const [selectedCategory, setSelectedCategory] = useState<CategoryType>('All');

  // Real-Time Player Counts per Game from Firestore
  const [playerCounts, setPlayerCounts] = useState<Record<string, number>>({});

  useEffect(() => {
    const betsRef = collection(db, 'loop_bets');
    const q = query(betsRef, limit(50));

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const counts: Record<string, Set<string>> = {};

        snapshot.forEach((docSnap) => {
          const bet = docSnap.data() as MultiplayerBet;
          if (bet.gameId) {
            if (!counts[bet.gameId]) counts[bet.gameId] = new Set();
            counts[bet.gameId].add(bet.userId || bet.id);
          }
        });

        const newPlayerCounts: Record<string, number> = {};
        Object.keys(counts).forEach((gId) => {
          newPlayerCounts[gId] = counts[gId].size;
        });

        setPlayerCounts(newPlayerCounts);
      },
      (error) => {
        console.warn('Real-time player count query notice:', error.message);
      }
    );

    return () => unsubscribe();
  }, []);

  const filteredGames = selectedCategory === 'All'
    ? ALL_GAMES
    : ALL_GAMES.filter((g) => g.category === selectedCategory);

  const categories: CategoryType[] = ['All', 'Crash', 'Table', 'Instant'];

  const handleGameClick = (gameId: LoopGameType) => {
    haptic?.impact('medium');
    onSelectGame(gameId);
  };

  return (
    <div className="w-full max-w-md mx-auto min-h-screen p-4 space-y-4 pb-24 text-white font-sans">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-[#232d48] pb-3">
        <div className="flex items-center space-x-2">
          <div className="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
            <Gamepad2 className="w-4 h-4" />
          </div>
          <div>
            <h2 className="text-base font-black text-amber-400 uppercase tracking-wide">
              Game Catalog
            </h2>
            <p className="text-[10px] text-slate-400">7 Real-Time Provably Fair Games</p>
          </div>
        </div>
        <span className="px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[10px] font-bold">
          {ALL_GAMES.length} Active Games
        </span>
      </div>

      {/* Category Filter Pills */}
      <div className="flex items-center space-x-2 overflow-x-auto no-scrollbar py-1">
        <Filter className="w-3.5 h-3.5 text-slate-400 shrink-0 mr-1" />
        {categories.map((cat) => {
          const isActive = selectedCategory === cat;
          return (
            <button
              key={cat}
              onClick={() => {
                haptic?.impact('light');
                setSelectedCategory(cat);
              }}
              className={`px-3 py-1.5 rounded-xl text-xs font-extrabold shrink-0 transition-all ${
                isActive
                  ? 'bg-amber-500 text-slate-950 shadow-md shadow-amber-500/20'
                  : 'bg-[#151c2e] border border-[#232d48] text-slate-400 hover:text-slate-200'
              }`}
            >
              {cat}
            </button>
          );
        })}
      </div>

      {/* Games Grid (2 columns) */}
      <div className="grid grid-cols-2 gap-3">
        {filteredGames.map((game) => {
          const Icon = game.icon;
          const liveCount = playerCounts[game.id] || 0;

          return (
            <div
              key={game.id}
              onClick={() => handleGameClick(game.id)}
              className={`group relative bg-gradient-to-br ${game.gradient} bg-[#151c2e] border ${game.accentBorder} rounded-2xl p-3.5 flex flex-col justify-between shadow-xl cursor-pointer hover:scale-[1.02] active:scale-95 transition-all duration-200 space-y-3`}
            >
              {/* Top Badge & Icon */}
              <div className="flex items-center justify-between">
                <div className="w-9 h-9 rounded-xl bg-slate-900/80 border border-slate-700/50 flex items-center justify-center text-amber-400 shadow-lg group-hover:text-amber-300">
                  <Icon className="w-4 h-4" />
                </div>
                <span className="px-2 py-0.5 rounded-full bg-amber-500/10 border border-amber-500/30 text-amber-400 text-[9px] font-black tracking-tight">
                  {game.badge}
                </span>
              </div>

              {/* Title & Tagline */}
              <div>
                <div className="text-[9px] text-amber-400/80 font-semibold uppercase tracking-wider">
                  {game.categoryLabel}
                </div>
                <h3 className="text-sm font-black text-slate-100 group-hover:text-amber-400 transition-colors leading-tight">
                  {game.title}
                </h3>
                <p className="text-[10px] text-slate-400 line-clamp-2 mt-0.5 leading-tight">
                  {game.tagline}
                </p>
              </div>

              {/* Footer Row */}
              <div className="pt-2 border-t border-[#232d48] flex items-center justify-between">
                <div className="flex items-center space-x-1 text-[10px] text-slate-400 font-medium">
                  <Users className="w-3 h-3 text-emerald-400" />
                  <span>{liveCount} Live</span>
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
    </div>
  );
};

export default GamesPage;
