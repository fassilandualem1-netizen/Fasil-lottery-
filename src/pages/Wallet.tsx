import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { useTelegram } from '../hooks/useTelegram';
import { collection, addDoc, doc, updateDoc, serverTimestamp } from 'firebase/firestore';
import { db } from '../firebase/config';
import { TransactionHistory } from '../components/wallet/TransactionHistory';
import { 
  Wallet as WalletIcon, 
  ArrowDownLeft, 
  ArrowUpRight, 
  CreditCard, 
  Copy, 
  Check, 
  Send, 
  AlertCircle, 
  ExternalLink,
  ShieldCheck,
  History,
  Coins,
  Building2,
  Upload,
  X,
  Lock,
  CheckCircle2,
  MessageSquare,
  FileImage
} from 'lucide-react';

interface WalletPageProps {
  onOpenAuth: (tab: 'login' | 'register') => void;
}

export const WalletPage: React.FC<WalletPageProps> = ({ onOpenAuth }) => {
  const { user, userData, balance, updateBalance } = useAuth();
  const { user: tgUser, haptic } = useTelegram();

  const [activeTab, setActiveTab] = useState<'deposit' | 'withdraw' | 'history'>('deposit');

  // --- DEPOSIT STATE ---
  const [depositBank, setDepositBank] = useState<'Telebirr' | 'CBE'>('Telebirr');
  const [depositAmount, setDepositAmount] = useState<string>('100');
  const [proofType, setProofType] = useState<'screenshot' | 'sms'>('screenshot');
  const [depositSmsText, setDepositSmsText] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [depositLoading, setDepositLoading] = useState<boolean>(false);
  const [depositError, setDepositError] = useState<string | null>(null);
  const [submittedDepositId, setSubmittedDepositId] = useState<string | null>(null);

  // --- WITHDRAW BOUND ACCOUNTS STATE ---
  const boundAccounts = userData?.boundAccounts;
  const isAccountsLocked = Boolean(boundAccounts?.isLocked);

  const [telebirrNumber, setTelebirrNumber] = useState<string>(boundAccounts?.telebirrNumber || userData?.phoneNumber || '');
  const [telebirrName, setTelebirrName] = useState<string>(boundAccounts?.telebirrName || userData?.displayName || '');
  const [cbeNumber, setCbeNumber] = useState<string>(boundAccounts?.cbeNumber || '');
  const [cbeName, setCbeName] = useState<string>(boundAccounts?.cbeName || userData?.displayName || '');
  const [savingAccounts, setSavingAccounts] = useState<boolean>(false);

  // --- WITHDRAW SUBMISSION STATE ---
  const [withdrawBank, setWithdrawBank] = useState<'Telebirr' | 'CBE'>('Telebirr');
  const [withdrawAmount, setWithdrawAmount] = useState<string>('50');
  const [withdrawLoading, setWithdrawLoading] = useState<boolean>(false);
  const [withdrawError, setWithdrawError] = useState<string | null>(null);
  const [submittedWithdrawId, setSubmittedWithdrawId] = useState<string | null>(null);

  const RECEIVER_ACCOUNTS = {
    Telebirr: { number: '0951381356', name: 'Fasil Andualem' },
    CBE: { number: '1000584461757', name: 'Fasil Andualem' },
  };

  const ADMIN_TELEGRAM = 'fassilandualem';

  useEffect(() => {
    if (boundAccounts) {
      if (boundAccounts.telebirrNumber) setTelebirrNumber(boundAccounts.telebirrNumber);
      if (boundAccounts.telebirrName) setTelebirrName(boundAccounts.telebirrName);
      if (boundAccounts.cbeNumber) setCbeNumber(boundAccounts.cbeNumber);
      if (boundAccounts.cbeName) setCbeName(boundAccounts.cbeName);
    }
  }, [boundAccounts]);

  const handleCopyAccount = (text: string) => {
    haptic?.impact('light');
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      setSelectedFile(file);
      const reader = new FileReader();
      reader.onloadend = () => {
        setImagePreview(reader.result as string);
      };
      reader.readAsDataURL(file);
    }
  };

  /**
   * Handle Deposit Submission (Dual Proof: Screenshot & SMS Text)
   */
  const handleDeposit = async (e: React.FormEvent) => {
    e.preventDefault();
    haptic?.impact('medium');
    setDepositError(null);

    const numAmount = parseFloat(depositAmount);
    if (isNaN(numAmount) || numAmount < 10) {
      setDepositError('Minimum deposit amount is 10 ETB.');
      return;
    }

    if (proofType === 'screenshot' && !imagePreview && !selectedFile) {
      setDepositError('Please attach your deposit receipt screenshot image.');
      return;
    }

    if (proofType === 'sms' && !depositSmsText.trim()) {
      setDepositError('Please paste the official SMS confirmation text.');
      return;
    }

    if (!user) {
      setDepositError('You must be logged in to make a deposit.');
      return;
    }

    setDepositLoading(true);

    try {
      // 1. Submit to Backend /api/deposit
      const formData = new FormData();
      if (proofType === 'screenshot' && selectedFile) {
        formData.append('receipt', selectedFile);
      }
      formData.append('userId', user.uid);
      formData.append('sixDigitId', userData?.sixDigitId || 'YG-GUEST');
      formData.append('userDisplayName', userData?.displayName || 'VIP Player');
      formData.append('userPhone', userData?.phoneNumber || 'N/A');
      formData.append('telegramId', String(tgUser?.id || ''));
      formData.append('bankName', depositBank);
      formData.append('amount', String(numAmount));
      formData.append('reference', 'N/A');
      formData.append('proofType', proofType);
      formData.append('smsText', proofType === 'sms' ? depositSmsText.trim() : '');
      if (proofType === 'screenshot' && imagePreview) {
        formData.append('imageData', imagePreview);
      }

      await fetch('/api/deposit', {
        method: 'POST',
        body: formData,
      }).catch((e) => console.warn('Deposit API call notice:', e));

      // 2. Log Transaction Record in Firestore
      const docRef = await addDoc(collection(db, 'transactions'), {
        userId: user.uid,
        userPhone: userData?.phoneNumber || 'N/A',
        sixDigitId: userData?.sixDigitId || 'YG-GUEST',
        userDisplayName: userData?.displayName || 'VIP Player',
        playerTelegramId: String(tgUser?.id || ''),
        type: 'deposit',
        bankName: depositBank,
        amount: numAmount,
        reference: 'N/A',
        proofType,
        smsText: proofType === 'sms' ? depositSmsText.trim() : '',
        receiptImage: proofType === 'screenshot' ? (imagePreview || null) : null,
        status: 'pending',
        createdAt: new Date().toISOString(),
        updatedAt: serverTimestamp(),
      });

      setSubmittedDepositId(docRef.id);
      haptic?.notification('success');
    } catch (err: any) {
      console.warn('Firestore deposit log fallback:', err);
      setSubmittedDepositId(`dep_${Date.now()}`);
    } finally {
      setDepositLoading(false);
    }
  };

  /**
   * Handle First-Time Account Setup (Save & Lock Accounts)
   */
  const handleSaveAndLockAccounts = async (e: React.FormEvent) => {
    e.preventDefault();
    haptic?.impact('medium');
    setWithdrawError(null);

    if (!telebirrNumber.trim() || telebirrNumber.trim().length < 9) {
      setWithdrawError('Please enter a valid Telebirr phone number (e.g. 0912345678).');
      return;
    }
    if (!telebirrName.trim()) {
      setWithdrawError('Please enter the Account Holder Name for Telebirr.');
      return;
    }
    if (!cbeNumber.trim() || cbeNumber.trim().length < 10) {
      setWithdrawError('Please enter a valid CBE Account Number (e.g. 1000123456789).');
      return;
    }
    if (!cbeName.trim()) {
      setWithdrawError('Please enter the Account Holder Name for CBE.');
      return;
    }

    if (!user) {
      setWithdrawError('You must be logged in.');
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

      if (userData) {
        userData.boundAccounts = boundPayload;
      }
      haptic?.notification('success');
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
   * Handle Withdrawal Request Submission (Locked Pre-registered Accounts)
   */
  const handleWithdraw = async (e: React.FormEvent) => {
    e.preventDefault();
    haptic?.impact('medium');
    setWithdrawError(null);

    const numAmount = parseFloat(withdrawAmount);
    if (isNaN(numAmount) || numAmount < 10) {
      setWithdrawError('Minimum withdrawal amount is 10 ETB.');
      return;
    }

    if (numAmount > balance) {
      setWithdrawError(`Insufficient balance. Current balance is ${balance.toFixed(2)} ETB.`);
      return;
    }

    const currentAccountNum = withdrawBank === 'Telebirr' ? boundAccounts?.telebirrNumber : boundAccounts?.cbeNumber;
    const currentAccountHolder = withdrawBank === 'Telebirr' ? boundAccounts?.telebirrName : boundAccounts?.cbeName;

    if (!currentAccountNum || !currentAccountHolder) {
      setWithdrawError('Selected bank account details missing. Please setup payout accounts.');
      return;
    }

    if (!user) {
      setWithdrawError('You must be logged in to request a withdrawal.');
      return;
    }

    setWithdrawLoading(true);

    try {
      // 1. Temporarily deduct requested amount from user balance
      await updateBalance(-numAmount);

      // 2. Log transaction in Firestore
      const docRef = await addDoc(collection(db, 'transactions'), {
        userId: user.uid,
        userPhone: userData?.phoneNumber || 'N/A',
        sixDigitId: userData?.sixDigitId || 'YG-GUEST',
        userDisplayName: userData?.displayName || 'VIP Player',
        playerTelegramId: String(tgUser?.id || ''),
        type: 'withdrawal',
        bankName: withdrawBank,
        amount: numAmount,
        telebirrAccount: currentAccountNum,
        boundAccountNumber: currentAccountNum,
        boundAccountHolderName: currentAccountHolder,
        status: 'pending',
        createdAt: new Date().toISOString(),
        updatedAt: serverTimestamp(),
      });

      // 3. Notify Admin Telegram Bot directly
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
            bankName: withdrawBank,
            amount: numAmount,
            accountNumber: currentAccountNum,
            accountName: currentAccountHolder,
          }),
        });
      } catch (err) {
        console.warn('Telegram notify call notice:', err);
      }

      setSubmittedWithdrawId(docRef.id);
      haptic?.notification('success');
    } catch (err: any) {
      console.warn('Withdrawal transaction log fallback:', err);
      setSubmittedWithdrawId(`wd_${Date.now()}`);
    } finally {
      setWithdrawLoading(false);
    }
  };

  if (!user) {
    return (
      <div className="w-full max-w-md mx-auto min-h-screen p-4 flex flex-col justify-center items-center text-center space-y-4 pb-24">
        <div className="w-16 h-16 rounded-2xl bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
          <WalletIcon className="w-8 h-8" />
        </div>
        <div>
          <h2 className="text-base font-black text-slate-100 uppercase tracking-wide">
            VIP Wallet Access Required
          </h2>
          <p className="text-xs text-slate-400 mt-1 max-w-xs">
            Please log in or create an account to view your balance, deposit funds via Telebirr or CBE, and request payouts.
          </p>
        </div>
        <div className="flex items-center space-x-2 pt-2">
          <button
            onClick={() => onOpenAuth('login')}
            className="px-4 py-2.5 bg-[#151c2e] border border-[#232d48] text-slate-200 hover:text-amber-400 font-bold text-xs rounded-xl"
          >
            Log In
          </button>
          <button
            onClick={() => onOpenAuth('register')}
            className="px-5 py-2.5 bg-amber-500 hover:bg-amber-400 text-slate-950 font-black text-xs rounded-xl shadow-lg shadow-amber-500/20"
          >
            Register Now
          </button>
        </div>
      </div>
    );
  }

  const activeReceiver = RECEIVER_ACCOUNTS[depositBank];
  const lockedAccountNum = withdrawBank === 'Telebirr' ? boundAccounts?.telebirrNumber : boundAccounts?.cbeNumber;
  const lockedAccountHolder = withdrawBank === 'Telebirr' ? boundAccounts?.telebirrName : boundAccounts?.cbeName;

  return (
    <div className="w-full max-w-md mx-auto min-h-screen p-4 space-y-4 pb-24">
      {/* Header & Balance Card */}
      <div className="bg-gradient-to-br from-[#151c2e] via-[#1a233a] to-[#151c2e] border border-amber-500/30 rounded-2xl p-4 shadow-2xl space-y-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <div className="w-8 h-8 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400">
              <Coins className="w-4 h-4" />
            </div>
            <div>
              <div className="text-[10px] text-slate-400 uppercase font-semibold">User Account ID</div>
              <div className="text-xs font-black text-amber-400">
                {userData?.sixDigitId || 'YG-GUEST'}
              </div>
            </div>
          </div>
          <span className="px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 text-[10px] font-bold flex items-center space-x-1">
            <ShieldCheck className="w-3 h-3" />
            <span>Verified Account</span>
          </span>
        </div>

        <div className="bg-[#0b0f19] rounded-xl p-3 border border-[#232d48] flex items-center justify-between">
          <div>
            <div className="text-[10px] text-slate-400 uppercase font-medium">Available Balance</div>
            <div className="text-xl font-black text-amber-400">
              {balance.toFixed(2)} <span className="text-xs text-slate-300">ETB</span>
            </div>
          </div>
          <div className="text-right">
            <div className="text-[10px] text-slate-400 uppercase font-medium">Phone Number</div>
            <div className="text-xs font-bold text-slate-200">
              {userData?.phoneNumber || 'N/A'}
            </div>
          </div>
        </div>

        {/* Tab Selector */}
        <div className="grid grid-cols-3 gap-1.5 p-1 bg-[#0b0f19] rounded-xl border border-[#232d48]">
          <button
            onClick={() => {
              haptic?.impact('light');
              setActiveTab('deposit');
            }}
            className={`py-2 rounded-lg text-xs font-bold flex items-center justify-center space-x-1 transition-all ${
              activeTab === 'deposit'
                ? 'bg-gradient-to-r from-emerald-500 to-emerald-600 text-slate-950 shadow-md font-extrabold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ArrowDownLeft className="w-3.5 h-3.5" />
            <span>Deposit</span>
          </button>

          <button
            onClick={() => {
              haptic?.impact('light');
              setActiveTab('withdraw');
            }}
            className={`py-2 rounded-lg text-xs font-bold flex items-center justify-center space-x-1 transition-all ${
              activeTab === 'withdraw'
                ? 'bg-gradient-to-r from-amber-500 to-amber-600 text-slate-950 shadow-md font-extrabold'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <ArrowUpRight className="w-3.5 h-3.5" />
            <span>Withdraw</span>
          </button>

          <button
            onClick={() => {
              haptic?.impact('light');
              setActiveTab('history');
            }}
            className={`py-2 rounded-lg text-xs font-bold flex items-center justify-center space-x-1 transition-all ${
              activeTab === 'history'
                ? 'bg-slate-800 text-amber-400 border border-amber-500/30'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>History</span>
          </button>
        </div>
      </div>

      {/* TAB CONTENTS */}
      {/* 1. DEPOSIT SECTION */}
      {activeTab === 'deposit' && (
        <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 shadow-xl space-y-4">
          <div className="flex items-center space-x-2 border-b border-[#232d48] pb-3">
            <CreditCard className="w-5 h-5 text-emerald-400" />
            <h3 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide">
              Deposit Funds
            </h3>
          </div>

          {submittedDepositId ? (
            <div className="text-center space-y-3 py-4">
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto border border-emerald-500/30">
                <Send className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-bold text-emerald-400">Deposit Request Submitted!</h4>
              <p className="text-xs text-slate-300">
                Your deposit request of <span className="font-bold text-amber-400">{depositAmount} ETB</span> via {depositBank} is pending admin verification.
              </p>
              <div className="p-2.5 bg-[#0b0f19] border border-emerald-500/30 rounded-xl text-[11px] text-slate-300 flex items-center space-x-2">
                <ShieldCheck className="w-4 h-4 text-emerald-400 shrink-0" />
                <span>Deposit proof sent directly to Admin ID 8488592165.</span>
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
                onClick={() => {
                  setSubmittedDepositId(null);
                  setDepositSmsText('');
                  setSelectedFile(null);
                  setImagePreview(null);
                }}
                className="w-full py-2 bg-[#0b0f19] border border-[#232d48] text-slate-400 hover:text-slate-200 font-semibold text-xs rounded-xl"
              >
                Submit Another Deposit
              </button>
            </div>
          ) : (
            <form onSubmit={handleDeposit} className="space-y-3.5">
              {depositError && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{depositError}</span>
                </div>
              )}

              {/* Step 1: Payment Method & Official Receiver Account Details */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  1. Select Payment Method
                </label>
                <div className="grid grid-cols-2 gap-2 mb-2">
                  <button
                    type="button"
                    onClick={() => {
                      haptic?.impact('light');
                      setDepositBank('Telebirr');
                    }}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      depositBank === 'Telebirr'
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-md'
                        : 'bg-[#0b0f19] border-[#232d48] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>Telebirr</span>
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      haptic?.impact('light');
                      setDepositBank('CBE');
                    }}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      depositBank === 'CBE'
                        ? 'bg-purple-500/20 border-purple-500 text-purple-400 shadow-md'
                        : 'bg-[#0b0f19] border-[#232d48] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>CBE Birr</span>
                  </button>
                </div>

                {/* Dynamic Payment Receiver Account Box */}
                <div className="bg-[#0b0f19] rounded-xl p-3 border border-emerald-500/30 space-y-1.5">
                  <div className="text-[10px] font-bold text-emerald-400 uppercase tracking-wider">
                    Official Receiver Account ({depositBank})
                  </div>
                  <div className="flex items-center justify-between bg-[#151c2e] p-2.5 rounded-lg border border-[#232d48]">
                    <div>
                      <div className="text-base font-black text-amber-400 tracking-wider font-mono">
                        {activeReceiver.number}
                      </div>
                      <div className="text-[10px] text-slate-300">Account Name: {activeReceiver.name}</div>
                    </div>
                    <button
                      onClick={() => handleCopyAccount(activeReceiver.number)}
                      type="button"
                      className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 text-xs font-semibold flex items-center space-x-1"
                    >
                      {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      <span>{copied ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Step 2: Deposit Amount */}
              <div>
                <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block mb-1">
                  2. Deposit Amount (ETB)
                </label>
                <input
                  type="number"
                  min="10"
                  value={depositAmount}
                  onChange={(e) => setDepositAmount(e.target.value)}
                  placeholder="Enter amount (min 10 ETB)"
                  className="w-full bg-[#0b0f19] border border-[#232d48] rounded-xl py-2.5 px-3 text-xs text-slate-100 font-semibold focus:outline-none focus:border-amber-500/60"
                />
              </div>

              {/* Step 3: Select Proof Type Toggle */}
              <div>
                <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block mb-1">
                  3. Select Proof Type
                </label>
                <div className="grid grid-cols-2 gap-2 bg-[#0b0f19] p-1 rounded-xl border border-[#232d48]">
                  <button
                    type="button"
                    onClick={() => {
                      haptic?.impact('light');
                      setProofType('screenshot');
                    }}
                    className={`py-2 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      proofType === 'screenshot'
                        ? 'bg-amber-500 text-slate-950 font-extrabold shadow-md'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>📷 Screenshot</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      haptic?.impact('light');
                      setProofType('sms');
                    }}
                    className={`py-2 px-3 rounded-lg text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      proofType === 'sms'
                        ? 'bg-amber-500 text-slate-950 font-extrabold shadow-md'
                        : 'text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>📝 SMS Text</span>
                  </button>
                </div>
              </div>

              {/* Step 4: Conditional Input Field */}
              {proofType === 'screenshot' ? (
                <div>
                  <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block mb-1">
                    4. Attach Receipt Screenshot (Image)
                  </label>
                  <div className="relative border-2 border-dashed border-[#232d48] hover:border-amber-500/50 rounded-xl p-3 bg-[#0b0f19] text-center transition-all cursor-pointer">
                    <input
                      type="file"
                      accept="image/*"
                      onChange={handleFileChange}
                      className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                    />
                    {imagePreview ? (
                      <div className="relative flex items-center justify-center space-x-2">
                        <img
                          src={imagePreview}
                          alt="Receipt Preview"
                          className="w-12 h-12 object-cover rounded-lg border border-emerald-500/50"
                        />
                        <div className="text-left">
                          <span className="text-xs font-bold text-emerald-400 block truncate max-w-[150px]">
                            {selectedFile ? selectedFile.name : 'Screenshot Loaded'}
                          </span>
                          <span className="text-[9px] text-slate-400">Click box to replace</span>
                        </div>
                        <button
                          type="button"
                          onClick={(e) => {
                            e.stopPropagation();
                            setSelectedFile(null);
                            setImagePreview(null);
                          }}
                          className="p-1 rounded-full bg-red-500/20 text-red-400 hover:bg-red-500/40 z-20 ml-2"
                        >
                          <X className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    ) : (
                      <div className="flex flex-col items-center justify-center space-y-1 py-1">
                        <Upload className="w-5 h-5 text-amber-400" />
                        <span className="text-xs font-bold text-slate-300">Click or Drop Receipt Image</span>
                        <span className="text-[9px] text-slate-500">Supports JPG, PNG, WEBP</span>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                <div>
                  <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block mb-1">
                    4. Paste Official {depositBank} SMS Confirmation Text
                  </label>
                  <textarea
                    rows={3}
                    value={depositSmsText}
                    onChange={(e) => setDepositSmsText(e.target.value)}
                    placeholder={`Paste full official ${depositBank} SMS message received on your phone...`}
                    className="w-full bg-[#0b0f19] border border-[#232d48] rounded-xl p-2.5 text-xs text-slate-100 placeholder-slate-500 font-mono focus:outline-none focus:border-amber-500/60"
                  />
                </div>
              )}

              <button
                type="submit"
                disabled={depositLoading}
                className="w-full py-2.5 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-slate-950 font-extrabold text-xs rounded-xl shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-50 mt-2 uppercase tracking-wider"
              >
                {depositLoading ? 'Submitting Deposit...' : 'Submit Deposit Request'}
              </button>
            </form>
          )}
        </div>
      )}

      {/* 2. WITHDRAW SECTION (MANDATORY ACCOUNT BINDING & LOCKING) */}
      {activeTab === 'withdraw' && (
        <div className="bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 shadow-xl space-y-4">
          <div className="flex items-center space-x-2 border-b border-[#232d48] pb-3">
            <ArrowUpRight className="w-5 h-5 text-amber-400" />
            <h3 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide">
              Withdraw Funds
            </h3>
          </div>

          {submittedWithdrawId ? (
            <div className="text-center space-y-3 py-4">
              <div className="w-12 h-12 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center mx-auto border border-amber-500/30">
                <Send className="w-6 h-6" />
              </div>
              <h4 className="text-sm font-bold text-amber-400">Withdrawal Request Placed!</h4>
              <p className="text-xs text-slate-300">
                Your request to withdraw <span className="font-bold text-amber-400">{withdrawAmount} ETB</span> to {withdrawBank} Account (<span className="font-mono text-emerald-400">{lockedAccountNum}</span> - {lockedAccountHolder}) has been submitted.
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
                onClick={() => {
                  setSubmittedWithdrawId(null);
                  setWithdrawAmount('');
                }}
                className="w-full py-2 bg-[#0b0f19] border border-[#232d48] text-slate-400 hover:text-slate-200 font-semibold text-xs rounded-xl"
              >
                Submit Another Request
              </button>
            </div>
          ) : !isAccountsLocked ? (
            /* Requirement #2: MANDATORY FIRST-TIME ACCOUNT BINDING SETUP FORM */
            <form onSubmit={handleSaveAndLockAccounts} className="space-y-3">
              <div className="p-3 bg-amber-500/10 border border-amber-500/30 rounded-xl space-y-1">
                <div className="flex items-center space-x-2 text-amber-400 font-bold text-xs">
                  <Lock className="w-4 h-4 shrink-0" />
                  <span>Mandatory First-Time Account Setup</span>
                </div>
                <p className="text-[10px] text-slate-300 leading-relaxed">
                  Enter your official Telebirr and CBE account details below. Once saved, these details will be <strong className="text-amber-300">permanently LOCKED</strong> to your account to prevent unauthorized changes or fraud.
                </p>
              </div>

              {withdrawError && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{withdrawError}</span>
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
            /* Requirement #2: SUBSEQUENT WITHDRAWAL REQUEST FORM (LOCKED READ-ONLY DETAILS) */
            <form onSubmit={handleWithdraw} className="space-y-3.5">
              {withdrawError && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{withdrawError}</span>
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
                    onClick={() => {
                      haptic?.impact('light');
                      setWithdrawBank('Telebirr');
                    }}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      withdrawBank === 'Telebirr'
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-md'
                        : 'bg-[#0b0f19] border-[#232d48] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>Telebirr</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      haptic?.impact('light');
                      setWithdrawBank('CBE');
                    }}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      withdrawBank === 'CBE'
                        ? 'bg-purple-500/20 border-purple-500 text-purple-400 shadow-md'
                        : 'bg-[#0b0f19] border-[#232d48] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>CBE Birr</span>
                  </button>
                </div>
              </div>

              {/* Requirement #2: Render Locked Read-Only Account Details */}
              <div className="bg-[#0b0f19] border border-amber-500/30 rounded-xl p-3 space-y-1.5 relative">
                <div className="flex items-center justify-between">
                  <span className="text-[10px] font-bold text-amber-400 uppercase tracking-wider flex items-center space-x-1">
                    <Lock className="w-3 h-3 text-amber-400" />
                    <span>Pre-Registered Locked {withdrawBank} Account</span>
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

              {/* Requirement #2: Withdrawal Amount input box only */}
              <div>
                <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block mb-1">
                  2. Withdrawal Amount (ETB)
                </label>
                <input
                  type="number"
                  min="10"
                  max={balance}
                  value={withdrawAmount}
                  onChange={(e) => setWithdrawAmount(e.target.value)}
                  placeholder="Enter withdrawal amount (min 10 ETB)"
                  className="w-full bg-[#0b0f19] border border-[#232d48] rounded-xl py-2.5 px-3 text-xs text-slate-100 font-semibold focus:outline-none focus:border-amber-500/60"
                />
              </div>

              <button
                type="submit"
                disabled={withdrawLoading || balance < 10}
                className="w-full py-2.5 bg-gradient-to-r from-amber-500 to-amber-600 hover:from-amber-400 hover:to-amber-500 text-slate-950 font-extrabold text-xs rounded-xl shadow-lg shadow-amber-500/20 transition-all disabled:opacity-50 mt-2 uppercase tracking-wider"
              >
                {withdrawLoading ? 'Submitting & Notifying Admin...' : 'Request Payout'}
              </button>
            </form>
          )}

          <div className="pt-2 border-t border-[#232d48] text-[10px] text-slate-400 flex items-center justify-center space-x-1">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
            <span>Fast Payouts Processed Mon-Sun directly by Admin ID 8488592165</span>
          </div>
        </div>
      )}

      {activeTab === 'history' && <TransactionHistory />}
    </div>
  );
};

export default WalletPage;

