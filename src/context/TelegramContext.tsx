import React, { createContext, useContext, useEffect, useState } from 'react';
import { TelegramUser, TelegramWebApp } from '../types';

interface TelegramContextType {
  webApp: TelegramWebApp | null;
  user: TelegramUser | null;
  isReady: boolean;
  expandApp: () => void;
  triggerHaptic: (style?: 'light' | 'medium' | 'heavy') => void;
}

const TelegramContext = createContext<TelegramContextType>({
  webApp: null,
  user: null,
  isReady: false,
  expandApp: () => {},
  triggerHaptic: () => {},
});

export const TelegramProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [webApp, setWebApp] = useState<TelegramWebApp | null>(null);
  const [user, setUser] = useState<TelegramUser | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const tg = window.Telegram?.WebApp;
    if (tg) {
      tg.ready();
      tg.expand();
      setWebApp(tg);
      if (tg.initDataUnsafe?.user) {
        setUser(tg.initDataUnsafe.user);
      }
    } else {
      // Fallback user for web browser development/testing
      setUser({
        id: 999999999,
        first_name: 'Demo',
        last_name: 'Player',
        username: 'demoplayer',
      });
    }
    setIsReady(true);
  }, []);

  const expandApp = () => {
    webApp?.expand();
  };

  const triggerHaptic = (style: 'light' | 'medium' | 'heavy' = 'light') => {
    webApp?.HapticFeedback?.impactOccurred(style);
  };

  return (
    <TelegramContext.Provider value={{ webApp, user, isReady, expandApp, triggerHaptic }}>
      {children}
    </TelegramContext.Provider>
  );
};

export const useTelegram = () => useContext(TelegramContext);
