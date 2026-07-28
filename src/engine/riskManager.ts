/**
 * Yegna Bet - Risk Management & Limits Engine
 * Enforces global financial limits, house edge rules, and maximum payout constraints
 * to protect casino liquidity and prevent malicious exploit bets.
 */

export interface RiskConfig {
  houseEdge: number;      // e.g. 0.04 = 4%
  minBet: number;         // e.g. 5 ETB
  maxBet: number;         // e.g. 5,000 ETB
  maxPayout: number;      // e.g. 50,000 ETB per single bet
  currency: string;       // e.g. 'ETB'
  supportedGames: string[];
}

export const DEFAULT_RISK_CONFIG: RiskConfig = {
  houseEdge: 0.04,        // 4% House Edge
  minBet: 5.00,           // Minimum 5 ETB
  maxBet: 5000.00,        // Maximum 5,000 ETB per bet
  maxPayout: 50000.00,    // Maximum 50,000 ETB potential payout per bet
  currency: 'ETB',
  supportedGames: ['crash', 'slots', 'roulette', 'dice', 'mines', 'keno', 'greyhound'],
};

export interface BetValidationResult {
  valid: boolean;
  reason?: string;
  maxAllowedBet?: number;
  maxAllowedPayout?: number;
}

/**
 * Validate a user's bet before session initialization or contract placement
 */
export function validateBet(
  betAmount: number,
  userBalance: number,
  targetMultiplier: number = 1.01,
  config: RiskConfig = DEFAULT_RISK_CONFIG
): BetValidationResult {
  // 1. Basic positive number check
  if (isNaN(betAmount) || betAmount <= 0) {
    return { valid: false, reason: 'Bet amount must be a positive number.' };
  }

  // 2. Minimum Bet Check
  if (betAmount < config.minBet) {
    return {
      valid: false,
      reason: `Minimum bet amount is ${config.minBet} ${config.currency}.`,
    };
  }

  // 3. Maximum Bet Check
  if (betAmount > config.maxBet) {
    return {
      valid: false,
      reason: `Maximum allowed bet is ${config.maxBet.toLocaleString()} ${config.currency}.`,
      maxAllowedBet: config.maxBet,
    };
  }

  // 4. Insufficient Balance Check
  if (betAmount > userBalance) {
    return {
      valid: false,
      reason: `Insufficient balance (${userBalance.toFixed(2)} ${config.currency} available).`,
      maxAllowedBet: Math.min(userBalance, config.maxBet),
    };
  }

  // 5. Maximum Potential Payout Constraint Check
  const potentialPayout = betAmount * targetMultiplier;
  if (potentialPayout > config.maxPayout) {
    const maxSafeBet = Math.floor((config.maxPayout / targetMultiplier) * 100) / 100;
    return {
      valid: false,
      reason: `Potential payout exceeds maximum limit of ${config.maxPayout.toLocaleString()} ${config.currency}.`,
      maxAllowedPayout: config.maxPayout,
      maxAllowedBet: Math.min(maxSafeBet, config.maxBet),
    };
  }

  return { valid: true };
}

/**
 * Calculate maximum allowable multiplier for a given bet amount
 */
export function getMaxMultiplierForBet(
  betAmount: number,
  config: RiskConfig = DEFAULT_RISK_CONFIG
): number {
  if (betAmount <= 0) return 1.00;
  return Math.floor((config.maxPayout / betAmount) * 100) / 100;
}
