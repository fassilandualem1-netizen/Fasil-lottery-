import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTelegram } from '../hooks/useTelegram';
import { 
  Coins, 
  Zap, 
  RotateCcw, 
  Crown, 
  Star 
} from 'lucide-react';

export const CoinflipGame: React.FC = () => {
  const { user, updateBalance, isDemo } = useAuth();
  const { haptic } = useTelegram();

  const [choice, setChoice] = useState<'HEADS' | 'TAILS'>('HEADS');
  const [betAmount, setBetAmount] = useState<number>(50);
  const [isFlipping, setIsFlipping] = useState<boolean>(false);
  const [result, setResult] = useState<'HEADS' | 'TAILS' | null>(null);
  const [lastWin, setLastWin] = useState<{ won: boolean; amount: number } | null>(null);

  const handleFlip = () => {
    if (user.balance < betAmount) {
      alert('Insufficient wallet balance!');
      return;
    }

    updateBalance(-betAmount, `Coinflip Bet on ${choice}`);
    setIsFlipping(true);
    setResult(null);
    setLastWin(null);
    haptic('impact', 'medium');

    setTimeout(() => {
      const outcome: 'HEADS' | 'TAILS' = Math.random() < 0.5 ? 'HEADS' : 'TAILS';
      setResult(outcome);
      setIsFlipping(false);

      const won = outcome === choice;
      const winAmount = won ? Math.floor(betAmount * 1.96 * 100) / 100 : 0;

      if (won) {
        updateBalance(winAmount, `Coinflip Win on ${choice} (1.96x)`);
        haptic('notification', 'success');
      } else {
        haptic('notification', 'error');
      }

      setLastWin({ won, amount: winAmount });
    }, 1200);
  };

  return (
    <div className="w-full max-w-md mx-auto space-y-3 pb-6">
      <div className="flex items-center justify-between bg-[#151c2e] border border-[#232d48] rounded-xl px-3 py-2">
        <div className="flex items-center space-x-2">
          <Coins className="w-5 h-5 text-amber-400" />
          <span className="text-sm font-black tracking-wider text-slate-100 uppercase">
            Yegna Coinflip
          </span>
        </div>
        <span className="text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
          1.96X MULTIPLIER
        </span>
      </div>

      {/* Coin Display Arena */}
      <div className="relative bg-slate-950 border-2 border-[#232d48] rounded-2xl h-56 flex flex-col items-center justify-center p-4 shadow-2xl overflow-hidden">
        <div
          className={`w-28 h-28 rounded-full border-4 border-amber-400 bg-gradient-to-tr from-amber-600 via-amber-400 to-amber-200 flex items-center justify-center text-slate-950 shadow-2xl transition-all duration-700 ${
            isFlipping ? 'animate-spin' : ''
          }`}
        >
          {result === 'HEADS' || (choice === 'HEADS' && !result) ? (
            <div className="text-center">
              <Crown className="w-12 h-12 mx-auto drop-shadow-md" />
              <span className="text-[10px] font-black uppercase">HEADS</span>
            </div>
          ) : (
            <div className="text-center">
              <Star className="w-12 h-12 mx-auto drop-shadow-md" />
              <span className="text-[10px] font-black uppercase">TAILS</span>
            </div>
          )}
        </div>

        {lastWin && (
          <div className="mt-3 text-center">
            <span
              className={`text-sm font-black uppercase tracking-wider ${
                lastWin.won ? 'text-emerald-400' : 'text-red-400'
              }`}
            >
              {lastWin.won ? `WINNER! +${lastWin.amount} ETB` : 'RESULT: ' + result}
            </span>
          </div>
        )}
      </div>

      {/* Side Selection */}
      <div className="grid grid-cols-2 gap-2">
        <button
          onClick={() => !isFlipping && setChoice('HEADS')}
          disabled={isFlipping}
          className={`p-3 rounded-xl border flex items-center justify-center space-x-2 transition-all ${
            choice === 'HEADS'
              ? 'bg-amber-500/20 border-amber-500 text-amber-400'
              : 'bg-slate-950 border-[#232d48] text-slate-300'
          }`}
        >
          <Crown className="w-5 h-5" />
          <span className="font-black text-sm uppercase">HEADS (1.96x)</span>
        </button>

        <button
          onClick={() => !isFlipping && setChoice('TAILS')}
          disabled={isFlipping}
          className={`p-3 rounded-xl border flex items-center justify-center space-x-2 transition-all ${
            choice === 'TAILS'
              ? 'bg-amber-500/20 border-amber-500 text-amber-400'
              : 'bg-slate-950 border-[#232d48] text-slate-300'
          }`}
        >
          <Star className="w-5 h-5" />
          <span className="font-black text-sm uppercase">TAILS (1.96x)</span>
        </button>
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
              disabled={isFlipping}
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
          onClick={handleFlip}
          disabled={isFlipping}
          className="w-full py-3.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-slate-950 font-black text-base rounded-xl shadow-lg uppercase tracking-wider flex items-center justify-center space-x-2"
        >
          <Zap className="w-5 h-5 fill-slate-950" />
          <span>{isFlipping ? 'FLIPPING COIN...' : `FLIP COIN (${betAmount} ETB)`}</span>
        </button>
      </div>
    </div>
  );
};
