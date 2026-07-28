/**
 * Yegna Bet - Global TypeScript Definitions
 */

// Telegram WebApp Types
export interface TelegramUser {
  id: number;
  first_name: string;
  last_name?: string;
  username?: string;
  language_code?: string;
  is_premium?: boolean;
  photo_url?: string;
}

export interface TelegramWebApp {
  initData: string;
  initDataUnsafe: {
    query_id?: string;
    user?: TelegramUser;
    auth_date?: string;
    hash?: string;
  };
  version: string;
  isVersionAtLeast?: (version: string) => boolean;
  platform: string;
  colorScheme: 'light' | 'dark';
  themeParams: Record<string, string>;
  isExpanded: boolean;
  viewportHeight: number;
  viewportStableHeight: number;
  headerColor: string;
  backgroundColor: string;
  BackButton: {
    isVisible: boolean;
    show: () => void;
    hide: () => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
  };
  MainButton: {
    text: string;
    color: string;
    textColor: string;
    isVisible: boolean;
    isActive: boolean;
    isProgressVisible: boolean;
    setText: (text: string) => void;
    onClick: (cb: () => void) => void;
    offClick: (cb: () => void) => void;
    show: () => void;
    hide: () => void;
    enable: () => void;
    disable: () => void;
    showProgress: (leaveActive?: boolean) => void;
    hideProgress: () => void;
  };
  HapticFeedback: {
    impactOccurred: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notificationOccurred: (type: 'error' | 'success' | 'warning') => void;
    selectionChanged: () => void;
  };
  ready: () => void;
  expand: () => void;
  close: () => void;
  sendData: (data: string) => void;
}

declare global {
  interface Window {
    Telegram?: {
      WebApp: TelegramWebApp;
    };
  }
}

// Casino User & Financial Models
export interface ActiveGameSession {
  betId: string;
  gameType: string;
  betAmount: number;
  serverSeed: string;
  serverSeedHash: string;
  clientSeed: string;
  nonce: number;
  startedAt: string;
  gameData?: Record<string, any>;
}

export interface BoundAccounts {
  telebirrNumber?: string;
  telebirrName?: string;
  cbeNumber?: string;
  cbeName?: string;
  isLocked?: boolean;
  lockedAt?: string;
}

export interface UserProfile {
  uid: string;
  telegramId?: number;
  phoneNumber?: string;
  sixDigitId?: string;
  username: string;
  displayName: string;
  photoUrl?: string;
  balance: number; // in ETB or Coins
  vipLevel: number;
  totalWagered: number;
  role?: 'user' | 'admin';
  inGame?: boolean;
  activeGameSession?: ActiveGameSession | null;
  boundAccounts?: BoundAccounts;
  createdAt: string;
  updatedAt: string;
}

export type TransactionType = 'deposit' | 'withdrawal';
export type TransactionStatus = 'pending' | 'approved' | 'rejected';

export interface TransactionRecord {
  id: string;
  userId: string;
  userPhone?: string;
  sixDigitId?: string;
  userDisplayName?: string;
  playerTelegramId?: string;
  type: TransactionType;
  bankName?: 'Telebirr' | 'CBE' | string;
  amount: number;
  reference?: string;
  smsText?: string;
  receiptImage?: string | null;
  telebirrAccount?: string;
  boundAccountHolderName?: string;
  boundAccountNumber?: string;
  status: TransactionStatus;
  createdAt: string;
  updatedAt?: string;
  adminNotes?: string;
}

export type BetStatus = 'PENDING' | 'WON' | 'LOST' | 'CANCELLED' | 'REFUNDED';

export interface BetRecord {
  id: string;
  userId: string;
  gameId: string;
  betAmount: number;
  multiplier: number;
  payout: number;
  status: BetStatus;
  won: boolean;
  serverSeed?: string;
  serverSeedHash?: string;
  clientSeed?: string;
  nonce?: number;
  gameData?: Record<string, any>;
  timestamp: string;
  resolvedAt?: string;
}

export interface GameInfo {
  id: string;
  name: string;
  slug: string;
  description: string;
  icon: string;
  minBet: number;
  maxBet: number;
  active: boolean;
}

export type LoopState = 'BETTING' | 'IN_GAME' | 'RESOLVED' | 'COOLDOWN';
export type LoopGameType = 'aviator' | 'keno' | 'coinflip' | 'virtual_sport' | 'mines' | 'dice' | 'color_wheel';

export interface LoopRound {
  roundId: string;
  gameId: LoopGameType;
  state: LoopState;
  serverSeedHash: string;
  serverSeed?: string;
  outcome?: any;
  bettingEndsAt: number;
  gameEndsAt: number;
  cooldownEndsAt: number;
  createdAt: string;
}

export interface MultiplayerBet {
  id: string;
  roundId: string;
  gameId: LoopGameType;
  userId: string;
  displayName: string;
  sixDigitId?: string;
  betAmount: number;
  gameData?: Record<string, any>;
  status: 'BETTING' | 'CASHOUT' | 'WON' | 'LOST' | 'CANCELLED';
  cashedOutAtMultiplier?: number;
  payout: number;
  createdAt: string;
}
