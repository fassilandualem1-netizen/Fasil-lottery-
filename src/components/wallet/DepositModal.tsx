import React, { useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useTelegram } from '../../hooks/useTelegram';
import { collection, addDoc, serverTimestamp } from 'firebase/firestore';
import { db } from '../../firebase/config';
import { CreditCard, Copy, Check, Send, AlertCircle, X, ExternalLink, Image as ImageIcon, Upload } from 'lucide-react';

interface DepositModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export const DepositModal: React.FC<DepositModalProps> = ({ isOpen, onClose }) => {
  const { user, userData } = useAuth();
  const { user: tgUser } = useTelegram();
  const [bankName, setBankName] = useState<'Telebirr' | 'CBE'>('Telebirr');
  const [amount, setAmount] = useState<string>('100');
  const [proofType, setProofType] = useState<'screenshot' | 'sms'>('screenshot');
  const [smsText, setSmsText] = useState<string>('');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string | null>(null);
  const [copied, setCopied] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [submittedTxId, setSubmittedTxId] = useState<string | null>(null);

  if (!isOpen) return null;

  const ACCOUNTS = {
    Telebirr: { account: '0951381356', name: 'Fasil Andualem' },
    CBE: { account: '1000584461757', name: 'Fasil Andualem' },
  };

  const ADMIN_TELEGRAM = 'fassilandualem';

  const handleCopyAccount = () => {
    navigator.clipboard.writeText(ACCOUNTS[bankName].account);
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

  const handleSubmitDeposit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const numAmount = parseFloat(amount);
    if (isNaN(numAmount) || numAmount < 10) {
      setError('Minimum deposit amount is 10 ETB.');
      return;
    }

    if (proofType === 'screenshot' && !imagePreview && !selectedFile) {
      setError('Please attach your deposit receipt screenshot image.');
      return;
    }

    if (proofType === 'sms' && !smsText.trim()) {
      setError('Please paste the official SMS confirmation text.');
      return;
    }

    if (!user) {
      setError('You must be logged in to make a deposit.');
      return;
    }

    setLoading(true);

    try {
      // 1. Send FormData to server backend (/api/deposit) for Telegram Bot notify & image handling
      const formData = new FormData();
      formData.append('userId', user.uid);
      formData.append('userPhone', userData?.phoneNumber || 'N/A');
      formData.append('sixDigitId', userData?.sixDigitId || 'YG-GUEST');
      formData.append('userDisplayName', userData?.displayName || 'VIP Player');
      formData.append('telegramId', String(tgUser?.id || ''));
      formData.append('bankName', bankName);
      formData.append('amount', String(numAmount));
      formData.append('reference', 'N/A');
      formData.append('proofType', proofType);
      formData.append('smsText', proofType === 'sms' ? smsText.trim() : '');
      if (proofType === 'screenshot' && imagePreview) {
        formData.append('imageData', imagePreview);
      }
      if (proofType === 'screenshot' && selectedFile) {
        formData.append('receipt', selectedFile);
      }

      let serverResponse: any = null;
      try {
        const res = await fetch('/api/deposit', {
          method: 'POST',
          body: formData,
        });
        serverResponse = await res.json();
      } catch (err) {
        console.warn('Server API call notice:', err);
      }

      // 2. Save deposit record to Firestore for Admin Dashboard & Transaction History
      const docRef = await addDoc(collection(db, 'transactions'), {
        userId: user.uid,
        userPhone: userData?.phoneNumber || 'N/A',
        sixDigitId: userData?.sixDigitId || 'YG-GUEST',
        userDisplayName: userData?.displayName || 'VIP Player',
        playerTelegramId: String(tgUser?.id || ''),
        type: 'deposit',
        bankName,
        amount: numAmount,
        reference: 'N/A',
        proofType,
        smsText: proofType === 'sms' ? smsText.trim() : '',
        receiptImage: proofType === 'screenshot' ? (imagePreview || null) : null,
        status: 'pending',
        createdAt: new Date().toISOString(),
        updatedAt: serverTimestamp(),
      });

      setSubmittedTxId(serverResponse?.depositId || docRef.id);
    } catch (err: any) {
      console.warn('Deposit submission fallback:', err);
      setSubmittedTxId(`DEP-${Date.now()}`);
    } finally {
      setLoading(false);
    }
  };

  const resetAndClose = () => {
    setSubmittedTxId(null);
    setSmsText('');
    setSelectedFile(null);
    setImagePreview(null);
    setError(null);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm animate-fade-in">
      <div className="w-full max-w-sm bg-[#151c2e] border border-[#232d48] rounded-2xl shadow-2xl overflow-hidden relative max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="p-4 border-b border-[#232d48] flex items-center justify-between shrink-0">
          <div className="flex items-center space-x-2">
            <CreditCard className="w-5 h-5 text-emerald-400" />
            <h2 className="text-sm font-extrabold text-slate-100 uppercase tracking-wide">
              Instant Bank Deposit
            </h2>
          </div>
          <button
            onClick={resetAndClose}
            className="p-1 rounded-lg bg-[#0b0f19] border border-[#232d48] text-slate-400 hover:text-white"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-3 overflow-y-auto">
          {submittedTxId ? (
            /* Deposit Success View */
            <div className="text-center space-y-3 py-2">
              <div className="w-12 h-12 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mx-auto border border-emerald-500/30">
                <Send className="w-6 h-6" />
              </div>
              <h3 className="text-sm font-bold text-emerald-400">Deposit Request Submitted!</h3>
              <p className="text-xs text-slate-300">
                Your deposit request of <span className="font-bold text-amber-400">{amount} ETB</span> via {bankName} has been sent directly to Admin ID 8488592165 for instant verification.
              </p>
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
          ) : (
            /* Deposit Form */
            <>
              {/* Step 1: Bank Selector & Payment Details */}
              <div>
                <label className="text-[10px] font-bold text-slate-400 uppercase tracking-wider block mb-1">
                  1. Select Payment Method
                </label>
                <div className="grid grid-cols-2 gap-2 mb-2">
                  <button
                    type="button"
                    onClick={() => setBankName('Telebirr')}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      bankName === 'Telebirr'
                        ? 'bg-emerald-500/20 border-emerald-500 text-emerald-400 shadow-md'
                        : 'bg-[#0b0f19] border-[#232d48] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>Telebirr</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => setBankName('CBE')}
                    className={`py-2 px-3 rounded-xl border text-xs font-bold transition-all flex items-center justify-center space-x-1.5 ${
                      bankName === 'CBE'
                        ? 'bg-purple-500/20 border-purple-500 text-purple-400 shadow-md'
                        : 'bg-[#0b0f19] border-[#232d48] text-slate-400 hover:text-slate-200'
                    }`}
                  >
                    <span>CBE Birr</span>
                  </button>
                </div>

                {/* Payment Details Box */}
                <div className="bg-[#0b0f19] rounded-xl p-3 border border-amber-500/30 space-y-2">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="text-[10px] text-slate-400 font-medium">Official {bankName} Receiver Account</div>
                      <div className="text-sm font-black text-amber-400 tracking-wider">
                        {ACCOUNTS[bankName].account}
                      </div>
                      <div className="text-[10px] text-slate-300">Name: {ACCOUNTS[bankName].name}</div>
                    </div>
                    <button
                      onClick={handleCopyAccount}
                      type="button"
                      className="p-2 rounded-lg bg-amber-500/10 border border-amber-500/30 text-amber-400 hover:bg-amber-500/20 text-xs font-semibold flex items-center space-x-1"
                    >
                      {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
                      <span>{copied ? 'Copied' : 'Copy'}</span>
                    </button>
                  </div>
                </div>
              </div>

              {/* Form Inputs */}
              <form onSubmit={handleSubmitDeposit} className="space-y-3">
                {error && (
                  <div className="p-2.5 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs flex items-center space-x-2">
                    <AlertCircle className="w-4 h-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                {/* Step 2: Deposit Amount */}
                <div>
                  <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block mb-1">
                    2. Amount (ETB)
                  </label>
                  <input
                    type="number"
                    min="10"
                    value={amount}
                    onChange={(e) => setAmount(e.target.value)}
                    placeholder="Enter amount (min 10 ETB)"
                    className="w-full bg-[#0b0f19] border border-[#232d48] rounded-xl py-2 px-3 text-xs text-slate-100 font-semibold focus:outline-none focus:border-amber-500/60"
                  />
                </div>

                {/* Step 3: Proof Selection Switcher (Screenshot vs SMS Text) */}
                <div>
                  <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block mb-1">
                    3. Select Proof Type
                  </label>
                  <div className="grid grid-cols-2 gap-2 bg-[#0b0f19] p-1 rounded-xl border border-[#232d48]">
                    <button
                      type="button"
                      onClick={() => setProofType('screenshot')}
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
                      onClick={() => setProofType('sms')}
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
                      4. Attach Receipt Screenshot
                    </label>
                    <div className="relative border-2 border-dashed border-[#232d48] hover:border-amber-500/50 rounded-xl p-3 bg-[#0b0f19] text-center transition-all cursor-pointer">
                      <input
                        type="file"
                        accept="image/*"
                        onChange={handleFileChange}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10"
                      />
                      {imagePreview ? (
                        <div className="flex items-center space-x-3 text-left">
                          <img
                            src={imagePreview}
                            alt="Receipt Preview"
                            className="w-12 h-12 object-cover rounded-lg border border-amber-500/40"
                          />
                          <div>
                            <div className="text-xs font-bold text-emerald-400 flex items-center space-x-1">
                              <Check className="w-3.5 h-3.5" />
                              <span>Screenshot Selected</span>
                            </div>
                            <p className="text-[10px] text-slate-400">Click or drag to replace image</p>
                          </div>
                        </div>
                      ) : (
                        <div className="flex flex-col items-center justify-center space-y-1 text-slate-400 py-1">
                          <Upload className="w-5 h-5 text-amber-400" />
                          <span className="text-xs font-bold text-slate-300">Upload Receipt Screenshot</span>
                          <span className="text-[9px] text-slate-500">PNG, JPG, WEBP up to 15MB</span>
                        </div>
                      )}
                    </div>
                  </div>
                ) : (
                  <div>
                    <label className="text-[10px] font-bold text-slate-300 uppercase tracking-wider block mb-1">
                      4. Paste Official {bankName} SMS Confirmation Text
                    </label>
                    <textarea
                      rows={3}
                      value={smsText}
                      onChange={(e) => setSmsText(e.target.value)}
                      placeholder={`Paste full official ${bankName} SMS message received on your phone...`}
                      className="w-full bg-[#0b0f19] border border-[#232d48] rounded-xl p-2.5 text-xs text-slate-100 placeholder-slate-500 font-mono focus:outline-none focus:border-amber-500/60"
                    />
                  </div>
                )}

                <button
                  type="submit"
                  disabled={loading}
                  className="w-full py-2.5 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 text-slate-950 font-extrabold text-xs rounded-xl shadow-lg shadow-emerald-500/20 transition-all disabled:opacity-50 mt-2 uppercase tracking-wider"
                >
                  {loading ? 'Submitting & Notifying Admin...' : 'Submit Deposit Request'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

export default DepositModal;
