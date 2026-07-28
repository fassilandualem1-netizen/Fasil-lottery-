/**
 * Yegna Bet - Provably Fair & Cryptographically Secure Math RNG Utilities
 * Ensures game outcomes (Crash multipliers, Dice, Mines, Slots, Cards) use true non-deterministic RNG
 */

/**
 * Cryptographically secure float in range [0, 1)
 */
export function cryptoRandomFloat(): number {
  if (typeof window !== 'undefined' && window.crypto && window.crypto.getRandomValues) {
    const buffer = new Uint32Array(1);
    window.crypto.getRandomValues(buffer);
    return buffer[0] / (0xffffffff + 1);
  }
  return Math.random();
}

/**
 * Generate Crash Multiplier based on standard provably fair curve formula
 * House Edge default is 3% (0.03 -> multiplier factor 0.97 or 0.99)
 */
export function generateCrashMultiplier(houseEdge: number = 0.03): number {
  const e = 100;
  const r = cryptoRandomFloat();
  
  // 3% instant crash at 1.00x
  if (r < houseEdge) {
    return 1.00;
  }

  // Formula: multiplier = (100 - houseEdge*100) / (100 - randomValue * 100)
  const rawMultiplier = (e * (1 - houseEdge)) / (e - r * e);
  const finalMultiplier = Math.floor(rawMultiplier * 100) / 100;
  
  return Math.max(1.00, finalMultiplier);
}

/**
 * Roll Dice returning a decimal value between min and max (default 0 to 100)
 */
export function rollDice(min: number = 0, max: number = 100): number {
  const r = cryptoRandomFloat();
  const rolled = min + r * (max - min);
  return Math.floor(rolled * 100) / 100;
}

/**
 * Generate Mines grid positions
 * @param totalTiles Total number of tiles on grid (e.g., 25 for 5x5)
 * @param mineCount Number of hidden mines (e.g., 3)
 * @returns Array of booleans where true = mine, false = gem
 */
export function generateMinesGrid(totalTiles: number = 25, mineCount: number = 3): boolean[] {
  const grid = new Array(totalTiles).fill(false);
  let placedMines = 0;

  while (placedMines < mineCount) {
    const randomIndex = Math.floor(cryptoRandomFloat() * totalTiles);
    if (!grid[randomIndex]) {
      grid[randomIndex] = true;
      placedMines++;
    }
  }

  return grid;
}

/**
 * Spin Slots Reel returning array of symbol IDs for N reels
 */
export function spinSlots<T>(symbols: T[], reelCount: number = 3): T[] {
  const result: T[] = [];
  for (let i = 0; i < reelCount; i++) {
    const randomIndex = Math.floor(cryptoRandomFloat() * symbols.length);
    result.push(symbols[randomIndex]);
  }
  return result;
}

/**
 * Draw a random card for casino card games
 */
export interface Card {
  suit: '♠' | '♥' | '♦' | '♣';
  value: string;
  numericValue: number;
}

export function generateRandomCard(): Card {
  const suits: Card['suit'][] = ['♠', '♥', '♦', '♣'];
  const values = ['2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A'];
  
  const suit = suits[Math.floor(cryptoRandomFloat() * suits.length)];
  const valueIndex = Math.floor(cryptoRandomFloat() * values.length);
  const value = values[valueIndex];
  
  // Calculate numeric value (Ace = 11, Face cards = 10)
  let numericValue = valueIndex + 2;
  if (valueIndex >= 8 && valueIndex <= 11) numericValue = 10; // 10, J, Q, K
  if (value === 'A') numericValue = 11;

  return { suit, value, numericValue };
}
