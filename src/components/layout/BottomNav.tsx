import React from 'react';
import { Home, Gamepad2, Wallet, History, Headphones, ShieldAlert } from 'lucide-react';
import { useTelegram } from '../../hooks/useTelegram';
import { useAuth } from '../../context/AuthContext';

export type NavTab = 'home' | 'games' | 'wallet' | 'history' | 'support' | 'admin';

interface BottomNavProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
  pendingDepositCount?: number;
}

export const BottomNav: React.FC<BottomNavProps> = ({
  activeTab,
  onTabChange,
}) => {
  const { haptic, isAdmin: isTgAdmin } = useTelegram();
  const { isAdmin: isAuthAdmin } = useAuth();
  const isAdmin = isTgAdmin || isAuthAdmin;

  const handleSelect = (tab: NavTab) => {
    haptic?.impact('light');
    onTabChange(tab);
  };

  const navItems = [
    { id: 'home' as NavTab, label: 'Home', icon: Home },
    { id: 'games' as NavTab, label: 'Games', icon: Gamepad2 },
    { id: 'wallet' as NavTab, label: 'Wallet', icon: Wallet },
    { id: 'history' as NavTab, label: 'History', icon: History },
    { id: 'support' as NavTab, label: 'Support', icon: Headphones },
  ];

  // Grant access to Admin Tab only if Telegram User ID is 8488592165 or Admin Role
  if (isAdmin) {
    navItems.push({ id: 'admin' as NavTab, label: 'Admin 👑', icon: ShieldAlert });
  }

  return (
    <nav className="fixed bottom-0 left-0 right-0 z-50 bg-[#0d1322]/95 backdrop-blur-lg border-t border-[#232d48] px-2 py-2 max-w-md mx-auto shadow-2xl">
      <div className="flex items-center justify-around">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;

          return (
            <button
              key={item.id}
              onClick={() => handleSelect(item.id)}
              className={`flex flex-col items-center justify-center py-1 px-2.5 rounded-xl transition-all duration-200 relative ${
                isActive
                  ? 'text-amber-400 scale-105 font-bold'
                  : 'text-slate-400 hover:text-slate-200 font-medium'
              }`}
            >
              <div
                className={`p-1.5 rounded-xl transition-all ${
                  isActive
                    ? 'bg-gradient-to-tr from-amber-500/20 to-amber-300/10 border border-amber-500/30 shadow-md shadow-amber-500/10'
                    : 'bg-transparent'
                }`}
              >
                <Icon className={`w-5 h-5 ${isActive ? 'text-amber-400' : 'text-slate-400'}`} />
              </div>
              <span className="text-[10px] tracking-tight mt-0.5">{item.label}</span>

              {/* Active Dot Indicator */}
              {isActive && (
                <span className="absolute -top-1 w-1.5 h-1.5 rounded-full bg-amber-400 shadow-sm shadow-amber-400" />
              )}
            </button>
          );
        })}
      </div>
    </nav>
  );
};

export default BottomNav;
