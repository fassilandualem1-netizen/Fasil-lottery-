/**
 * Yegna Bet - Global Multiplayer Loop Game Engine
 * Synchronized 24/7 infinite round-based state machine (BETTING -> IN_GAME -> RESOLVED -> COOLDOWN)
 * for Aviator, Virtual Sport, Keno, Coinflip, Mines, Classic Dice, and Color Wheel.
 * 
 * Features:
 * 1. Global Timestamp Synchronization based on absolute Unix Epoch Time (Date.now())
 * 2. Deterministic Provably Fair outcome generation (HMAC-SHA256 seed hash)
 * 3. Zero-player continuous operation (rounds advance continuously 24/7)
 * 4. Mass settlement execution with atomic balance updates
 */

import { 
  doc, 
  setDoc, 
  updateDoc, 
  collection, 
  query, 
  where, 
  getDocs, 
  runTransaction, 
  serverTimestamp 
} from 'firebase/firestore';
import { db } from '../firebase/config';
import { 
  hashServerSeed, 
  getProvableCrashMultiplier, 
  getProvableCoinflip, 
  getGameOutcome,
  getProvableMinesGrid,
  getProvableDiceRoll
} from './provablyFair';
import { validateBet } from './riskManager';
import { LoopState, LoopGameType, LoopRound, MultiplayerBet, UserProfile } from '../types';

// Configuration for Round Cycle Timers (in milliseconds)
export const GAME_CYCLE_CONFIG: Record<LoopGameType, {
  bettingMs: number;
  inGameMs: number;
  resolvedMs: number;
  cooldownMs: number;
  totalCycleMs: number;
}> = {
  aviator: { bettingMs: 10000, inGameMs: 8000, resolvedMs: 3000, cooldownMs: 3000, totalCycleMs: 24000 },
  virtual_sport: { bettingMs: 10000, inGameMs: 8000, resolvedMs: 3000, cooldownMs: 3000, totalCycleMs: 24000 },
  keno: { bettingMs: 10000, inGameMs: 6000, resolvedMs: 3000, cooldownMs: 3000, totalCycleMs: 22000 },
  coinflip: { bettingMs: 10000, inGameMs: 4000, resolvedMs: 3000, cooldownMs: 3000, totalCycleMs: 20000 },
  mines: { bettingMs: 10000, inGameMs: 6000, resolvedMs: 3000, cooldownMs: 3000, totalCycleMs: 22000 },
  dice: { bettingMs: 10000, inGameMs: 5000, resolvedMs: 3000, cooldownMs: 3000, totalCycleMs: 21000 },
  color_wheel: { bettingMs: 10000, inGameMs: 6000, resolvedMs: 3000, cooldownMs: 3000, totalCycleMs: 22000 },
};

export interface DeterministicRoundInfo {
  roundIndex: number;
  roundId: string;
  gameId: LoopGameType;
  state: LoopState;
  elapsedMsInPhase: number;
  timeLeftSeconds: number;
  bettingEndsAt: number;
  gameEndsAt: number;
  cooldownEndsAt: number;
  cycleStartAt: number;
}

export interface RoundOutcomeResult {
  serverSeed: string;
  serverSeedHash: string;
  clientSeed: string;
  nonce: number;
  data: any;
}

/**
 * Deterministically calculate current round state from absolute Unix Epoch time
 */
export function getDeterministicRoundInfo(
  gameId: LoopGameType,
  now: number = Date.now()
): DeterministicRoundInfo {
  const config = GAME_CYCLE_CONFIG[gameId] || GAME_CYCLE_CONFIG.aviator;
  const roundIndex = Math.floor(now / config.totalCycleMs);
  const roundId = `RND-${gameId}-${roundIndex}`;
  const cycleStartAt = roundIndex * config.totalCycleMs;
  const elapsedInCycle = now - cycleStartAt;

  const bettingEndsAt = cycleStartAt + config.bettingMs;
  const gameEndsAt = bettingEndsAt + config.inGameMs;
  const cooldownEndsAt = cycleStartAt + config.totalCycleMs;

  let state: LoopState = 'BETTING';
  let timeLeftSeconds = 0;
  let elapsedMsInPhase = 0;

  if (elapsedInCycle < config.bettingMs) {
    state = 'BETTING';
    elapsedMsInPhase = elapsedInCycle;
    timeLeftSeconds = Math.max(0, Math.ceil((config.bettingMs - elapsedInCycle) / 1000));
  } else if (elapsedInCycle < config.bettingMs + config.inGameMs) {
    state = 'IN_GAME';
    elapsedMsInPhase = elapsedInCycle - config.bettingMs;
    timeLeftSeconds = Math.max(0, Math.ceil((config.bettingMs + config.inGameMs - elapsedInCycle) / 1000));
  } else if (elapsedInCycle < config.bettingMs + config.inGameMs + config.resolvedMs) {
    state = 'RESOLVED';
    elapsedMsInPhase = elapsedInCycle - config.bettingMs - config.inGameMs;
    timeLeftSeconds = Math.max(0, Math.ceil((config.bettingMs + config.inGameMs + config.resolvedMs - elapsedInCycle) / 1000));
  } else {
    state = 'COOLDOWN';
    elapsedMsInPhase = elapsedInCycle - config.bettingMs - config.inGameMs - config.resolvedMs;
    timeLeftSeconds = Math.max(0, Math.ceil((config.totalCycleMs - elapsedInCycle) / 1000));
  }

  return {
    roundIndex,
    roundId,
    gameId,
    state,
    elapsedMsInPhase,
    timeLeftSeconds,
    bettingEndsAt,
    gameEndsAt,
    cooldownEndsAt,
    cycleStartAt,
  };
}

const seedCache = new Map<string, string>();

/**
 * Deterministically generate a 64-char hex server seed for a given game and round index
 */
export async function getDeterministicServerSeed(gameId: string, roundIndex: number): Promise<string> {
  const key = `${gameId}:${roundIndex}`;
  if (seedCache.has(key)) return seedCache.get(key)!;

  let seedHex = '';
  if (typeof crypto !== 'undefined' && crypto.subtle) {
    const encoder = new TextEncoder();
    const data = encoder.encode(`YEGNA_SEED:${gameId}:${roundIndex}`);
    const hashBuffer = await crypto.subtle.digest('SHA-256', data);
    const hashArray = Array.from(new Uint8Array(hashBuffer));
    seedHex = hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
  } else {
    let h1 = 0x811c9dc5;
    let h2 = 0x09dc5811;
    const str = `YEGNA_SEED:${gameId}:${roundIndex}`;
    for (let i = 0; i < str.length; i++) {
      const ch = str.charCodeAt(i);
      h1 = Math.imul(h1 ^ ch, 16777619);
      h2 = Math.imul(h2 ^ ch, 2246822519);
    }
    seedHex = ((h1 >>> 0).toString(16) + (h2 >>> 0).toString(16)).padStart(64, 'a');
  }

  if (seedCache.size > 100) seedCache.clear();
  seedCache.set(key, seedHex);
  return seedHex;
}

/**
 * Pre-calculate provably fair outcome deterministically for any round index worldwide
 */
export async function generatePreRoundOutcomeForRoundIndex(
  gameId: LoopGameType,
  roundIndex: number
): Promise<RoundOutcomeResult> {
  const serverSeed = await getDeterministicServerSeed(gameId, roundIndex);
  const serverSeedHash = await hashServerSeed(serverSeed);
  const clientSeed = `CLIENT-SEED-${gameId}`;
  const nonce = roundIndex;

  let data: any = {};

  switch (gameId) {
    case 'aviator': {
      const multiplier = await getProvableCrashMultiplier(serverSeed, clientSeed, nonce, 0.03);
      data = { crashMultiplier: multiplier };
      break;
    }
    case 'keno': {
      const drawn: number[] = [];
      let currentNonce = nonce;
      while (drawn.length < 20) {
        const float = await getGameOutcome(serverSeed, clientSeed, currentNonce);
        const num = Math.floor(float * 80) + 1;
        if (!drawn.includes(num)) {
          drawn.push(num);
        }
        currentNonce++;
      }
      drawn.sort((a, b) => a - b);
      data = { drawnNumbers: drawn };
      break;
    }
    case 'coinflip': {
      const outcome = await getProvableCoinflip(serverSeed, clientSeed, nonce);
      data = { outcome }; // 'HEADS' | 'TAILS'
      break;
    }
    case 'virtual_sport': {
      const float1 = await getGameOutcome(serverSeed, clientSeed, nonce);
      const float2 = await getGameOutcome(serverSeed, clientSeed, nonce + 1);
      const homeScore = Math.floor(float1 * 5);
      const awayScore = Math.floor(float2 * 5);
      const winner = homeScore > awayScore ? 'HOME' : awayScore > homeScore ? 'AWAY' : 'DRAW';
      data = { homeScore, awayScore, winner };
      break;
    }
    case 'mines': {
      const minesGrid = await getProvableMinesGrid(serverSeed, clientSeed, nonce, 25, 3);
      data = { minesGrid };
      break;
    }
    case 'dice': {
      const rolledValue = await getProvableDiceRoll(serverSeed, clientSeed, nonce);
      data = { rolledValue };
      break;
    }
    case 'color_wheel': {
      const float = await getGameOutcome(serverSeed, clientSeed, nonce);
      const sectorIdx = Math.floor(float * 16);
      let sector: 'RED' | 'BLACK' | 'GREEN' | 'GOLD' = 'RED';
      let multiplier = 2;
      if (sectorIdx < 7) {
        sector = 'RED';
        multiplier = 2;
      } else if (sectorIdx < 14) {
        sector = 'BLACK';
        multiplier = 2;
      } else if (sectorIdx === 14) {
        sector = 'GREEN';
        multiplier = 14;
      } else {
        sector = 'GOLD';
        multiplier = 14;
      }
      data = { sector, sectorIdx, multiplier };
      break;
    }
  }

  return {
    serverSeed,
    serverSeedHash,
    clientSeed,
    nonce,
    data,
  };
}

/**
 * Mass Settlement Execution for all bets placed in a round
 */
export async function settleRoundBets(
  gameId: LoopGameType,
  roundId: string,
  outcome: any
): Promise<void> {
  try {
    const betsRef = collection(db, 'loop_bets');
    const q = query(betsRef, where('roundId', '==', roundId));
    const snap = await getDocs(q);

    if (snap.empty) return; // Zero players handling: exit cleanly

    for (const docSnap of snap.docs) {
      const bet = docSnap.data() as MultiplayerBet;
      if (bet.status !== 'BETTING' && bet.status !== 'CASHOUT') continue;

      let won = false;
      let payout = 0;
      let status: MultiplayerBet['status'] = 'LOST';
      let cashedOutMult = bet.cashedOutAtMultiplier || 0;

      switch (gameId) {
        case 'aviator': {
          const crashMultiplier = outcome?.crashMultiplier || 1.0;
          if (bet.status === 'CASHOUT' && cashedOutMult <= crashMultiplier) {
            won = true;
            payout = bet.payout;
            status = 'WON';
          } else {
            won = false;
            payout = 0;
            status = 'LOST';
          }
          break;
        }
        case 'keno': {
          const drawn = outcome?.drawnNumbers || [];
          const selected = bet.gameData?.selectedNumbers || [];
          const matches = selected.filter((num: number) => drawn.includes(num)).length;
          
          let multiplier = 0;
          if (selected.length === 5) {
            if (matches === 5) multiplier = 50;
            else if (matches === 4) multiplier = 10;
            else if (matches === 3) multiplier = 3;
            else if (matches === 2) multiplier = 1;
          } else {
            if (matches >= 1) multiplier = matches * 1.8;
          }

          if (multiplier > 0) {
            won = true;
            payout = Math.round(bet.betAmount * multiplier * 100) / 100;
            status = 'WON';
          }
          break;
        }
        case 'coinflip': {
          const actualSide = outcome?.outcome;
          const chosenSide = bet.gameData?.chosenSide;
          if (actualSide && chosenSide && actualSide === chosenSide) {
            won = true;
            payout = Math.round(bet.betAmount * 1.96 * 100) / 100;
            status = 'WON';
          }
          break;
        }
        case 'virtual_sport': {
          const actualWinner = outcome?.winner;
          const chosenPick = bet.gameData?.chosenPick;
          if (actualWinner && chosenPick && actualWinner === chosenPick) {
            won = true;
            const odds = bet.gameData?.odds || 2.0;
            payout = Math.round(bet.betAmount * odds * 100) / 100;
            status = 'WON';
          }
          break;
        }
        case 'mines': {
          const safeHits = bet.gameData?.safeHitsCount || 0;
          if (bet.status === 'CASHOUT' || (safeHits > 0 && !bet.gameData?.hitMine)) {
            won = true;
            const mult = Math.pow(1.15, safeHits);
            payout = Math.round(bet.betAmount * mult * 100) / 100;
            status = 'WON';
          }
          break;
        }
        case 'dice': {
          const rolled = outcome?.rolledValue ?? 50.0;
          const target = bet.gameData?.targetValue ?? 50.0;
          const mode = bet.gameData?.mode || 'UNDER';
          if ((mode === 'UNDER' && rolled < target) || (mode === 'OVER' && rolled > target)) {
            won = true;
            const winChance = mode === 'UNDER' ? target : (100 - target);
            const mult = Math.max(1.01, Math.min(99, (98 / winChance)));
            payout = Math.round(bet.betAmount * mult * 100) / 100;
            status = 'WON';
          }
          break;
        }
        case 'color_wheel': {
          const actualSector = outcome?.sector;
          const chosenColor = bet.gameData?.chosenColor;
          if (actualSector && chosenColor && actualSector === chosenColor) {
            won = true;
            const mult = outcome?.multiplier || 2;
            payout = Math.round(bet.betAmount * mult * 100) / 100;
            status = 'WON';
          }
          break;
        }
      }

      try {
        await runTransaction(db, async (transaction) => {
          const betDocRef = doc(db, 'loop_bets', docSnap.id);
          const userRef = doc(db, 'users', bet.userId);

          const userSnap = await transaction.get(userRef);

          if (won && payout > 0 && userSnap.exists()) {
            const userData = userSnap.data() as UserProfile;
            const updatedBal = (userData.balance || 0) + payout;
            transaction.update(userRef, {
              balance: updatedBal,
              updatedAt: serverTimestamp(),
            });
          }

          transaction.update(betDocRef, {
            status,
            payout,
            resolvedAt: new Date().toISOString(),
          });
        });
      } catch (err) {
        console.warn(`Error settling bet ${docSnap.id}:`, err);
        try {
          await updateDoc(doc(db, 'loop_bets', docSnap.id), { status, payout });
        } catch (e) {}
      }
    }
  } catch (error) {
    console.warn('Mass settlement error:', error);
  }
}

/**
 * Place a multiplayer bet in the current active round
 */
export async function placeLoopBet(
  gameId: LoopGameType,
  roundId: string,
  user: UserProfile,
  betAmount: number,
  gameData?: Record<string, any>
): Promise<{ success: boolean; betId?: string; error?: string }> {
  const val = validateBet(betAmount, user.balance);
  if (!val.valid) {
    return { success: false, error: val.reason || 'Invalid bet parameters.' };
  }

  const betRef = doc(collection(db, 'loop_bets'));
  const betId = betRef.id;

  try {
    await runTransaction(db, async (transaction) => {
      const userRef = doc(db, 'users', user.uid);
      const userSnap = await transaction.get(userRef);

      if (!userSnap.exists()) {
        throw new Error('User profile not found.');
      }

      const userData = userSnap.data() as UserProfile;
      if (userData.balance < betAmount) {
        throw new Error('Insufficient balance for this bet.');
      }

      transaction.update(userRef, {
        balance: userData.balance - betAmount,
        totalWagered: (userData.totalWagered || 0) + betAmount,
        updatedAt: serverTimestamp(),
      });

      const loopBet: MultiplayerBet = {
        id: betId,
        roundId,
        gameId,
        userId: user.uid,
        displayName: user.displayName || 'Player',
        sixDigitId: user.sixDigitId || 'YG-GUEST',
        betAmount,
        gameData: gameData || {},
        status: 'BETTING',
        payout: 0,
        createdAt: new Date().toISOString(),
      };

      transaction.set(betRef, loopBet);
    });

    return { success: true, betId };
  } catch (err: any) {
    console.warn('Loop bet placement fallback:', err.message);
    return { success: false, error: err.message || 'Failed to place bet.' };
  }
}

/**
 * Cash out active bet during IN_GAME phase
 */
export async function cashOutLoopBet(
  betId: string,
  userId: string,
  currentMultiplier: number
): Promise<{ success: boolean; payout?: number; error?: string }> {
  try {
    let payout = 0;
    await runTransaction(db, async (transaction) => {
      const betRef = doc(db, 'loop_bets', betId);
      const userRef = doc(db, 'users', userId);

      const betSnap = await transaction.get(betRef);
      const userSnap = await transaction.get(userRef);

      if (!betSnap.exists()) {
        throw new Error('Bet record not found.');
      }

      const bet = betSnap.data() as MultiplayerBet;
      if (bet.status !== 'BETTING') {
        throw new Error('Bet is no longer active.');
      }

      payout = Math.round(bet.betAmount * currentMultiplier * 100) / 100;

      if (userSnap.exists()) {
        const userData = userSnap.data() as UserProfile;
        transaction.update(userRef, {
          balance: userData.balance + payout,
          updatedAt: serverTimestamp(),
        });
      }

      transaction.update(betRef, {
        status: 'CASHOUT',
        cashedOutAtMultiplier: currentMultiplier,
        payout,
      });
    });

    return { success: true, payout };
  } catch (err: any) {
    console.warn('Cashout error:', err.message);
    return { success: false, error: err.message || 'Cashout failed.' };
  }
}
