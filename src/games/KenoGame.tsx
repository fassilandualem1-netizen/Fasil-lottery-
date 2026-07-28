import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTelegram } from '../hooks/useTelegram';
import { 
  Sparkles, 
  RotateCcw, 
  Zap, 
  Trophy, 
  CheckCircle2, 
  HelpCircle 
} from 'lucide-react';

// Keno Payout Table depending on selected count & matched count
const KENO_PAYOUTS: Record<number, Record<number, number>> = {
  1: { 1: 3.5 },
  2: { 1: 1.0, 2: 7.0 },
  3: { 2: 2.5, 3: 25.0 },
  4: { 2: 1.0, 3: 5.0, 4: 80.0 },
  5: { 3: 2.0, 4: 15.0, 5: 300.0 },
  6: { 3: 1.0, 4: 7.0, 5: 50.0, 6: 1000.0 },
  7: { 4: 3.0, 5: 20.0, 6: 200.0, 7: 2000.0 },
  8: { 4: 2.0, 5: 12.0, 6: 80.0, 7: 500.0, 8: 5000.0 },
  9: { 5: 5.0, 6: 30.0, 7: 200.0, 8: 1500.0, 9: 10000.0 },
  10: { 5: 2.0, 6: 15.0, 7: 100.0, 8: 600.0, 9: 3000.0, 10: 25000.0 },
};

export const KenoGame: React.FC = () => {
  const { user, updateBalance, isDemo } = useAuth();
  const { haptic } = useTelegram();

  const [selectedNumbers, setSelectedNumbers] = useState<number[]>([]);
  const [betAmount, setBetAmount] = useState<number>(50);
  const [drawnNumbers, setDrawnNumbers] = useState<number[]>([]);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [lastResult, setLastResult] = useState<{ matches: number; winAmount: number; mult: number } | null>(null);

  const toggleNumber = (num: number) => {
    if (isPlaying) return;
    if (selectedNumbers.includes(num)) {
      setSelectedNumbers((prev) => prev.filter((n) => n !== num));
      haptic('selection');
    } else {
      if (selectedNumbers.length >= 10) {
        alert('You can select a maximum of 10 numbers.');
        return;
      }
      setSelectedNumbers((prev) => [...prev, num].sort((a, b) => a - b));
      haptic('selection');
    }
  };

  const handleAutoPick = () => {
    if (isPlaying) return;
    const picked: number[] = [];
    while (picked.length < 10) {
      const rand = Math.floor(Math.random() * 80) + 1;
      if (!picked.includes(rand)) picked.push(rand);
    }
    setSelectedNumbers(picked.sort((a, b) => a - b));
    haptic('impact', 'light');
  };

  const handleClear = () => {
    if (isPlaying) return;
    setSelectedNumbers([]);
    setDrawnNumbers([]);
    setLastResult(null);
  };

  const handlePlayKeno = () => {
    if (selectedNumbers.length === 0) {
      alert('Please select at least 1 number to play.');
      return;
    }
    if (user.balance < betAmount) {
      alert('Insufficient wallet balance!');
      return;
    }

    updateBalance(-betAmount, `Keno Bet (${selectedNumbers.length} numbers)`);
    setIsPlaying(true);
    setDrawnNumbers([]);
    setLastResult(null);
    haptic('impact', 'medium');

    // Generate 20 unique numbers from 1 to 80
    const drawPool: number[] = [];
    while (drawPool.length < 20) {
      const num = Math.floor(Math.random() * 80) + 1;
      if (!drawPool.includes(num)) drawPool.push(num);
    }

    // Animate drawing balls one by one
    let idx = 0;
    const interval = setInterval(() => {
      if (idx < 20) {
        const nextNum = drawPool[idx];
        setDrawnNumbers((prev) => [...prev, nextNum]);
        haptic('impact', 'light');
        idx++;
      } else {
        clearInterval(interval);
        // Calculate result
        const matches = selectedNumbers.filter((n) => drawPool.includes(n)).length;
        const payoutsForCount = KENO_PAYOUTS[selectedNumbers.length] || {};
        const mult = payoutsForCount[matches] || 0;
        const winAmount = Math.floor(betAmount * mult * 100) / 100;

        if (winAmount > 0) {
          updateBalance(winAmount, `Keno Win (${matches}/${selectedNumbers.length} Hits - ${mult}x)`);
          haptic('notification', 'success');
        } else {
          haptic('notification', 'error');
        }

        setLastResult({ matches, winAmount, mult });
        setIsPlaying(false);
      }
    }, 120);
  };

  const activePayoutMap = KENO_PAYOUTS[selectedNumbers.length] || {};

  return (
    <div className="w-full max-w-md mx-auto space-y-3 pb-6">
      {/* Top Banner */}
      <div className="flex items-center justify-between bg-[#151c2e] border border-[#232d48] rounded-xl px-3 py-2">
        <div className="flex items-center space-x-2">
          <Sparkles className="w-5 h-5 text-amber-400 animate-spin" />
          <span className="text-sm font-black tracking-wider text-slate-100 uppercase">
            Yegna Keno 80
          </span>
        </div>
        <span className="text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
          Pick {selectedNumbers.length}/10
        </span>
      </div>

      {/* Drawn Balls Bar */}
      <div className="bg-slate-950 border border-[#232d48] rounded-2xl p-3 space-y-2">
        <div className="flex items-center justify-between text-[11px] font-bold uppercase text-slate-400">
          <span>Live Drawn Balls ({drawnNumbers.length}/20):</span>
          {lastResult && (
            <span className={lastResult.winAmount > 0 ? 'text-emerald-400 font-black' : 'text-slate-400'}>
              {lastResult.matches} Hits - {lastResult.winAmount > 0 ? `+${lastResult.winAmount} ETB` : 'No Win'}
            </span>
          )}
        </div>

        <div className="flex items-center space-x-1.5 overflow-x-auto py-1 min-h-[44px] scrollbar-none">
          {drawnNumbers.length === 0 ? (
            <span className="text-xs text-slate-600 font-semibold italic mx-auto">
              Press PLAY to draw 20 Keno balls
            </span>
          ) : (
            drawnNumbers.map((num, i) => {
              const isMatch = selectedNumbers.includes(num);
              return (
                <div
                  key={i}
                  className={`shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-xs font-black border transition-all animate-bounce ${
                    isMatch
                      ? 'bg-amber-400 border-amber-300 text-slate-950 shadow-lg shadow-amber-400/40 scale-110'
                      : 'bg-slate-800 border-slate-700 text-slate-200'
                  }`}
                >
                  {num}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 80-Number Selection Grid */}
      <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-3 space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold text-slate-400 uppercase">Select Numbers (1-80)</span>
          <div className="flex space-x-2">
            <button
              onClick={handleAutoPick}
              disabled={isPlaying}
              className="px-2.5 py-1 bg-amber-500/20 border border-amber-500/40 text-amber-300 rounded-lg text-xs font-bold hover:bg-amber-500/30 transition-all disabled:opacity-50"
            >
              Auto Pick
            </button>
            <button
              onClick={handleClear}
              disabled={isPlaying}
              className="px-2.5 py-1 bg-slate-900 border border-[#232d48] text-slate-400 rounded-lg text-xs font-bold hover:text-slate-200 transition-all disabled:opacity-50"
            >
              Clear
            </button>
          </div>
        </div>

        <div className="grid grid-cols-10 gap-1 text-center">
          {Array.from({ length: 80 }, (_, i) => i + 1).map((num) => {
            const isSelected = selectedNumbers.includes(num);
            const isDrawn = drawnNumbers.includes(num);
            const isHit = isSelected && isDrawn;

            return (
              <button
                key={num}
                onClick={() => toggleNumber(num)}
                disabled={isPlaying}
                className={`h-7 rounded-md text-xs font-black transition-all flex items-center justify-center border ${
                  isHit
                    ? 'bg-emerald-500 border-emerald-400 text-slate-950 shadow-md scale-105'
                    : isDrawn
                    ? 'bg-slate-800 border-slate-700 text-slate-500 line-through'
                    : isSelected
                    ? 'bg-amber-400 border-amber-300 text-slate-950 shadow-md'
                    : 'bg-slate-950 border-[#232d48] text-slate-300 hover:border-amber-500/50'
                }`}
              >
                {num}
              </button>
            );
          })}
        </div>
      </div>

      {/* Dynamic Payout Table Ribbon */}
      <div className="bg-[#151c2e] border border-[#232d48] rounded-xl p-2.5">
        <div className="text-[10px] font-extrabold uppercase text-slate-400 mb-1.5">
          Hit Multipliers (for Pick {selectedNumbers.length}):
        </div>
        <div className="flex items-center space-x-1.5 overflow-x-auto scrollbar-none">
          {Object.keys(activePayoutMap).length === 0 ? (
            <span className="text-xs text-slate-500">Select numbers to view hit multipliers</span>
          ) : (
            Object.entries(activePayoutMap).map(([hits, mult]) => (
              <div
                key={hits}
                className="shrink-0 bg-slate-950 border border-[#232d48] px-2 py-1 rounded-lg text-center"
              >
                <div className="text-[10px] text-slate-400 font-bold">{hits} Hits</div>
                <div className="text-xs font-black text-amber-400">{mult}x</div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Bet Panel & Action Trigger */}
      <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 space-y-3">
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
              onClick={() => setBetAmount(amt)}
              disabled={isPlaying}
              className={`py-1.5 text-xs font-black rounded-lg border transition-all ${
                betAmount === amt
                  ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                  : 'bg-slate-900 border-[#232d48] text-slate-300 hover:border-slate-700'
              }`}
            >
              +{amt}
            </button>
          ))}
        </div>

        <button
          onClick={handlePlayKeno}
          disabled={isPlaying || selectedNumbers.length === 0}
          className="w-full py-3.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-slate-950 font-black text-base rounded-xl shadow-lg shadow-amber-500/20 uppercase tracking-wider flex items-center justify-center space-x-2 transition-all"
        >
          <Zap className="w-5 h-5 fill-slate-950" />
          <span>{isPlaying ? 'DRAWING BALLS...' : `PLAY KENO (${betAmount} ETB)`}</span>
        </button>
      </div>
    </div>
  );
};
