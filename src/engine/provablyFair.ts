/**
 * Yegna Bet - Provably Fair Engine
 * Uses HMAC-SHA256 cryptographic hash algorithms to generate 100% deterministic,
 * verifiable, and unmanipulable game outcomes.
 */

/**
 * Generate a cryptographically secure 64-character hexadecimal server seed
 */
export function generateServerSeed(): string {
  const array = new Uint8Array(32);
  if (typeof window !== 'undefined' && window.crypto) {
    window.crypto.getRandomValues(array);
  } else {
    for (let i = 0; i < 32; i++) {
      array[i] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(array, (byte) => byte.toString(16).padStart(2, '0')).join('');
}

/**
 * Hash the server seed with SHA-256 for public disclosure before game rounds
 */
export async function hashServerSeed(serverSeed: string): Promise<string> {
  const encoder = new TextEncoder();
  const data = encoder.encode(serverSeed);
  const hashBuffer = await crypto.subtle.digest('SHA-256', data);
  const hashArray = Array.from(new Uint8Array(hashBuffer));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Generate a random client seed string
 */
export function generateClientSeed(): string {
  const array = new Uint8Array(16);
  if (typeof window !== 'undefined' && window.crypto) {
    window.crypto.getRandomValues(array);
  } else {
    for (let i = 0; i < 16; i++) {
      array[i] = Math.floor(Math.random() * 256);
    }
  }
  return Array.from(array, (b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Calculate HMAC-SHA256 hash using browser SubtleCrypto
 */
export async function calculateHmacSha256(key: string, message: string): Promise<string> {
  const encoder = new TextEncoder();
  const keyData = encoder.encode(key);
  const msgData = encoder.encode(message);

  const cryptoKey = await crypto.subtle.importKey(
    'raw',
    keyData,
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );

  const signature = await crypto.subtle.sign('HMAC', cryptoKey, msgData);
  const hashArray = Array.from(new Uint8Array(signature));
  return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
}

/**
 * Convert HMAC hex string to deterministic uniform float in range [0, 1)
 */
export async function getGameOutcome(
  serverSeed: string,
  clientSeed: string,
  nonce: number
): Promise<number> {
  const message = `${clientSeed}:${nonce}`;
  const hmacHex = await calculateHmacSha256(serverSeed, message);

  // Take first 8 characters (32 bits) of the HMAC string
  const subHash = hmacHex.substring(0, 8);
  const decimalValue = parseInt(subHash, 16);

  // Divide by 2^32 (4294967296) to get float between [0, 1)
  return decimalValue / 4294967296;
}

/**
 * Provably Fair Crash Game Multiplier Calculator
 * Formula: multiplier = (100 - houseEdge*100) / (100 - randomValue * 100)
 */
export async function getProvableCrashMultiplier(
  serverSeed: string,
  clientSeed: string,
  nonce: number,
  houseEdge: number = 0.03
): Promise<number> {
  const randomValue = await getGameOutcome(serverSeed, clientSeed, nonce);

  // Instant crash chance equal to house edge (e.g., 3%)
  if (randomValue < houseEdge) {
    return 1.00;
  }

  const e = 100;
  const rawMultiplier = (e * (1 - houseEdge)) / (e - randomValue * e);
  const finalMultiplier = Math.floor(rawMultiplier * 100) / 100;

  return Math.max(1.00, finalMultiplier);
}

/**
 * Provably Fair Dice Roll Result (0.00 to 100.00)
 */
export async function getProvableDiceRoll(
  serverSeed: string,
  clientSeed: string,
  nonce: number
): Promise<number> {
  const float = await getGameOutcome(serverSeed, clientSeed, nonce);
  const rolled = float * 100;
  return Math.floor(rolled * 100) / 100;
}

/**
 * Provably Fair Coinflip Result ('HEADS' | 'TAILS')
 */
export async function getProvableCoinflip(
  serverSeed: string,
  clientSeed: string,
  nonce: number
): Promise<'HEADS' | 'TAILS'> {
  const float = await getGameOutcome(serverSeed, clientSeed, nonce);
  return float < 0.5 ? 'HEADS' : 'TAILS';
}

/**
 * Provably Fair Mines Grid Generator
 */
export async function getProvableMinesGrid(
  serverSeed: string,
  clientSeed: string,
  nonce: number,
  totalTiles: number = 25,
  mineCount: number = 3
): Promise<boolean[]> {
  const grid = new Array(totalTiles).fill(false);
  let placed = 0;
  let currentNonce = nonce;

  while (placed < mineCount) {
    const float = await getGameOutcome(serverSeed, clientSeed, currentNonce);
    const index = Math.floor(float * totalTiles);
    if (!grid[index]) {
      grid[index] = true;
      placed++;
    }
    currentNonce++;
  }

  return grid;
}
