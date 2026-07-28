/**
 * Yegna Bet - Atomic Bet Processor & State Lock Engine
 * Uses Firestore transactions (runTransaction) to execute atomic balance updates,
 * prevent double-spending, and maintain strict game session locks.
 */

import { doc, runTransaction, collection, serverTimestamp } from 'firebase/firestore';
import { db } from '../firebase/config';
import { validateBet } from './riskManager';
import { generateServerSeed, hashServerSeed, generateClientSeed } from './provablyFair';
import { ActiveGameSession, BetRecord, UserProfile } from '../types';

export interface PlaceBetResult {
  success: boolean;
  betId?: string;
  serverSeed?: string;
  serverSeedHash?: string;
  clientSeed?: string;
  nonce?: number;
  error?: string;
}

export interface ResolveBetResult {
  success: boolean;
  payout?: number;
  multiplier?: number;
  status?: string;
  error?: string;
}

/**
 * Atomically deduct balance, acquire IN_GAME session lock, and register bet
 */
export async function placeBet(
  userId: string,
  gameType: string,
  betAmount: number,
  clientSeedOverride?: string,
  gameData?: Record<string, any>
): Promise<PlaceBetResult> {
  const betRef = doc(collection(db, 'bets'));
  const betId = betRef.id;

  const serverSeed = generateServerSeed();
  const serverSeedHash = await hashServerSeed(serverSeed);
  const clientSeed = clientSeedOverride || generateClientSeed();
  const nonce = 1;

  try {
    await runTransaction(db, async (transaction) => {
      const userRef = doc(db, 'users', userId);
      const userDoc = await transaction.get(userRef);

      if (!userDoc.exists()) {
        throw new Error('User profile not found.');
      }

      const userData = userDoc.data() as UserProfile;

      // Check if user is already locked in another active game session
      if (userData.inGame) {
        throw new Error('Active game session already in progress. Finish current game first.');
      }

      // Risk Manager check
      const validation = validateBet(betAmount, userData.balance);
      if (!validation.valid) {
        throw new Error(validation.reason || 'Invalid bet parameters.');
      }

      const newBalance = userData.balance - betAmount;
      const activeSession: ActiveGameSession = {
        betId,
        gameType,
        betAmount,
        serverSeed,
        serverSeedHash,
        clientSeed,
        nonce,
        startedAt: new Date().toISOString(),
        gameData,
      };

      // Atomic Update User Doc
      transaction.update(userRef, {
        balance: newBalance,
        inGame: true,
        activeGameSession: activeSession,
        updatedAt: serverTimestamp(),
      });

      // Create Pending Bet Record
      const betRecord: BetRecord = {
        id: betId,
        userId,
        gameId: gameType,
        betAmount,
        multiplier: 0,
        payout: 0,
        status: 'PENDING',
        won: false,
        serverSeed,
        serverSeedHash,
        clientSeed,
        nonce,
        gameData,
        timestamp: new Date().toISOString(),
      };

      transaction.set(betRef, betRecord);
    });

    return {
      success: true,
      betId,
      serverSeed,
      serverSeedHash,
      clientSeed,
      nonce,
    };
  } catch (error: any) {
    console.warn('BetProcessor transaction warning (falling back to demo execution if unauthenticated):', error.message);
    return {
      success: false,
      error: error.message || 'Failed to place bet.',
    };
  }
}

/**
 * Atomically resolve bet, release IN_GAME lock, and credit winnings
 */
export async function resolveBet(
  userId: string,
  betId: string,
  winAmount: number,
  multiplier: number,
  outcomeStatus: 'WON' | 'LOST' | 'CANCELLED' = winAmount > 0 ? 'WON' : 'LOST',
  gameOutcomeData?: Record<string, any>
): Promise<ResolveBetResult> {
  try {
    await runTransaction(db, async (transaction) => {
      const userRef = doc(db, 'users', userId);
      const betRef = doc(db, 'bets', betId);

      const userDoc = await transaction.get(userRef);
      const betDoc = await transaction.get(betRef);

      if (!userDoc.exists()) {
        throw new Error('User record not found.');
      }

      if (!betDoc.exists()) {
        throw new Error('Bet record not found.');
      }

      const betData = betDoc.data() as BetRecord;

      if (betData.status !== 'PENDING') {
        throw new Error('Bet has already been resolved.');
      }

      const userData = userDoc.data() as UserProfile;
      const updatedBalance = userData.balance + winAmount;
      const updatedWagered = (userData.totalWagered || 0) + betData.betAmount;

      // Unlock User Session
      transaction.update(userRef, {
        balance: updatedBalance,
        inGame: false,
        activeGameSession: null,
        totalWagered: updatedWagered,
        updatedAt: serverTimestamp(),
      });

      // Update Bet Status
      transaction.update(betRef, {
        payout: winAmount,
        multiplier,
        status: outcomeStatus,
        won: winAmount > 0,
        gameData: { ...(betData.gameData || {}), ...(gameOutcomeData || {}) },
        resolvedAt: new Date().toISOString(),
      });
    });

    return {
      success: true,
      payout: winAmount,
      multiplier,
      status: outcomeStatus,
    };
  } catch (error: any) {
    console.warn('BetProcessor resolve error:', error.message);
    return {
      success: false,
      error: error.message || 'Failed to resolve bet.',
    };
  }
}
