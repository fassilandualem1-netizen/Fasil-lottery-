import React from 'react';
import { useTelegram } from '../hooks/useTelegram';
import { 
  Headphones, 
  Send, 
  ShieldCheck, 
  Sparkles, 
  MessageSquare, 
  HelpCircle,
  ExternalLink,
  Award
} from 'lucide-react';

export const SupportPage: React.FC = () => {
  const { haptic } = useTelegram();

  const openTelegramChannel = () => {
    haptic?.impact('light');
    window.open('https://t.me/yegnabet_official', '_blank');
  };

  const openTelegramAdmin = () => {
    haptic?.impact('light');
    window.open('https://t.me/fassilandualem', '_blank');
  };

  return (
    <div className="w-full max-w-md mx-auto min-h-screen p-4 space-y-4 pb-24">
      {/* Title Header */}
      <div className="bg-gradient-to-br from-[#151c2e] via-[#1a233a] to-[#151c2e] border border-amber-500/30 rounded-2xl p-5 shadow-2xl space-y-3">
        <div className="flex items-center space-x-3">
          <div className="w-10 h-10 rounded-2xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 shrink-0 shadow-lg">
            <Headphones className="w-5 h-5" />
          </div>
          <div>
            <h2 className="text-base font-black text-slate-100 uppercase tracking-wide">
              Official VIP Support
            </h2>
            <p className="text-xs text-slate-400">Yegna Bet Telegram Admin & Community</p>
          </div>
        </div>

        <p className="text-xs text-slate-300 leading-relaxed">
          Need instant deposit verification, assistance with fast withdrawals, or official promo codes? Connect directly with our team on Telegram.
        </p>

        {/* Action Buttons */}
        <div className="space-y-2.5 pt-2">
          <button
            onClick={openTelegramChannel}
            className="w-full py-3 px-4 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-extrabold text-xs rounded-xl shadow-lg shadow-blue-500/20 flex items-center justify-between transition-all"
          >
            <div className="flex items-center space-x-2">
              <Send className="w-4 h-4" />
              <span>Join Official Telegram Channel</span>
            </div>
            <ExternalLink className="w-4 h-4" />
          </button>

          <button
            onClick={openTelegramAdmin}
            className="w-full py-3 px-4 bg-[#0b0f19] border border-amber-500/40 hover:border-amber-400 text-amber-400 font-extrabold text-xs rounded-xl shadow-md flex items-center justify-between transition-all"
          >
            <div className="flex items-center space-x-2">
              <MessageSquare className="w-4 h-4" />
              <span>Contact Admin (@fassilandualem)</span>
            </div>
            <ExternalLink className="w-4 h-4 text-amber-400" />
          </button>
        </div>
      </div>

      {/* FAQ & Verification Guidelines Card */}
      <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 shadow-xl space-y-3">
        <div className="flex items-center space-x-2 border-b border-[#232d48] pb-2">
          <HelpCircle className="w-4 h-4 text-amber-400" />
          <h3 className="text-xs font-black text-slate-100 uppercase tracking-wider">
            Frequent Questions & Help
          </h3>
        </div>

        <div className="space-y-2.5 text-xs">
          <div className="bg-[#0b0f19] p-3 rounded-xl border border-[#232d48]">
            <div className="font-bold text-amber-400 mb-1">How fast are Telebirr deposits processed?</div>
            <div className="text-slate-300 text-[11px] leading-relaxed">
              Deposits submitted with a valid Telebirr reference code are verified and credited within 2 to 5 minutes by our automated admin queue.
            </div>
          </div>

          <div className="bg-[#0b0f19] p-3 rounded-xl border border-[#232d48]">
            <div className="font-bold text-amber-400 mb-1">Are game outcomes provably fair?</div>
            <div className="text-slate-300 text-[11px] leading-relaxed">
              Yes! All game outcomes (Aviator, Virtual Sport, Keno, Coinflip) use pre-generated HMAC-SHA256 server seed hashes disclosed before every round starts.
            </div>
          </div>
        </div>

        <div className="pt-2 border-t border-[#232d48] text-center text-[10px] text-slate-400 flex items-center justify-center space-x-1">
          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
          <span>Provably Fair Engine & Encrypted Transactions</span>
        </div>
      </div>
    </div>
  );
};

export default SupportPage;
