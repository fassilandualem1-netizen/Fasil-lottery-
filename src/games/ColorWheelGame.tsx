import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTelegram } from '../hooks/useTelegram';
import { 
  Compass, 
  Zap, 
  RotateCcw, 
  Sparkles 
} from 'lucide-react';

const SEGMENTS = [
  { mult: 1.2, color: 'bg-emerald-500', label: '1.2x' },
  { mult: 0, color: 'bg-slate-800', label: '0x' },
  { mult: 1.5, color: 'bg-blue-500', label: '1.5x' },
  { mult: 2.0, color: 'bg-purple-500', label: '2x' },
  { mult: 0, color: 'bg-slate-800', label: '0x' },
  { mult: 3.0, color: 'bg-amber-500', label: '3x' },
  { mult: 1.2, color: 'bg-emerald-500', label: '1.2x' },
  { mult: 5.0, color: 'bg-pink-500', label: '5x' },
  { mult: 0, color: 'bg-slate-800', label: '0x' },
  { mult: 10.0, color: 'bg-red-500', label: '10x' },
  { mult: 2.0, color: 'bg-purple-500', label: '2x' },
  { mult: 25.0, color: 'bg-yellow-400', label: '25x' },
];

export const ColorWheelGame: React.FC = () => {
  const { user, updateBalance, isDemo } = useAuth();
  const { haptic } = useTelegram();

  const [betAmount, setBetAmount] = useState<number>(50);
  const [isSpinning, setIsSpinning] = useState<boolean>(false);
  const [rotation, setRotation] = useState<number>(0);
  const [lastWin, setLastWin] = useState<{ mult: number; amount: number } | null>(null);

  const handleSpin = () => {
    if (user.balance < betAmount) {
      alert('Insufficient wallet balance!');
      return;
    }

    updateBalance(-betAmount, `Color Wheel Spin`);
    setIsSpinning(true);
    setLastWin(null);
    haptic('impact', 'medium');

    const randomIndex = Math.floor(Math.random() * SEGMENTS.length);
    const segmentAngle = 360 / SEGMENTS.length;
    const targetAngle = 360 * 5 + (SEGMENTS.length - randomIndex) * segmentAngle - segmentAngle / 2;

    setRotation((prev) => prev + targetAngle);

    setTimeout(() => {
      setIsSpinning(false);
      const landed = SEGMENTS[randomIndex];
      const winAmount = Math.floor(betAmount * landed.mult * 100) / 100;

      if (winAmount > 0) {
        updateBalance(winAmount, `Color Wheel Win (${landed.mult}x)`);
        haptic('notification', 'success');
      } else {
        haptic('notification', 'error');
      }

      setLastWin({ mult: landed.mult, amount: winAmount });
    }, 4000);
  };

  return (
    <div className="w-full max-w-md mx-auto space-y-3 pb-6">
      <div className="flex items-center justify-between bg-[#151c2e] border border-[#232d48] rounded-xl px-3 py-2">
        <div className="flex items-center space-x-2">
          <Compass className="w-5 h-5 text-amber-400" />
          <span className="text-sm font-black tracking-wider text-slate-100 uppercase">
            Yegna Color Wheel
          </span>
        </div>
        <span className="text-xs font-bold text-amber-400 bg-amber-500/10 border border-amber-500/20 px-2 py-0.5 rounded-full">
          UP TO 25X MULTIPLIER
        </span>
      </div>

      {/* Wheel Arena */}
      <div className="relative bg-slate-950 border-2 border-[#232d48] rounded-2xl h-64 flex flex-col items-center justify-center p-4 shadow-2xl overflow-hidden">
        {/* Top Pointer */}
        <div className="absolute top-2 z-20 w-0 h-0 border-l-[12px] border-l-transparent border-r-[12px] border-r-transparent border-t-[20px] border-t-amber-400 drop-shadow-md" />

        {/* Rotating Wheel Container */}
        <div
          className="w-48 h-48 rounded-full border-4 border-amber-400/50 relative overflow-hidden transition-transform duration-[4000ms] ease-out shadow-2xl"
          style={{ transform: `rotate(${rotation}deg)` }}
        >
          {SEGMENTS.map((seg, i) => {
            const angle = (360 / SEGMENTS.length) * i;
            return (
              <div
                key={i}
                className={`absolute w-full h-full text-center text-[10px] font-black text-slate-950 ${seg.color}`}
                style={{
                  clipPath: 'polygon(50% 50%, 50% 0%, 75% 0%)',
                  transform: `rotate(${angle}deg)`,
                  transformOrigin: '50% 50%',
                }}
              />
            );
          })}
          <div className="absolute inset-4 rounded-full bg-slate-950/40 border border-slate-700/50 flex items-center justify-center">
            <Sparkles className="w-8 h-8 text-amber-400 animate-spin" />
          </div>
        </div>

        {lastWin && (
          <div className="mt-2 text-center z-10">
            <span
              className={`text-xs font-black uppercase ${
                lastWin.amount > 0 ? 'text-emerald-400' : 'text-slate-400'
              }`}
            >
              {lastWin.amount > 0 ? `WINNER! +${lastWin.amount} ETB (${lastWin.mult}x)` : '0x - TRY AGAIN!'}
            </span>
          </div>
        )}
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
              disabled={isSpinning}
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
          onClick={handleSpin}
          disabled={isSpinning}
          className="w-full py-3.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-slate-950 font-black text-base rounded-xl shadow-lg uppercase tracking-wider flex items-center justify-center space-x-2"
        >
          <Zap className="w-5 h-5 fill-slate-950" />
          <span>{isSpinning ? 'SPINNING WHEEL...' : `SPIN WHEEL (${betAmount} ETB)`}</span>
        </button>
      </div>
    </div>
  );
};
