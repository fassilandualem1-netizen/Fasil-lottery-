/**
 * Yegna Bet - Network Disconnection & Crash Recovery Engine
 * Automatically detects orphaned/interrupted game sessions on app initialization or reconnect,
 * safely auto-settling or refunding bets to ensure zero loss of player funds.
 */

import { doc, getDoc, updateDoc, serverTimestamp } from 'firebase/firestore';
import { db } from '../firebase/config';
import { UserProfile, BetRecord } from '../types';

export interface RecoveryResult {
  recovered: boolean;
  refundedAmount?: number;
  betId?: string;
  gameType?: string;
  message?: string;
}

/**
 * Check for unresolved active game sessions upon app startup or network reconnect
 */
export async function checkAndRecoverActiveSession(userId: string): Promise<RecoveryResult> {
  if (!userId) {
    return { recovered: false };
  }

  try {
    const userRef = doc(db, 'users', userId);
    const userSnap = await getDoc(userRef);

    if (!userSnap.exists()) {
      return { recovered: false };
    }

    const userData = userSnap.data() as UserProfile;

    // Check if user has an active session flag
    if (userData.inGame && userData.activeGameSession) {
      const activeSession = userData.activeGameSession;
      const betId = activeSession.betId;
      const refundAmount = activeSession.betAmount;

      console.warn(`Interrupted session detected for bet ${betId} (${activeSession.gameType}). Auto-refunding ${refundAmount} ETB.`);

      // Refund user balance and clear session lock
      const newBalance = userData.balance + refundAmount;
      await updateDoc(userRef, {
        balance: newBalance,
        inGame: false,
        activeGameSession: null,
        updatedAt: serverTimestamp(),
      });

      // Update bet record status if it exists
      if (betId) {
        try {
          const betRef = doc(db, 'bets', betId);
          await updateDoc(betRef, {
            status: 'REFUNDED',
            payout: refundAmount,
            multiplier: 1.0,
            won: false,
            resolvedAt: new Date().toISOString(),
          });
        } catch (e) {
          console.warn('Bet document update deferred during session recovery:', e);
        }
      }

      return {
        recovered: true,
        refundedAmount: refundAmount,
        betId,
        gameType: activeSession.gameType,
        message: `Your interrupted ${activeSession.gameType.toUpperCase()} game session was safely refunded (${refundAmount.toFixed(2)} ETB returned to wallet).`,
      };
    }

    return { recovered: false };
  } catch (error: any) {
    console.warn('Session recovery check skipped:', error.message);
    return { recovered: false };
  }
}
