import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTelegram } from '../hooks/useTelegram';
import { 
  Trophy, 
  Play, 
  FastForward, 
  CheckCircle2, 
  Zap, 
  Flame,
  Volume2
} from 'lucide-react';

interface Match {
  id: string;
  homeTeam: string;
  awayTeam: string;
  homeOdds: number;
  drawOdds: number;
  awayOdds: number;
  over25Odds: number;
  bttsOdds: number;
  status: 'UPCOMING' | 'LIVE' | 'FINISHED';
  homeScore: number;
  awayScore: number;
  minute: number;
  commentary: string[];
}

const INITIAL_MATCHES: Match[] = [
  {
    id: 'm1',
    homeTeam: 'Saint George S.C.',
    awayTeam: 'Fasil Kenema S.C.',
    homeOdds: 2.10,
    drawOdds: 3.20,
    awayOdds: 3.40,
    over25Odds: 1.95,
    bttsOdds: 1.85,
    status: 'UPCOMING',
    homeScore: 0,
    awayScore: 0,
    minute: 0,
    commentary: ['Teams taking the pitch at Addis Ababa Stadium'],
  },
  {
    id: 'm2',
    homeTeam: 'Ethiopian Bunna',
    awayTeam: 'Bahir Dar Kenema',
    homeOdds: 2.30,
    drawOdds: 3.10,
    awayOdds: 2.90,
    over25Odds: 2.10,
    bttsOdds: 1.75,
    status: 'UPCOMING',
    homeScore: 0,
    awayScore: 0,
    minute: 0,
    commentary: ['Match kickoff delayed 2 minutes'],
  },
  {
    id: 'm3',
    homeTeam: 'Adama City',
    awayTeam: 'Sidama Bunna',
    homeOdds: 1.85,
    drawOdds: 3.40,
    awayOdds: 4.20,
    over25Odds: 2.20,
    bttsOdds: 1.90,
    status: 'UPCOMING',
    homeScore: 0,
    awayScore: 0,
    minute: 0,
    commentary: ['Ideal pitch conditions'],
  },
];

export const VirtualSportsGame: React.FC = () => {
  const { user, updateBalance, isDemo } = useAuth();
  const { haptic } = useTelegram();

  const [matches, setMatches] = useState<Match[]>(INITIAL_MATCHES);
  const [selectedMatch, setSelectedMatch] = useState<Match>(INITIAL_MATCHES[0]);
  const [betSelection, setBetSelection] = useState<{ type: string; odds: number; label: string } | null>(null);
  const [betAmount, setBetAmount] = useState<number>(100);
  const [isSimulating, setIsSimulating] = useState<boolean>(false);
  const [betPlaced, setBetPlaced] = useState<boolean>(false);
  const [matchResult, setMatchResult] = useState<{ won: boolean; winAmount: number } | null>(null);

  const handleSelectOdd = (type: string, odds: number, label: string) => {
    if (isSimulating) return;
    setBetSelection({ type, odds, label });
    haptic('selection');
  };

  const handlePlaceBet = () => {
    if (!betSelection) return;
    if (user.balance < betAmount) {
      alert('Insufficient wallet balance!');
      return;
    }

    updateBalance(-betAmount, `Virtual Football Bet: ${betSelection.label} @ ${betSelection.odds}x`);
    setBetPlaced(true);
    setMatchResult(null);
    haptic('impact', 'medium');
  };

  const startSimulation = () => {
    if (!betPlaced) return;
    setIsSimulating(true);

    let homeGoals = 0;
    let awayGoals = 0;
    let min = 0;

    const commentaryEvents = [
      'Great pass through the midfield!',
      'Shot saved by the goalkeeper!',
      'Header hits the crossbar!',
      'GOALLL!! Spectacular finish!',
      'Yellow card shown for a late tackle.',
      'Foul near the penalty arc.',
    ];

    const timer = setInterval(() => {
      min += 15;
      if (Math.random() < 0.35) homeGoals += 1;
      if (Math.random() < 0.30) awayGoals += 1;

      const randomComment = commentaryEvents[Math.floor(Math.random() * commentaryEvents.length)];

      setSelectedMatch((prev) => ({
        ...prev,
        status: min >= 90 ? 'FINISHED' : 'LIVE',
        minute: Math.min(90, min),
        homeScore: homeGoals,
        awayScore: awayGoals,
        commentary: [`${min}' - ${randomComment}`, ...prev.commentary],
      }));

      haptic('impact', 'light');

      if (min >= 90) {
        clearInterval(timer);
        setIsSimulating(false);

        // Evaluate bet outcome
        let won = false;
        if (betSelection?.type === 'HOME' && homeGoals > awayGoals) won = true;
        if (betSelection?.type === 'DRAW' && homeGoals === awayGoals) won = true;
        if (betSelection?.type === 'AWAY' && awayGoals > homeGoals) won = true;
        if (betSelection?.type === 'OVER25' && homeGoals + awayGoals > 2.5) won = true;
        if (betSelection?.type === 'BTTS' && homeGoals > 0 && awayGoals > 0) won = true;

        const winAmount = won ? Math.floor(betAmount * betSelection!.odds * 100) / 100 : 0;

        if (won) {
          updateBalance(winAmount, `Virtual Football Win: ${selectedMatch.homeTeam} vs ${selectedMatch.awayTeam}`);
          haptic('notification', 'success');
        } else {
          haptic('notification', 'error');
        }

        setMatchResult({ won, winAmount });
      }
    }, 800);
  };

  const handleResetMatch = () => {
    setSelectedMatch({
      ...INITIAL_MATCHES[0],
      id: String(Date.now()),
    });
    setBetSelection(null);
    setBetPlaced(false);
    setMatchResult(null);
    setIsSimulating(false);
  };

  return (
    <div className="w-full max-w-md mx-auto space-y-3 pb-6">
      {/* Header Banner */}
      <div className="flex items-center justify-between bg-[#151c2e] border border-[#232d48] rounded-xl px-3 py-2">
        <div className="flex items-center space-x-2">
          <Trophy className="w-5 h-5 text-amber-400" />
          <span className="text-sm font-black tracking-wider text-slate-100 uppercase">
            Virtual Premier League
          </span>
        </div>
        <span className="bg-emerald-500/20 text-emerald-400 text-[10px] font-extrabold px-2 py-0.5 rounded-full border border-emerald-500/30">
          3 MIN ROUNDS
        </span>
      </div>

      {/* Match Display Stadium Scoreboard */}
      <div className="relative bg-gradient-to-b from-slate-950 to-[#0e1424] border-2 border-[#232d48] rounded-2xl p-4 space-y-3 shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between text-xs font-bold text-slate-400">
          <span>ETHIOPIAN PREMIER LEAGUE</span>
          <span className="flex items-center text-red-400 animate-pulse">
            <Flame className="w-3.5 h-3.5 mr-1" />
            {selectedMatch.status === 'LIVE' ? `${selectedMatch.minute}' LIVE` : selectedMatch.status}
          </span>
        </div>

        {/* Score Board */}
        <div className="flex items-center justify-between py-2 border-y border-[#232d48]/60">
          <div className="flex-1 text-center space-y-1">
            <div className="w-12 h-12 mx-auto rounded-full bg-slate-900 border border-[#232d48] flex items-center justify-center text-base font-black text-amber-400 shadow-md">
              SG
            </div>
            <div className="text-xs font-black text-slate-100">{selectedMatch.homeTeam}</div>
          </div>

          <div className="px-4 text-center">
            <div className="text-3xl font-black text-amber-400 font-mono tracking-wider">
              {selectedMatch.homeScore} - {selectedMatch.awayScore}
            </div>
            <span className="text-[10px] text-slate-500 font-bold uppercase">VS</span>
          </div>

          <div className="flex-1 text-center space-y-1">
            <div className="w-12 h-12 mx-auto rounded-full bg-slate-900 border border-[#232d48] flex items-center justify-center text-base font-black text-red-400 shadow-md">
              FK
            </div>
            <div className="text-xs font-black text-slate-100">{selectedMatch.awayTeam}</div>
          </div>
        </div>

        {/* Live Commentary Feed */}
        <div className="bg-slate-950/80 border border-[#232d48] rounded-xl p-2.5 max-h-20 overflow-y-auto space-y-1">
          {selectedMatch.commentary.map((c, i) => (
            <p key={i} className="text-[11px] text-slate-300 font-medium flex items-center">
              <Volume2 className="w-3 h-3 mr-1 text-amber-400 shrink-0" />
              {c}
            </p>
          ))}
        </div>
      </div>

      {/* Betting Markets Grid */}
      <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-xs font-bold uppercase text-slate-400">Match Betting Odds</span>
          <span className="text-xs font-bold text-amber-400">1X2 & Goal Markets</span>
        </div>

        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => handleSelectOdd('HOME', selectedMatch.homeOdds, `${selectedMatch.homeTeam} Win`)}
            disabled={betPlaced}
            className={`p-2.5 rounded-xl border text-center transition-all ${
              betSelection?.type === 'HOME'
                ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                : 'bg-slate-950 border-[#232d48] text-slate-200 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] text-slate-400 font-bold">1 (Home)</div>
            <div className="text-sm font-black">{selectedMatch.homeOdds}x</div>
          </button>

          <button
            onClick={() => handleSelectOdd('DRAW', selectedMatch.drawOdds, 'Match Draw')}
            disabled={betPlaced}
            className={`p-2.5 rounded-xl border text-center transition-all ${
              betSelection?.type === 'DRAW'
                ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                : 'bg-slate-950 border-[#232d48] text-slate-200 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] text-slate-400 font-bold">X (Draw)</div>
            <div className="text-sm font-black">{selectedMatch.drawOdds}x</div>
          </button>

          <button
            onClick={() => handleSelectOdd('AWAY', selectedMatch.awayOdds, `${selectedMatch.awayTeam} Win`)}
            disabled={betPlaced}
            className={`p-2.5 rounded-xl border text-center transition-all ${
              betSelection?.type === 'AWAY'
                ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                : 'bg-slate-950 border-[#232d48] text-slate-200 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] text-slate-400 font-bold">2 (Away)</div>
            <div className="text-sm font-black">{selectedMatch.awayOdds}x</div>
          </button>
        </div>

        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => handleSelectOdd('OVER25', selectedMatch.over25Odds, 'Over 2.5 Goals')}
            disabled={betPlaced}
            className={`p-2 rounded-xl border text-center transition-all ${
              betSelection?.type === 'OVER25'
                ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                : 'bg-slate-950 border-[#232d48] text-slate-200 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] text-slate-400 font-bold">Over 2.5 Goals</div>
            <div className="text-xs font-black">{selectedMatch.over25Odds}x</div>
          </button>

          <button
            onClick={() => handleSelectOdd('BTTS', selectedMatch.bttsOdds, 'Both Teams To Score')}
            disabled={betPlaced}
            className={`p-2 rounded-xl border text-center transition-all ${
              betSelection?.type === 'BTTS'
                ? 'bg-amber-500/20 border-amber-500 text-amber-400'
                : 'bg-slate-950 border-[#232d48] text-slate-200 hover:border-slate-700'
            }`}
          >
            <div className="text-[10px] text-slate-400 font-bold">Both Teams Score</div>
            <div className="text-xs font-black">{selectedMatch.bttsOdds}x</div>
          </button>
        </div>
      </div>

      {/* Bet Slip & Match Controls */}
      <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 space-y-3">
        {betSelection && (
          <div className="bg-slate-950 border border-[#232d48] p-3 rounded-xl flex items-center justify-between text-xs">
            <div>
              <span className="text-slate-400 block font-bold">Selection:</span>
              <span className="font-black text-amber-400">{betSelection.label}</span>
            </div>
            <div className="text-right">
              <span className="text-slate-400 block font-bold">Odds / Payout:</span>
              <span className="font-black text-emerald-400">
                {(betAmount * betSelection.odds).toFixed(2)} ETB ({betSelection.odds}x)
              </span>
            </div>
          </div>
        )}

        {!betPlaced ? (
          <button
            onClick={handlePlaceBet}
            disabled={!betSelection}
            className="w-full py-3.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 disabled:opacity-50 text-slate-950 font-black text-base rounded-xl shadow-lg uppercase tracking-wider flex items-center justify-center space-x-2"
          >
            <Zap className="w-5 h-5 fill-slate-950" />
            <span>PLACE MATCH BET ({betAmount} ETB)</span>
          </button>
        ) : selectedMatch.status === 'FINISHED' ? (
          <div className="space-y-2">
            <div
              className={`p-3 rounded-xl text-center font-black text-sm border ${
                matchResult?.won
                  ? 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400'
                  : 'bg-red-500/20 border-red-500/40 text-red-400'
              }`}
            >
              {matchResult?.won
                ? `YOU WON +${matchResult.winAmount} ETB!`
                : 'MATCH LOST - BETTER LUCK NEXT TIME!'}
            </div>
            <button
              onClick={handleResetMatch}
              className="w-full py-2.5 bg-slate-900 border border-[#232d48] text-slate-300 font-bold text-xs rounded-xl uppercase"
            >
              Next Virtual Match
            </button>
          </div>
        ) : (
          <button
            onClick={startSimulation}
            disabled={isSimulating}
            className="w-full py-3.5 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-slate-950 font-black text-base rounded-xl shadow-lg uppercase tracking-wider flex items-center justify-center space-x-2 animate-pulse"
          >
            <Play className="w-5 h-5 fill-slate-950" />
            <span>{isSimulating ? 'SIMULATING MATCH...' : 'KICKOFF MATCH SIMULATION'}</span>
          </button>
        )}
      </div>
    </div>
  );
};
