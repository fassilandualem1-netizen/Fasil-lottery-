import { useEffect, useState } from 'react';
import { TelegramUser, TelegramWebApp } from '../types';

export interface UseTelegramReturn {
  tg: TelegramWebApp | null;
  user: TelegramUser | null;
  isAdmin: boolean;
  onClose: () => void;
  isExpanded: boolean;
  haptic?: {
    impact: (style?: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft') => void;
    notification: (type: 'error' | 'success' | 'warning') => void;
    selection: () => void;
  };
}

/**
 * Custom hook to safely access the Telegram WebApp API
 * Automatically initializes and expands the WebApp view
 */
export function useTelegram(): UseTelegramReturn {
  const [tg, setTg] = useState<TelegramWebApp | null>(null);
  const [user, setUser] = useState<TelegramUser | null>(null);
  const [isExpanded, setIsExpanded] = useState<boolean>(false);

  useEffect(() => {
    const app = window.Telegram?.WebApp;
    if (app) {
      app.ready();
      app.expand();
      setTg(app);
      setIsExpanded(app.isExpanded);

      if (app.initDataUnsafe?.user) {
        setUser(app.initDataUnsafe.user);
      }
    } else {
      // Fallback dev user when testing directly in standard browser
      setUser({
        id: 777000123,
        first_name: 'Yegna',
        last_name: 'Player',
        username: 'yegna_vip',
        language_code: 'am',
      });
    }
  }, []);

  const onClose = () => {
    if (tg) {
      tg.close();
    }
  };

  const isHapticSupported = Boolean(
    tg?.isVersionAtLeast?.('6.1') || window.Telegram?.WebApp?.isVersionAtLeast?.('6.1')
  );

  const haptic = {
    impact: (style: 'light' | 'medium' | 'heavy' | 'rigid' | 'soft' = 'light') => {
      try {
        if (isHapticSupported && window.Telegram?.WebApp?.HapticFeedback) {
          window.Telegram?.WebApp?.HapticFeedback.impactOccurred(style);
        }
      } catch (e) {}
    },
    notification: (type: 'error' | 'success' | 'warning') => {
      try {
        if (isHapticSupported && window.Telegram?.WebApp?.HapticFeedback) {
          window.Telegram?.WebApp?.HapticFeedback.notificationOccurred(type);
        }
      } catch (e) {}
    },
    selection: () => {
      try {
        if (isHapticSupported && window.Telegram?.WebApp?.HapticFeedback) {
          window.Telegram?.WebApp?.HapticFeedback.selectionChanged();
        }
      } catch (e) {}
    },
  };

  const isAdmin = String(user?.id) === '8488592165';

  return {
    tg,
    user,
    isAdmin,
    onClose,
    isExpanded: isExpanded || true,
    haptic,
  };
}
