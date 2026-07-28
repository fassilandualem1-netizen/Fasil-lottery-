/**
 * Yegna Bet - Custom React Hook for Synchronized Loop Games
 * Consumes 24/7 infinite server-synchronized round state derived from Unix Epoch time (Date.now()),
 * live multiplayer bets, provably fair seed hashes, and handles user bet placement & cashouts
 * across all 7 games (Aviator, Virtual Sport, Keno, Coinflip, Mines, Dice, Color Wheel).
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { collection, query, where, onSnapshot, doc, setDoc } from 'firebase/firestore';
import { db } from '../firebase/config';
import { useAuth } from '../context/AuthContext';
import { 
  LoopGameType, 
  LoopRound, 
  MultiplayerBet, 
  LoopState 
} from '../types';
import { 
  getDeterministicRoundInfo,
  generatePreRoundOutcomeForRoundIndex,
  settleRoundBets,
  placeLoopBet, 
  cashOutLoopBet,
  RoundOutcomeResult
} from '../engine/loopEngine';

export function useLoopGame(gameId: LoopGameType) {
  const { user, userData } = useAuth();
  const [round, setRound] = useState<LoopRound | null>(null);
  const [timeLeft, setTimeLeft] = useState<number>(10);
  const [activeBets, setActiveBets] = useState<MultiplayerBet[]>([]);
  const [userBet, setUserBet] = useState<MultiplayerBet | null>(null);

  const outcomeCacheRef = useRef<Map<string, RoundOutcomeResult>>(new Map());
  const settledRoundsRef = useRef<Set<string>>(new Set());

  // 1. Continuous High-Precision 24/7 Timer Loop (runs every 100ms)
  useEffect(() => {
    let active = true;

    const updateLoop = async () => {
      const now = Date.now();
      const info = getDeterministicRoundInfo(gameId, now);
      const cacheKey = `${gameId}:${info.roundIndex}`;

      let outcomeRes = outcomeCacheRef.current.get(cacheKey);
      if (!outcomeRes) {
        outcomeRes = await generatePreRoundOutcomeForRoundIndex(gameId, info.roundIndex);
        if (active) {
          outcomeCacheRef.current.set(cacheKey, outcomeRes);
          if (outcomeCacheRef.current.size > 20) {
            outcomeCacheRef.current.clear();
            outcomeCacheRef.current.set(cacheKey, outcomeRes);
          }
        }
      }

      if (!active) return;

      const currentRoundObj: LoopRound = {
        roundId: info.roundId,
        gameId,
        state: info.state,
        serverSeedHash: outcomeRes.serverSeedHash,
        ...(info.state === 'RESOLVED' || info.state === 'COOLDOWN' ? { serverSeed: outcomeRes.serverSeed } : {}),
        outcome: outcomeRes.data,
        bettingEndsAt: info.bettingEndsAt,
        gameEndsAt: info.gameEndsAt,
        cooldownEndsAt: info.cooldownEndsAt,
        createdAt: new Date(info.cycleStartAt).toISOString(),
      };

      setRound(currentRoundObj);
      setTimeLeft(info.timeLeftSeconds);

      // Optionally sync current active loop to Firestore for cross-client inspection
      if (info.state === 'BETTING' && info.elapsedMsInPhase < 1000) {
        setDoc(doc(db, 'game_loops', gameId), currentRoundObj, { merge: true }).catch(() => {});
      }

      // Trigger Mass Settlement when entering RESOLVED state
      if (info.state === 'RESOLVED' && !settledRoundsRef.current.has(info.roundId)) {
        settledRoundsRef.current.add(info.roundId);
        settleRoundBets(gameId, info.roundId, outcomeRes.data);
      }
    };

    updateLoop();
    const intervalId = setInterval(updateLoop, 100);

    return () => {
      active = false;
      clearInterval(intervalId);
    };
  }, [gameId]);

  // 2. Live Multiplayer Bets Registry Snapshot Listener
  useEffect(() => {
    if (!round?.roundId) {
      setActiveBets([]);
      setUserBet(null);
      return;
    }

    const betsRef = collection(db, 'loop_bets');
    const q = query(betsRef, where('roundId', '==', round.roundId));

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const betsList: MultiplayerBet[] = [];
        let currentMyBet: MultiplayerBet | null = null;

        snapshot.forEach((docSnap) => {
          const betData = { id: docSnap.id, ...docSnap.data() } as MultiplayerBet;
          betsList.push(betData);

          if (user && betData.userId === user.uid) {
            currentMyBet = betData;
          }
        });

        // Sort bets descending by bet amount for live leaderboard
        betsList.sort((a, b) => b.betAmount - a.betAmount);

        setActiveBets(betsList);
        setUserBet(currentMyBet);
      },
      (error) => {
        console.warn(`Live bets listener notice for ${gameId}:`, error.message);
      }
    );

    return () => unsubscribe();
  }, [round?.roundId, user]);

  // 3. Action: Place Bet
  const handlePlaceBet = useCallback(
    async (betAmount: number, gameData?: Record<string, any>) => {
      if (!userData) {
        throw new Error('Please log in or create an account to place bets.');
      }

      if (round?.state !== 'BETTING') {
        throw new Error('Betting window is closed for this round. Wait for next round.');
      }

      if (!round?.roundId) {
        throw new Error('Round not initialized.');
      }

      const res = await placeLoopBet(gameId, round.roundId, userData, betAmount, gameData);
      if (!res.success) {
        throw new Error(res.error || 'Failed to place bet.');
      }

      return res;
    },
    [gameId, round, userData]
  );

  // 4. Action: Cash Out (e.g. Aviator, Mines)
  const handleCashOut = useCallback(
    async (currentMultiplier: number) => {
      if (!user) {
        throw new Error('User not logged in.');
      }

      if (!userBet) {
        throw new Error('No active bet found in this round.');
      }

      if (userBet.status !== 'BETTING') {
        throw new Error('Bet has already been cashed out or resolved.');
      }

      const res = await cashOutLoopBet(userBet.id, user.uid, currentMultiplier);
      if (!res.success) {
        throw new Error(res.error || 'Cashout failed.');
      }

      return res;
    },
    [user, userBet]
  );

  const state: LoopState = round?.state || 'BETTING';

  return {
    round,
    state,
    timeLeft,
    serverSeedHash: round?.serverSeedHash || '',
    serverSeed: round?.serverSeed || null,
    outcome: round?.outcome || null,
    activeBets,
    userBet,
    placeBet: handlePlaceBet,
    cashOut: handleCashOut,
    isBetting: state === 'BETTING',
    isInGame: state === 'IN_GAME',
    isResolved: state === 'RESOLVED',
    isCooldown: state === 'COOLDOWN',
  };
}

export default useLoopGame;
