import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTelegram } from '../hooks/useTelegram';
import { 
  Bomb, 
  Gem, 
  Zap, 
  RotateCcw, 
  CheckCircle2, 
  Shield 
} from 'lucide-react';

export const MinesGame: React.FC = () => {
  const { user, updateBalance, isDemo } = useAuth();
  const { haptic } = useTelegram();

  const [mineCount, setMineCount] = useState<number>(3);
  const [betAmount, setBetAmount] = useState<number>(50);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [grid, setGrid] = useState<{ isMine: boolean; revealed: boolean }[]>(
    Array(25).fill({ isMine: false, revealed: false })
  );
  const [revealedCount, setRevealedCount] = useState<number>(0);
  const [currentMultiplier, setCurrentMultiplier] = useState<number>(1.00);
  const [gameOver, setGameOver] = useState<boolean>(false);
  const [cashedOut, setCashedOut] = useState<boolean>(false);
  const [winAmount, setWinAmount] = useState<number>(0);

  // Calculate multiplier step
  const calculateNextMultiplier = (safeRevealed: number, mines: number) => {
    let mult = 1.0;
    const totalTiles = 25;
    for (let i = 0; i < safeRevealed; i++) {
      const remainingTiles = totalTiles - i;
      const safeTilesLeft = totalTiles - mines - i;
      mult *= remainingTiles / safeTilesLeft;
    }
    return Math.floor(mult * 0.97 * 100) / 100; // 3% house edge
  };

  const handleStartGame = () => {
    if (user.balance < betAmount) {
      alert('Insufficient wallet balance!');
      return;
    }

    updateBalance(-betAmount, `Mines Bet (${mineCount} Mines)`);
    haptic('impact', 'medium');

    // Place mines randomly
    const newGrid = Array(25).fill(null).map(() => ({ isMine: false, revealed: false }));
    let placed = 0;
    while (placed < mineCount) {
      const idx = Math.floor(Math.random() * 25);
      if (!newGrid[idx].isMine) {
        newGrid[idx].isMine = true;
        placed++;
      }
    }

    setGrid(newGrid);
    setRevealedCount(0);
    setCurrentMultiplier(1.00);
    setIsPlaying(true);
    setGameOver(false);
    setCashedOut(false);
    setWinAmount(0);
  };

  const handleTileClick = (index: number) => {
    if (!isPlaying || grid[index].revealed || gameOver || cashedOut) return;

    const updatedGrid = [...grid];
    updatedGrid[index].revealed = true;
    setGrid(updatedGrid);

    if (updatedGrid[index].isMine) {
      // Hit Mine!
      haptic('notification', 'error');
      setGameOver(true);
      setIsPlaying(false);
      // Reveal all tiles
      setGrid(updatedGrid.map((t) => ({ ...t, revealed: true })));
    } else {
      // Safe Diamond Hit
      haptic('impact', 'light');
      const nextRevealed = revealedCount + 1;
      setRevealedCount(nextRevealed);
      const nextMult = calculateNextMultiplier(nextRevealed, mineCount);
      setCurrentMultiplier(nextMult);
    }
  };

  const handleCashout = () => {
    if (!isPlaying || revealedCount === 0 || gameOver || cashedOut) return;

    const payout = Math.floor(betAmount * currentMultiplier * 100) / 100;
    updateBalance(payout, `Mines Cashout (${currentMultiplier.toFixed(2)}x)`);
    haptic('notification', 'success');
    setCashedOut(true);
    setWinAmount(payout);
    setIsPlaying(false);
    // Reveal rest of tiles
    setGrid(grid.map((t) => ({ ...t, revealed: true })));
  };

  return (
    <div className="w-full max-w-md mx-auto space-y-3 pb-6">
      {/* Header Banner */}
      <div className="flex items-center justify-between bg-[#151c2e] border border-[#232d48] rounded-xl px-3 py-2">
        <div className="flex items-center space-x-2">
          <Bomb className="w-5 h-5 text-amber-400" />
          <span className="text-sm font-black tracking-wider text-slate-100 uppercase">
            Yegna Mines
          </span>
        </div>
        <span className="text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
          {mineCount} MINES GRID
        </span>
      </div>

      {/* Grid Display Arena */}
      <div className="bg-slate-950 border-2 border-[#232d48] rounded-2xl p-4 space-y-3 shadow-2xl">
        <div className="flex items-center justify-between text-xs font-bold text-slate-400 border-b border-[#232d48] pb-2">
          <div className="flex items-center space-x-1 text-emerald-400">
            <Gem className="w-4 h-4" />
            <span>Gems: {revealedCount} / {25 - mineCount}</span>
          </div>
          <div className="text-amber-400 font-black text-sm">
            Multiplier: {currentMultiplier.toFixed(2)}x
          </div>
        </div>

        {/* 5x5 Tile Buttons Grid */}
        <div className="grid grid-cols-5 gap-2">
          {grid.map((tile, i) => (
            <button
              key={i}
              onClick={() => handleTileClick(i)}
              disabled={!isPlaying || tile.revealed}
              className={`h-14 rounded-xl flex items-center justify-center text-xl transition-all border ${
                tile.revealed
                  ? tile.isMine
                    ? 'bg-red-500/20 border-red-500/50 text-red-400 shadow-inner scale-95'
                    : 'bg-emerald-500/20 border-emerald-500/50 text-emerald-400 shadow-inner scale-95'
                  : 'bg-[#151c2e] border-[#232d48] hover:border-amber-500/50 active:scale-95 shadow-md'
              }`}
            >
              {tile.revealed ? (
                tile.isMine ? (
                  <Bomb className="w-6 h-6 text-red-500 animate-bounce" />
                ) : (
                  <Gem className="w-6 h-6 text-emerald-400 animate-pulse" />
                )
              ) : (
                <div className="w-3 h-3 rounded-full bg-slate-700/50" />
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Controls & Betting Panel */}
      <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase text-slate-400">Mine Count</span>
          <div className="flex space-x-1">
            {[1, 3, 5, 10, 20].map((m) => (
              <button
                key={m}
                onClick={() => !isPlaying && setMineCount(m)}
                disabled={isPlaying}
                className={`px-2.5 py-1 text-xs font-black rounded-lg border transition-all ${
                  mineCount === m
                    ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                    : 'bg-slate-900 border-[#232d48] text-slate-400'
                }`}
              >
                {m}
              </button>
            ))}
          </div>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase text-slate-400">Bet Amount (ETB)</span>
          <span className="text-xs font-bold text-amber-400">
            Balance: {isDemo ? `${user.demoBalance} (DEMO)` : `${user.balance.toLocaleString()} ETB`}
          </span>
        </div>

        <div className="grid grid-cols-4 gap-1.5">
          {[10, 50, 100, 500].map((amt) => (
            <button
              key={amt}
              onClick={() => !isPlaying && setBetAmount(amt)}
              disabled={isPlaying}
              className={`py-1.5 text-xs font-black rounded-lg border transition-all ${
                betAmount === amt
                  ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                  : 'bg-slate-900 border-[#232d48] text-slate-300'
              }`}
            >
              +{amt}
            </button>
          ))}
        </div>

        {isPlaying ? (
          <button
            onClick={handleCashout}
            disabled={revealedCount === 0}
            className="w-full py-3.5 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 disabled:opacity-50 text-slate-950 font-black text-base rounded-xl shadow-lg uppercase tracking-wider flex items-center justify-center space-x-2 animate-pulse"
          >
            <Shield className="w-5 h-5 fill-slate-950" />
            <span>CASH OUT ({(betAmount * currentMultiplier).toFixed(2)} ETB)</span>
          </button>
        ) : (
          <button
            onClick={handleStartGame}
            className="w-full py-3.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-base rounded-xl shadow-lg uppercase tracking-wider flex items-center justify-center space-x-2"
          >
            <Zap className="w-5 h-5 fill-slate-950" />
            <span>START MINES GAME ({betAmount} ETB)</span>
          </button>
        )}
      </div>
    </div>
  );
};
