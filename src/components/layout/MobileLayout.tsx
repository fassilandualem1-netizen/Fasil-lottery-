import React from 'react';

interface MobileLayoutProps {
  children: React.ReactNode;
  showHeader?: boolean;
  className?: string;
}

/**
 * MobileLayout: Master layout wrapper strictly adhering to mobile-first Telegram WebApp specifications.
 * Handles viewport safe areas, overflow constraints, and dark casino background styling.
 */
export const MobileLayout: React.FC<MobileLayoutProps> = ({ 
  children, 
  className = '' 
}) => {
  return (
    <div className="w-full max-w-[100vw] min-h-screen overflow-x-hidden bg-[#0b0f19] text-slate-100 font-sans flex flex-col relative select-none">
      {/* Top Safe Area Spacing for Telegram WebApp Header / Notches */}
      <div className="pt-safe sm:pt-2 w-full" />

      {/* Main Viewport Container */}
      <main className={`flex-1 flex flex-col w-full max-w-md mx-auto px-4 pb-20 pt-2 ${className}`}>
        {children}
      </main>

      {/* Bottom Safe Area Padding for iOS / Telegram Bottom Nav */}
      <div className="pb-safe w-full" />
    </div>
  );
};

export default MobileLayout;
