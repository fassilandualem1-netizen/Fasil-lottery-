import React, { useEffect, useState } from 'react';
import { useAuth } from '../../context/AuthContext';
import { collection, query, where, onSnapshot } from 'firebase/firestore';
import { db } from '../../firebase/config';
import { TransactionRecord } from '../../types';
import { Skeleton } from '../ui/Skeleton';
import { ArrowDownLeft, ArrowUpRight, Clock, CheckCircle2, XCircle, History } from 'lucide-react';

export const TransactionHistory: React.FC = () => {
  const { user } = useAuth();
  const [transactions, setTransactions] = useState<TransactionRecord[]>([]);
  const [filter, setFilter] = useState<'all' | 'deposit' | 'withdrawal'>('all');
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    if (!user) {
      setTransactions([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    const txRef = collection(db, 'transactions');
    const q = query(txRef, where('userId', '==', user.uid));

    const unsubscribe = onSnapshot(
      q,
      (snapshot) => {
        const docs: TransactionRecord[] = [];
        snapshot.forEach((docSnap) => {
          docs.push({ id: docSnap.id, ...docSnap.data() } as TransactionRecord);
        });

        // Sort descending by createdAt
        docs.sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime());

        setTransactions(docs);
        setLoading(false);
      },
      (error) => {
        console.warn('Transaction history listener error:', error);
        setLoading(false);
      }
    );

    return () => unsubscribe();
  }, [user]);

  const filteredTxs = transactions.filter((tx) => {
    if (filter === 'all') return true;
    return tx.type === filter;
  });

  const getStatusBadge = (status: TransactionRecord['status']) => {
    switch (status) {
      case 'approved':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 flex items-center space-x-1">
            <CheckCircle2 className="w-3 h-3" />
            <span>Approved</span>
          </span>
        );
      case 'rejected':
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-red-500/10 text-red-400 border border-red-500/30 flex items-center space-x-1">
            <XCircle className="w-3 h-3" />
            <span>Rejected</span>
          </span>
        );
      default:
        return (
          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-500/10 text-amber-400 border border-amber-500/30 flex items-center space-x-1">
            <Clock className="w-3 h-3 animate-pulse" />
            <span>Pending</span>
          </span>
        );
    }
  };

  return (
    <div className="w-full bg-[#151c2e] border border-[#232d48] rounded-2xl p-4 shadow-xl space-y-4">
      {/* Header & Filter Tabs */}
      <div className="flex items-center justify-between border-b border-[#232d48] pb-3">
        <div className="flex items-center space-x-2">
          <History className="w-4 h-4 text-amber-400" />
          <h3 className="text-xs font-extrabold text-slate-100 uppercase tracking-wide">
            Transaction History
          </h3>
        </div>

        <div className="flex items-center space-x-1 bg-[#0b0f19] p-0.5 rounded-lg border border-[#232d48]">
          <button
            onClick={() => setFilter('all')}
            className={`px-2 py-1 text-[10px] font-bold rounded-md transition-all ${
              filter === 'all'
                ? 'bg-amber-500 text-slate-950'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            All
          </button>
          <button
            onClick={() => setFilter('deposit')}
            className={`px-2 py-1 text-[10px] font-bold rounded-md transition-all ${
              filter === 'deposit'
                ? 'bg-amber-500 text-slate-950'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Deposits
          </button>
          <button
            onClick={() => setFilter('withdrawal')}
            className={`px-2 py-1 text-[10px] font-bold rounded-md transition-all ${
              filter === 'withdrawal'
                ? 'bg-amber-500 text-slate-950'
                : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Withdraws
          </button>
        </div>
      </div>

      {/* Transaction List */}
      <div className="space-y-2.5 max-h-72 overflow-y-auto pr-1">
        {loading ? (
          <div className="space-y-2">
            <Skeleton height={52} />
            <Skeleton height={52} />
            <Skeleton height={52} />
          </div>
        ) : filteredTxs.length === 0 ? (
          <div className="text-center py-6 text-slate-500 text-xs">
            No {filter !== 'all' ? filter : ''} transactions found.
          </div>
        ) : (
          filteredTxs.map((tx) => (
            <div
              key={tx.id}
              className="bg-[#0b0f19] border border-[#232d48] rounded-xl p-3 flex items-center justify-between"
            >
              <div className="flex items-center space-x-3">
                <div
                  className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                    tx.type === 'deposit'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }`}
                >
                  {tx.type === 'deposit' ? (
                    <ArrowDownLeft className="w-4 h-4" />
                  ) : (
                    <ArrowUpRight className="w-4 h-4" />
                  )}
                </div>

                <div>
                  <div className="text-xs font-bold text-slate-200 capitalize">
                    {tx.type}
                  </div>
                  <div className="text-[10px] text-slate-400">
                    {tx.reference ? `Ref: ${tx.reference}` : tx.telebirrAccount ? `Acc: ${tx.telebirrAccount}` : ''}
                  </div>
                  <div className="text-[9px] text-slate-500">
                    {new Date(tx.createdAt).toLocaleDateString()} {new Date(tx.createdAt).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                  </div>
                </div>
              </div>

              <div className="text-right space-y-1">
                <div
                  className={`text-xs font-extrabold ${
                    tx.type === 'deposit' ? 'text-emerald-400' : 'text-amber-400'
                  }`}
                >
                  {tx.type === 'deposit' ? '+' : '-'}{tx.amount.toFixed(2)} ETB
                </div>
                <div>{getStatusBadge(tx.status)}</div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
};

export default TransactionHistory;
