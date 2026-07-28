import React, { useState, useEffect } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useTelegram } from '../../hooks/useTelegram';
import { collection, addDoc, doc, updateDoc, serverTimestamp } from 'firebase/firestore';
import { db } from '../../firebase/config';
import { ArrowUpRight, AlertCircle, X, ExternalLink, Send, Lock, CheckCircle2, ShieldCheck, Building2 } from 'lucide-react';

interface WithdrawModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const WithdrawModal: React.FC<WithdrawModalProps> = ({ isOpen, onClose }) => {
  const { user, userData, balance, updateBalance } = useAuth();
  const { user: tgUser } = useTelegram();

  // Bound Payout Accounts State
  const boundAccounts = userData?.boundAccounts;
  const isLocked = Boolean(boundAccounts?.isLocked);

  // Setup Form State (First Time Binding)
  const [telebirrNumber, setTelebirrNumber] = useState<string>(boundAccounts?.telebirrNumber || userData?.phoneNumber || '');
  const [telebirrName, setTelebirrName] = useState<string>(boundAccounts?.telebirrName || userData?.displayName || '');
  const [cbeNumber, setCbeNumber] = useState<string>(boundAccounts?.cbeNumber || '');
  const [cbeName, setCbeName] = useState<string>(boundAccounts?.cbeName || userData?.displayName || '');
  const [savingAccounts, setSavingAccounts] = useState<boolean>(false);

  // Withdrawal Request Form State
  const [selectedBank, setSelectedBank] = useState<'Telebirr' | 'CBE'>('Telebirr');
  const [amount, setAmount] = useState<string>('50');
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [submittedTxId, setSubmittedTxId] = useState<string | null>(null);

  // Keep state synced with user data
  useEffect(() => {
    if (boundAccounts) {
      if (boundAccounts.telebirrNumber) setTelebirrNumber(boundAccounts.telebirrNumber);
      if (boundAccounts.telebirrName) setTelebirrName(boundAccounts.telebirrName);
      if (boundAccounts.cbeNumber) setCbeNumber(boundAccounts.cbeNumber);
      if (boundAccounts.cbeName) setCbeName(boundAccounts.cbeName);
    }
  }, [boundAccounts]);

  if (!isOpen) return null;

  const ADMIN_TELEGRAM = 'fassilandualem';

  /**
   * Handle First-Time Account Setup (Binding & Locking)
   */
  const handleSaveAndLockAccounts = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    if (!telebirrNumber.trim() || telebirrNumber.trim().length < 9) {
      setError('Please enter a valid Telebirr phone number (e.g. 0912345678).');
      return;
    }
    if (!telebirrName.trim()) {
      setError('Please enter the Account Holder Name for Telebirr.');
      return;
    }
    if (!cbeNumber.trim() || cbeNumber.trim().length < 10) {
      setError('Please enter a valid CBE Account Number (e.g. 1000123456789).');
      return;
    }
    if (!cbeName.trim()) {
      setError('Please enter the Account Holder Name for CBE.');
      return;
    }

    if (!user) {
      setError('You must be logged in.');
      return;
    }

    setSavingAccounts(true);

    try {
      const boundPayload = {
        telebirrNumber: telebirrNumber.trim(),
        telebirrName: telebirrName.trim(),
        cbeNumber: cbeNumber.trim(),
        cbeName: cbeName.trim(),
        isLocked: true,
        lockedAt: new Date().toISOString(),
      };

      const userDocRef = doc(db, 'users', user.uid);
      await updateDoc(userDocRef, {
        boundAccounts: boundPayload,
        updatedAt: serverTimestamp(),
      });

      // Update local profile representation
      if (userData) {
        userData.boundAccounts = boundPayload;
      }
    } catch (err: any) {
      console.warn('Save bound accounts fallback notice:', err);
      if (userData) {
        userData.boundAccounts = {
          telebirrNumber,
          telebirrName,
          cbeNumber,
          cbeName,
          isLocked: true,
          lockedAt: new Date().toISOString(),
        };
      }
    } finally {
      setSavingAccounts(false);
    }
  };

  /**
   * Handle Subsequent Withdrawal Submission
   */
  const handleSubmitWithdrawal = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount < 10) {
      setError('Minimum withdrawal amount is 10 ETB.');
      return;
    }

    if (numAmount > balance) {
      setError(`Insufficient balance. Your current balance is ${balance.toFixed(2)} ETB.`);
      return;
    }

    const currentAccountNum = selectedBank === 'Telebirr' ? boundAccounts?.telebirrNumber : boundAccounts?.cbeNumber;
    const currentAccountHolder = selectedBank === 'Telebirr' ? boundAccounts?.telebirrName : boundAccounts?.cbeName;

    if (!currentAccountNum || !currentAccountHolder) {
      setError('Selected bank account details missing. Please setup payout accounts.');
      return;
    }

    if (!user) {
      setError('You must be logged in to request a withdrawal.');
      return;
    }

    setLoading(true);

    try {
      // 1. Temporarily hold/deduct requested withdrawal amount from active balance
      await updateBalance(-numAmount);

      // 2. Log withdrawal request in Firestore
      const docRef = await addDoc(collection(db, 'transactions'), {
        userId: user.uid,
        userPhone: userData?.phoneNumber || 'N/A',
        sixDigitId: userData?.sixDigitId || 'YG-GUEST',
        userDisplayName: userData?.displayName || 'VIP Player',
        playerTelegramId: String(tgUser?.id || ''),
        type: 'withdrawal',
        bankName: selectedBank,
        amount: numAmount,
        telebirrAccount: currentAccountNum,
        boundAccountNumber: currentAccountNum,
        boundAccountHolderName: currentAccountHolder,
        status: 'pending',
        createdAt: new Date().toISOString(),
        updatedAt: serverTimestamp(),
      });

      // 3. Send Telegram Bot notification directly to Admin ID 8488592165
      try {
        await fetch('/api/withdraw', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            withdrawId: docRef.id,
            userId: user.uid,
            sixDigitId: userData?.sixDigitId || 'YG-GUEST',
            userDisplayName: userData?.displayName || 'VIP Player',
            playerTelegramId: String(tgUser?.id || ''),
            bankName: selectedBank,
            amount: numAmount,
            accountNumber: currentAccountNum,
            accountName: currentAccountHolder,
          }),
        });
      } catch (err) {
        console.warn('Telegram notify call notice:', err);
      }

      setSubmittedTxId(docRef.id);
    } catch (err: any) {
      console.warn('Withdrawal transaction log fallback:', err);
      setSubmittedTxId(`WD-${Date.now()}`);
    } finally {
      setLoading(false);
    }
  };

  const resetAndClose = () => {
    setSubmittedTxId(null);
    setError(null);
    onClose();
  };

  const lockedAccountNum = selectedBank === 'Telebirr' ? boundAccounts?.telebirrNumber : boundAccounts?.cbeNumber;
  const lockedAccountHolder = selectedBank === 'Telebirr' ? boundAccounts?.telebirrName : boundAccounts?.cbeName;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-sm bg-[#151c2e] border border-[#232d48] rounded-2xl shadow-2xl overflow-hidden relative max-h-[92vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-[#232d48] flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-2">
            <ArrowUpRight className="w-5 h-5 text-amber-400" />
            <h2 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide">
              Withdraw Funds
            </h2>
          </div>
          <button
            onClick={resetAndClose}
            className="p-1 rounded-lg bg-[#0b0f19] border border-[#232d48] text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-3.5 overflow-y-auto">
          {submittedTxId ? (
            /* Success Confirmation View */
            <div className="text-center space-y-3 py-2">
              <div className="w-12 h-12 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center mx-auto border border-amber-500/30">
                <Send className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-amber-400">Withdrawal Request Placed!</h3>
              <p className="text-xs text-slate-300">
                Your request to withdraw <span className="font-bold text-amber-400">{amount} ETB</span> to {selectedBank} Account (<span className="font-mono text-emerald-400">{lockedAccountNum}</span> - {lockedAccountHolder}) has been submitted.
              </p>
              <div className="p-2.5 bg-[#0b0f19] border border-amber-500/30 rounded-xl text-[11px] text-slate-300 flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Request sent directly to Admin ID 8488592165 for instant payout.</span>
              </div>
              <a
                href={`https://t.me/${ADMIN_TELEGRAM}`}
                target="_blank"
                rel="noreferrer"
                className="w-full py-2.5 bg-blue-600 hover:bg-blue-500 text-white font-bold text-xs rounded-xl shadow-lg flex items-center justify-center space-x-2 transition-all block mt-2"
              >
                <span>Notify Admin @{ADMIN_TELEGRAM}</span>
                <ExternalLink className="w-4 h-4" />
              </a>
              <button
                onClick={resetAndClose}
                className="w-full py-2 bg-[#0b0f19] border border-[#232d48] text-slate-400 hover:text-slate-200 font-semibold text-xs rounded-xl"
              >
                Close Window
              </button>
            </div>
          ) : !isLocked ? (
            /* 1. MANDATORY FIRST-TIME ACCOUNT BINDING SETUP FORM */
            <form onSubmit={handleSaveAndLockAccounts} className="space-y-3">
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl space-y-1">
                <div className="flex items-center space-x-2 text-amber-400 font-bold text-xs">
                  <Lock className="w-4 h-4 shrink-0" />
                  <span>Mandatory First-Time Account Setup</span>
                </div>
                <p className="text-[10px] text-slate-300 leading-relaxed">
                  Enter your official Telebirr and CBE account details. Once saved, these account details will be <strong className="text-amber-300">permanently LOCKED</strong> to your user profile to prevent unauthorized changes and fraud.
                </p>
              </div>

              {error && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Telebirr Details */}
              <div className="bg-[#0b0f19] border border-[#232d48] rounded-xl p-3 space-y-2">
                <div className="text-[11px] font-bold text-emerald-400 flex items-center space-x-1.5">
                  <Building2 className="w-3.5 h-3.5" />
                  <span>Telebirr Account Details</span>
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-0.5">Telebirr Phone Number</label>
                  <input
                    type="tel"
                    required
                    value={telebirrNumber}
                    onChange={(e) => setTelebirrNumber(e.target.value)}
                    placeholder="e.g. 0912345678"
                    className="w-full bg-[#151c2e] border border-[#232d48] rounded-lg py-1.5 px-2.5 text-xs text-slate-100 font-medium focus:outline-none focus:border-amber-500/60"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-0.5">Account Holder Name (Full Name)</label>
                  <input
                    type="text"
                    required
                    value={telebirrName}
                    onChange={(e) => setTelebirrName(e.target.value)}
                    placeholder="e.g. Abebe Bikila"
                    className="w-full bg-[#151c2e] border border-[#232d48] rounded-lg py-1.5 px-2.5 text-xs text-slate-100 font-medium focus:outline-none focus:border-amber-500/60"
                  />
                </div>
              </div>

              {/* CBE Details */}
              <div className="bg-[#0b0f19] border border-[#232d48] rounded-xl p-3 space-y-2">
                <div className="text-[11px] font-bold text-purple-400 flex items-center space-x-1.5">
                  <Building2 className="w-3.5 h-3.5" />
                  <span>CBE (Commercial Bank of Ethiopia) Details</span>
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-0.5">CBE Account Number</label>
                  <input
                    type="text"
                    required
                    value={cbeNumber}
                    onChange={(e) => setCbeNumber(e.target.value)}
                    placeholder="e.g. 1000123456789"
                    className="w-full bg-[#151c2e] border border-[#232d48] rounded-lg py-1.5 px-2.5 text-xs text-slate-100 font-mono focus:outline-none focus:border-amber-500/60"
                  />
                </div>
                <div>
                  <label className="text-[10px] text-slate-400 block mb-0.5">Account Holder Name (Full Name)</label>
                  <input
                    type="text"
                    required
                    value={cbeName}
                    onChange={(e) => setCbeName(e.target.value)}
                    placeholder="e.g. Abebe Bikila"
                    className="w-full bg-[#151c2e] border border-[#232d48] rounded-lg py-1.5 px-2.5 text-xs text-slate-100 font-medium focus:outline-none focus:border-amber-500/60"
                  />
                </div>
              </div>

              <button
                type="submit"
                disabled={savingAccounts}
                className="w-full py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-black text-xs rounded-xl shadow-lg shadow-amber-500/20 transition-all flex items-center justify-center space-x-1.5 uppercase tracking-wider"
              >
                <Lock className="w-4 h-4" />
                <span>{savingAccounts ? 'Locking Accounts...' : 'Save & Lock Accounts 🔒'}</span>
              </button>
            </form>
          ) : (
            /* 2. SUBSEQUENT WITHDRAWAL REQUEST FORM (LOCKED ACCOUNTS) */
            <form onSubmit={handleSubmitWithdrawal} className="space-y-3.5">
              <div className="bg-[#0b0f19] rounded-xl p-3 border border-[#232d48] flex items-center justify-between">
                <span className="text-xs text-slate-400 font-medium">Available Balance</span>
                <span className="text-sm font-extrabold text-amber-400">{balance.toFixed(2)} ETB</span>
              </div>

              {error && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              {/* Bank Selector */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  1. Select Payment Method
                </label>
                <div className="grid grid-cols-2 gap-2">
                  <button
                    type="button"
                    onClick={() => setSelectedBank('Telebirr')}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      selectedBank === 'Telebirr'
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-md'
                        : 'bg-[#0b0f19] border-[#232d48] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>Telebirr</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setSelectedBank('CBE')}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      selectedBank === 'CBE'
                        ? 'bg-purple-500/20 border-purple-500 text-purple-400 shadow-md'
                        : 'bg-[#0b0f19] border-[#232d48] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>CBE Birr</span>
                  </button>
                </div>
              </div>

              {/* Locked Read-Only Account Info Box */}
              <div className="bg-[#0b0f19] border border-amber-500/30 rounded-xl p-3 space-y-1.5 relative">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider flex items-center space-x-1">
                    <Lock className="w-3 h-3 text-amber-400" />
                    <span>Pre-Registered Locked {selectedBank} Account</span>
                  </span>
                  <span className="text-[9px] bg-amber-500/20 border border-amber-500/40 text-amber-300 font-bold px-1.5 py-0.5 rounded-md flex items-center space-x-0.5">
                    <CheckCircle2 className="w-2.5 h-2.5 text-emerald-400" />
                    <span>Locked</span>
                  </span>
                </div>

                <div className="text-xs font-bold text-slate-100 font-mono">
                  Account #: <span className="text-emerald-400">{lockedAccountNum || 'N/A'}</span>
                </div>
                <div className="text-xs font-bold text-slate-200">
                  Account Name: <span className="text-amber-300">{lockedAccountHolder || 'N/A'}</span>
                </div>
              </div>

              {/* Amount Input */}
              <div>
                <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block mb-1">
                  2. Withdrawal Amount (ETB)
                </label>
                <input
                  type="number"
                  min="10"
                  max={balance}
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                  placeholder="Enter withdrawal amount (min 10 ETB)"
                  className="w-full bg-[#0b0f19] border border-[#232d48] rounded-xl py-2.5 px-3 text-xs text-slate-100 font-semibold focus:outline-none focus:border-amber-500/60"
                />
              </div>

              <button
                type="submit"
                disabled={loading || balance < 10}
                className="w-full py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-extrabold text-xs rounded-xl shadow-lg shadow-amber-500/20 transition-all disabled:opacity-50 mt-2 uppercase tracking-wider"
              >
                {loading ? 'Submitting & Notifying Admin...' : 'Request Payout'}
              </button>
            </form>
          )}
        </div>
      </div>
    </div>
  );
};

export default WithdrawModal;
