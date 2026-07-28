import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTelegram } from '../hooks/useTelegram';
import { 
  Dices, 
  Zap, 
  RotateCcw, 
  TrendingUp, 
  TrendingDown 
} from 'lucide-react';

export const DiceGame: React.FC = () => {
  const { user, updateBalance, isDemo } = useAuth();
  const { haptic } = useTelegram();

  const [targetNumber, setTargetNumber] = useState<number>(50.00);
  const [rollType, setRollType] = useState<'OVER' | 'UNDER'>('OVER');
  const [betAmount, setBetAmount] = useState<number>(50);
  const [isRolling, setIsRolling] = useState<boolean>(false);
  const [rollResult, setRollResult] = useState<number | null>(null);
  const [lastWin, setLastWin] = useState<{ won: boolean; winAmount: number } | null>(null);

  // Win chance & multiplier calculation
  const winChance = rollType === 'OVER' ? 100 - targetNumber : targetNumber;
  const multiplier = Math.max(1.01, Math.floor((97 / winChance) * 100) / 100);

  const handleRoll = () => {
    if (user.balance < betAmount) {
      alert('Insufficient wallet balance!');
      return;
    }

    updateBalance(-betAmount, `Dice Roll ${rollType} ${targetNumber.toFixed(2)}`);
    setIsRolling(true);
    setRollResult(null);
    setLastWin(null);
    haptic('impact', 'medium');

    setTimeout(() => {
      const outcome = Math.floor(Math.random() * 10000) / 100;
      setRollResult(outcome);
      setIsRolling(false);

      const won = rollType === 'OVER' ? outcome > targetNumber : outcome < targetNumber;
      const winAmount = won ? Math.floor(betAmount * multiplier * 100) / 100 : 0;

      if (won) {
        updateBalance(winAmount, `Dice Win: Rolled ${outcome.toFixed(2)} (${multiplier.toFixed(2)}x)`);
        haptic('notification', 'success');
      } else {
        haptic('notification', 'error');
      }

      setLastWin({ won, winAmount });
    }, 600);
  };

  return (
    <div className="w-full max-w-md mx-auto space-y-3 pb-6">
      <div className="flex items-center justify-between bg-[#151c2e] border border-[#232d48] rounded-xl px-3 py-2">
        <div className="flex items-center space-x-2">
          <Dices className="w-5 h-5 text-amber-400" />
          <span className="text-sm font-black tracking-wider text-slate-100 uppercase">
            Yegna Dice Over/Under
          </span>
        </div>
        <span className="text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
          {multiplier.toFixed(2)}X MULTIPLIER
        </span>
      </div>

      {/* Roll Display Arena */}
      <div className="bg-slate-950 border-2 border-[#232d48] rounded-2xl p-6 flex flex-col items-center justify-center space-y-4 shadow-2xl relative">
        <div className="text-center">
          <span className="text-xs font-bold uppercase text-slate-400 tracking-wider">
            {isRolling ? 'ROLLING...' : 'DICE RESULT'}
          </span>
          <div className="text-5xl font-black text-amber-400 font-mono tracking-tighter mt-1">
            {rollResult !== null ? rollResult.toFixed(2) : '50.00'}
          </div>
        </div>

        {lastWin && (
          <div
            className={`px-4 py-1.5 rounded-full font-black text-xs uppercase border ${
              lastWin.won
                ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                : 'bg-red-500/20 border-red-500/40 text-red-400'
            }`}
          >
            {lastWin.won ? `WON +${lastWin.winAmount} ETB!` : 'ROLLED OUT OF TARGET'}
          </div>
        )}
      </div>

      {/* Slider & Stats Control */}
      <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 space-y-4">
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => !isRolling && setRollType('OVER')}
            disabled={isRolling}
            className={`p-2.5 rounded-xl border flex items-center justify-center space-x-1.5 transition-all ${
              rollType === 'OVER'
                ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                : 'bg-slate-950 border-[#232d48] text-slate-300'
            }`}
          >
            <TrendingUp className="w-4 h-4" />
            <span className="font-black text-xs">ROLL OVER</span>
          </button>

          <button
            onClick={() => !isRolling && setRollType('UNDER')}
            disabled={isRolling}
            className={`p-2.5 rounded-xl border flex items-center justify-center space-x-1.5 transition-all ${
              rollType === 'UNDER'
                ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                : 'bg-slate-950 border-[#232d48] text-slate-300'
            }`}
          >
            <TrendingDown className="w-4 h-4" />
            <span className="font-black text-xs">ROLL UNDER</span>
          </button>
        </div>

        {/* Target Slider */}
        <div className="space-y-1.5">
          <div className="flex justify-between text-xs font-bold text-slate-300">
            <span>Target: {targetNumber.toFixed(2)}</span>
            <span>Win Chance: {winChance.toFixed(2)}%</span>
          </div>
          <input
            type="range"
            min="5.00"
            max="95.00"
            step="1.00"
            value={targetNumber}
            onChange={(e) => !isRolling && setTargetNumber(Number(e.target.value))}
            disabled={isRolling}
            className="w-full accent-amber-400 cursor-pointer"
          />
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-2 gap-2 text-center text-xs">
          <div className="bg-slate-950 border border-[#232d48] p-2 rounded-xl">
            <span className="text-slate-400 block font-bold">Multiplier</span>
            <span className="font-black text-amber-400">{multiplier.toFixed(2)}x</span>
          </div>
          <div className="bg-slate-950 border border-[#232d48] p-2 rounded-xl">
            <span className="text-slate-400 block font-bold">Win Profit</span>
            <span className="font-black text-emerald-400">
              +{(betAmount * multiplier - betAmount).toFixed(2)} ETB
            </span>
          </div>
        </div>
      </div>

      {/* Bet Panel */}
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
              disabled={isRolling}
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

        <button
          onClick={handleRoll}
          disabled={isRolling}
          className="w-full py-3.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-slate-950 font-black text-base rounded-xl shadow-lg uppercase tracking-wider flex items-center justify-center space-x-2"
        >
          <Zap className="w-5 h-5 fill-slate-950" />
          <span>{isRolling ? 'ROLLING DICE...' : `ROLL DICE (${betAmount} ETB)`}</span>
        </button>
      </div>
    </div>
  );
};
