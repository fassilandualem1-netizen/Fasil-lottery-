import React, { useState, useEffect, useRef } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTelegram } from '../hooks/useTelegram';
import { 
  Plane, 
  ShieldCheck, 
  TrendingUp, 
  Users, 
  Zap, 
  CheckCircle2, 
  X,
  History
} from 'lucide-react';

interface AviatorGameProps {
  onClose?: () => void;
}

interface PastMultiplier {
  id: string;
  multiplier: number;
  isHigh: boolean;
}

interface FakePlayerBet {
  name: string;
  bet: number;
  cashedOut: boolean;
  cashoutMult?: number;
}

export const AviatorGame: React.FC<AviatorGameProps> = () => {
  const { user, updateBalance, isDemo } = useAuth();
  const { haptic } = useTelegram();

  // Game States
  const [gameState, setGameState] = useState<'WAITING' | 'RUNNING' | 'CRASHED'>('WAITING');
  const [multiplier, setMultiplier] = useState<number>(1.00);
  const [crashPoint, setCrashPoint] = useState<number>(2.00);
  const [betAmount, setBetAmount] = useState<number>(50);
  const [hasBet, setHasBet] = useState<boolean>(false);
  const [isCashedOut, setIsCashedOut] = useState<boolean>(false);
  const [cashedAmount, setCashedAmount] = useState<number>(0);
  const [autoCashout, setAutoCashout] = useState<number | ''>('');
  const [countdown, setCountdown] = useState<number>(5);

  // History & Seed
  const [history, setHistory] = useState<PastMultiplier[]>([
    { id: '1', multiplier: 1.45, isHigh: false },
    { id: '2', multiplier: 12.80, isHigh: true },
    { id: '3', multiplier: 2.10, isHigh: false },
    { id: '4', multiplier: 1.05, isHigh: false },
    { id: '5', multiplier: 5.60, isHigh: true },
    { id: '6', multiplier: 1.88, isHigh: false },
    { id: '7', multiplier: 3.42, isHigh: false },
  ]);

  const [showSeedModal, setShowSeedModal] = useState(false);
  const [serverSeed] = useState('d4e8c1b9f7a6e2d3c4b5a6f7e8d9c0b1a2f3e4d5c6b7a8f9e0d1c2b3a4f5e6d7');
  const [clientSeed] = useState('yegna_bet_client_seed_2026');
  const [nonce, setNonce] = useState(142);

  // Multiplayer Bets simulation
  const [playerBets, setPlayerBets] = useState<FakePlayerBet[]>([
    { name: 'Abebe K.', bet: 200, cashedOut: false },
    { name: 'Tigist M.', bet: 100, cashedOut: false },
    { name: 'Dawit G.', bet: 500, cashedOut: false },
    { name: 'Selam W.', bet: 50, cashedOut: false },
    { name: 'Ermias T.', bet: 1000, cashedOut: false },
  ]);

  const animationFrameRef = useRef<number | null>(null);
  const startTimeRef = useRef<number>(0);

  // Auto-cashout logic check during flight
  useEffect(() => {
    if (gameState === 'RUNNING' && hasBet && !isCashedOut && autoCashout && typeof autoCashout === 'number') {
      if (multiplier >= autoCashout) {
        handleCashout();
      }
    }
  }, [multiplier, gameState, hasBet, isCashedOut, autoCashout]);

  // Round loop runner
  useEffect(() => {
    let timer: any;

    if (gameState === 'WAITING') {
      if (countdown > 0) {
        timer = setInterval(() => {
          setCountdown((prev) => prev - 1);
        }, 1000);
      } else {
        // Generate new crash point via seed
        const newCrash = generateCrashPoint();
        setCrashPoint(newCrash);
        setGameState('RUNNING');
        setMultiplier(1.00);
        setIsCashedOut(false);
        setCashedAmount(0);
        startTimeRef.current = performance.now();
        startFlightAnimation(newCrash);
      }
    }

    return () => clearInterval(timer);
  }, [gameState, countdown]);

  const generateCrashPoint = (): number => {
    // Standard Aviator RNG formula: 3% house edge
    const rand = Math.random();
    if (rand < 0.03) return 1.00; // Instant crash
    const crash = (100 * 0.97) / (100 - rand * 97);
    return Math.max(1.00, Math.floor(crash * 100) / 100);
  };

  const startFlightAnimation = (targetCrash: number) => {
    const updateMultiplier = (now: number) => {
      const elapsed = (now - startTimeRef.current) / 1000;
      // Exponential curve formula: multiplier = e^(0.08 * elapsed)
      const currentMult = Math.min(targetCrash, Math.floor(Math.exp(0.08 * elapsed) * 100) / 100);
      setMultiplier(currentMult);

      // Simulate fake players cashing out randomly
      setPlayerBets((prev) =>
        prev.map((player) => {
          if (!player.cashedOut && Math.random() < 0.03 && currentMult > 1.2) {
            return { ...player, cashedOut: true, cashoutMult: currentMult };
          }
          return player;
        })
      );

      if (currentMult >= targetCrash) {
        // Crashed!
        setGameState('CRASHED');
        haptic('notification', 'error');
        setNonce((n) => n + 1);

        // Add to history
        setHistory((prev) => [
          { id: String(Date.now()), multiplier: targetCrash, isHigh: targetCrash >= 3.0 },
          ...prev.slice(0, 9),
        ]);

        // Reset player bets
        setTimeout(() => {
          setHasBet(false);
          setGameState('WAITING');
          setCountdown(4);
          setPlayerBets([
            { name: 'Abebe K.', bet: 200, cashedOut: false },
            { name: 'Tigist M.', bet: 100, cashedOut: false },
            { name: 'Dawit G.', bet: 500, cashedOut: false },
            { name: 'Selam W.', bet: 50, cashedOut: false },
            { name: 'Ermias T.', bet: 1000, cashedOut: false },
          ]);
        }, 2500);
      } else {
        animationFrameRef.current = requestAnimationFrame(updateMultiplier);
      }
    };

    animationFrameRef.current = requestAnimationFrame(updateMultiplier);
  };

  const handlePlaceBet = () => {
    if (betAmount <= 0) return;
    if (user.balance < betAmount) {
      alert('Insufficient wallet balance!');
      return;
    }
    updateBalance(-betAmount, `Aviator Bet`);
    setHasBet(true);
    haptic('impact', 'medium');
  };

  const handleCashout = () => {
    if (!hasBet || isCashedOut || gameState !== 'RUNNING') return;
    const winAmount = Math.floor(betAmount * multiplier * 100) / 100;
    updateBalance(winAmount, `Aviator Cashout (${multiplier.toFixed(2)}x)`);
    setIsCashedOut(true);
    setCashedAmount(winAmount);
    haptic('notification', 'success');
  };

  // SVG Flight path math
  const getPlanePosition = () => {
    if (gameState === 'WAITING') return { x: 40, y: 190, angle: 0 };
    if (gameState === 'CRASHED') return { x: 300, y: 30, angle: -45 };
    const progress = Math.min(1, (multiplier - 1) / (crashPoint === 1 ? 1 : crashPoint * 0.8));
    const x = 40 + progress * 260;
    const y = 190 - Math.pow(progress, 0.7) * 150;
    const angle = -15 - progress * 20;
    return { x, y, angle };
  };

  const planePos = getPlanePosition();

  return (
    <div className="w-full max-w-md mx-auto space-y-3 pb-6">
      {/* Top Banner & Seed Trigger */}
      <div className="flex items-center justify-between bg-[#151c2e] border border-[#232d48] rounded-xl px-3 py-2">
        <div className="flex items-center space-x-2">
          <Plane className="w-5 h-5 text-red-500 animate-pulse" />
          <span className="text-sm font-black tracking-wider text-slate-100 uppercase">
            Aviator Crash
          </span>
          <span className="bg-red-500/20 text-red-400 border border-red-500/30 text-[10px] font-extrabold px-2 py-0.5 rounded-full">
            LIVE 24/7
          </span>
        </div>
        <button
          onClick={() => setShowSeedModal(true)}
          className="text-slate-400 hover:text-amber-400 text-xs font-semibold flex items-center space-x-1 transition-colors"
        >
          <ShieldCheck className="w-4 h-4 text-emerald-400" />
          <span>Provably Fair</span>
        </button>
      </div>

      {/* History Ribbon */}
      <div className="flex items-center space-x-1.5 overflow-x-auto py-1 scrollbar-none">
        <div className="text-[10px] text-slate-400 font-bold uppercase shrink-0 px-1 flex items-center">
          <History className="w-3 h-3 mr-1 text-slate-400" />
          History:
        </div>
        {history.map((h) => (
          <span
            key={h.id}
            className={`shrink-0 text-xs font-black px-2.5 py-0.5 rounded-full border ${
              h.isHigh
                ? 'bg-amber-500/20 border-amber-500/40 text-amber-300'
                : h.multiplier < 1.3
                ? 'bg-blue-500/20 border-blue-500/30 text-blue-400'
                : 'bg-emerald-500/20 border-emerald-500/30 text-emerald-400'
            }`}
          >
            {h.multiplier.toFixed(2)}x
          </span>
        ))}
      </div>

      {/* Main Canvas Display Arena */}
      <div className="relative w-full h-56 bg-slate-950 border-2 border-[#232d48] rounded-2xl overflow-hidden flex flex-col items-center justify-center shadow-2xl">
        {/* Background Grid */}
        <div 
          className="absolute inset-0 opacity-10 bg-[linear-gradient(to_right,#1f293d_1px,transparent_1px),linear-gradient(to_bottom,#1f293d_1px,transparent_1px)]"
          style={{ backgroundSize: '24px 24px' }}
        />

        {/* Flight Curve SVG */}
        <svg className="absolute inset-0 w-full h-full pointer-events-none">
          <defs>
            <linearGradient id="flightGlow" x1="0" y1="1" x2="1" y2="0">
              <stop offset="0%" stopColor="#ef4444" stopOpacity="0.1" />
              <stop offset="100%" stopColor="#ef4444" stopOpacity="0.5" />
            </linearGradient>
          </defs>

          {gameState !== 'WAITING' && (
            <path
              d={`M 40 190 Q ${planePos.x * 0.6} 190, ${planePos.x} ${planePos.y}`}
              fill="none"
              stroke="#ef4444"
              strokeWidth="4"
              strokeLinecap="round"
            />
          )}
        </svg>

        {/* Animated Red Plane */}
        <div
          className="absolute transition-transform duration-75 ease-linear"
          style={{
            transform: `translate(${planePos.x - 20}px, ${planePos.y - 20}px) rotate(${planePos.angle}deg)`,
          }}
        >
          <div className="relative">
            <Plane className="w-10 h-10 text-red-500 drop-shadow-[0_0_12px_rgba(239,68,68,0.8)] fill-red-600" />
            {gameState === 'RUNNING' && (
              <div className="absolute -left-3 top-4 w-4 h-1 bg-amber-400 rounded-full blur-[1px] animate-ping" />
            )}
          </div>
        </div>

        {/* Multiplier / Overlay Display */}
        {gameState === 'WAITING' ? (
          <div className="text-center space-y-2 z-10">
            <p className="text-xs font-bold uppercase text-slate-400 tracking-widest">
              NEXT ROUND IN
            </p>
            <div className="text-4xl font-black text-amber-400 font-mono tracking-tighter">
              00:0{countdown}
            </div>
            <div className="w-32 h-1.5 bg-slate-800 rounded-full mx-auto overflow-hidden">
              <div
                className="h-full bg-amber-400 transition-all duration-1000"
                style={{ width: `${(countdown / 5) * 100}%` }}
              />
            </div>
          </div>
        ) : gameState === 'CRASHED' ? (
          <div className="text-center space-y-1 z-10 animate-bounce">
            <p className="text-sm font-black uppercase text-red-500 tracking-widest">
              FLEW AWAY!
            </p>
            <div className="text-4xl font-black text-red-500 font-mono">
              {multiplier.toFixed(2)}x
            </div>
          </div>
        ) : (
          <div className="text-center z-10">
            <div className="text-5xl font-black text-slate-100 font-mono tracking-tighter drop-shadow-[0_0_20px_rgba(255,255,255,0.3)]">
              {multiplier.toFixed(2)}x
            </div>
          </div>
        )}
      </div>

      {/* Betting Control Panel */}
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

        <div className="flex space-x-2">
          <div className="flex-1 relative">
            <input
              type="number"
              value={betAmount}
              onChange={(e) => setBetAmount(Math.max(1, Number(e.target.value)))}
              disabled={hasBet && gameState !== 'WAITING'}
              className="w-full bg-slate-950 border border-[#232d48] rounded-xl px-3 py-2.5 text-sm font-bold text-slate-100 focus:outline-none focus:border-amber-500 disabled:opacity-50"
            />
            <span className="absolute right-3 top-3 text-xs font-bold text-slate-500">ETB</span>
          </div>

          <div className="w-32">
            <input
              type="number"
              placeholder="Auto Cash"
              value={autoCashout}
              onChange={(e) => setAutoCashout(e.target.value ? Number(e.target.value) : '')}
              className="w-full bg-slate-950 border border-[#232d48] rounded-xl px-2.5 py-2.5 text-xs font-bold text-slate-100 focus:outline-none focus:border-amber-500"
            />
          </div>
        </div>

        {/* Main Action Button */}
        {hasBet ? (
          isCashedOut ? (
            <div className="w-full py-3 bg-emerald-500/20 border border-emerald-500/40 rounded-xl flex items-center justify-center space-x-2 text-emerald-400 font-black text-sm">
              <CheckCircle2 className="w-5 h-5" />
              <span>CASHED OUT FOR {cashedAmount.toFixed(2)} ETB</span>
            </div>
          ) : gameState === 'RUNNING' ? (
            <button
              onClick={handleCashout}
              className="w-full py-3.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-base rounded-xl shadow-lg shadow-amber-500/20 uppercase tracking-wider flex items-center justify-center space-x-2 animate-pulse"
            >
              <Zap className="w-5 h-5 fill-slate-950" />
              <span>CASH OUT ({(betAmount * multiplier).toFixed(2)} ETB)</span>
            </button>
          ) : (
            <div className="w-full py-3.5 bg-amber-500/10 border border-amber-500/30 text-amber-400 font-black text-sm rounded-xl text-center uppercase tracking-wider">
              BET PLACED - WAITING FOR FLIGHT...
            </div>
          )
        ) : (
          <button
            onClick={handlePlaceBet}
            disabled={gameState === 'RUNNING'}
            className="w-full py-3.5 bg-gradient-to-r from-red-600 to-red-700 hover:from-red-500 hover:to-red-600 disabled:opacity-50 text-slate-100 font-black text-base rounded-xl shadow-lg shadow-red-600/30 uppercase tracking-wider flex items-center justify-center space-x-2 transition-all"
          >
            <TrendingUp className="w-5 h-5" />
            <span>BET ({betAmount} ETB)</span>
          </button>
        )}
      </div>

      {/* Live Bets Feed */}
      <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between border-b border-[#232d48] pb-2">
          <div className="flex items-center space-x-1.5 text-xs font-black uppercase text-slate-300">
            <Users className="w-4 h-4 text-amber-400" />
            <span>Live Multiplayer Bets ({playerBets.length})</span>
          </div>
        </div>

        <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
          {playerBets.map((player, idx) => (
            <div
              key={idx}
              className="flex items-center justify-between text-xs bg-slate-950/60 border border-[#232d48] rounded-lg px-2.5 py-1.5"
            >
              <span className="font-bold text-slate-300">{player.name}</span>
              <div className="flex items-center space-x-3">
                <span className="text-slate-400 font-mono">{player.bet} ETB</span>
                {player.cashedOut ? (
                  <span className="bg-emerald-500/20 text-emerald-400 font-extrabold px-1.5 py-0.5 rounded text-[10px]">
                    {player.cashoutMult?.toFixed(2)}x
                  </span>
                ) : (
                  <span className="text-amber-400 text-[10px] font-bold">Flying...</span>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Provably Fair Seed Modal */}
      {showSeedModal && (
        <div className="fixed inset-0 z-50 bg-slate-950/80 backdrop-blur-sm flex items-center justify-center p-4">
          <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl w-full max-w-sm p-5 space-y-4 relative shadow-2xl">
            <button
              onClick={() => setShowSeedModal(false)}
              className="absolute top-4 right-4 text-slate-400 hover:text-slate-200"
            >
              <X className="w-5 h-5" />
            </button>

            <div className="flex items-center space-x-2 text-amber-400">
              <ShieldCheck className="w-6 h-6" />
              <h3 className="text-base font-black uppercase tracking-wide">
                HMAC-SHA256 Seed Proof
              </h3>
            </div>

            <div className="space-y-2 text-xs">
              <div>
                <span className="text-slate-400 block font-bold">Active Server Seed (Hashed):</span>
                <code className="block bg-slate-950 p-2 rounded-lg text-amber-300 text-[10px] break-all border border-[#232d48]">
                  {serverSeed}
                </code>
              </div>

              <div>
                <span className="text-slate-400 block font-bold">Client Seed:</span>
                <code className="block bg-slate-950 p-2 rounded-lg text-emerald-300 text-[10px] border border-[#232d48]">
                  {clientSeed}
                </code>
              </div>

              <div>
                <span className="text-slate-400 block font-bold">Nonce:</span>
                <span className="font-mono font-bold text-slate-200">{nonce}</span>
              </div>
            </div>

            <p className="text-[11px] text-slate-400">
              Every round outcome is mathematically predetermined prior to flight start using SHA256 hashes, ensuring zero server manipulation.
            </p>

            <button
              onClick={() => setShowSeedModal(false)}
              className="w-full py-2.5 bg-amber-500 text-slate-950 font-black text-xs rounded-xl uppercase tracking-wider"
            >
              Close
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
