import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Wallet, Trash2, Plus, ExternalLink } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

const CHAIN_ICONS = {
  ethereum: '⟠',
  bitcoin: '₿',
  polygon: '🔺',
  arbitrum: '🔷',
  bsc: '🟡',
  solana: '◎'
};

const CHAIN_COLORS = {
  ethereum: 'bg-blue-500',
  bitcoin: 'bg-orange-500',
  polygon: 'bg-purple-500',
  arbitrum: 'bg-cyan-500',
  bsc: 'bg-yellow-500',
  solana: 'bg-indigo-500'
};

export const SavedWallets = ({ getAuthHeader, onSelectWallet, userTier }) => {
  const [wallets, setWallets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  const [newWallet, setNewWallet] = useState({
    address: '',
    nickname: '',
    chain: 'ethereum'
  });

  useEffect(() => {
    fetchWallets();
  }, []);

  const fetchWallets = async () => {
    try {
      const response = await axios.get(
        `${API}/api/wallets/saved`,
        { headers: getAuthHeader() }
      );
      let fetchedWallets = response.data.wallets || [];
      
      // Filter to show only Ethereum wallets for free tier users
      if (userTier === 'free') {
        fetchedWallets = fetchedWallets.filter(w => w.chain === 'ethereum');
      }
      
      setWallets(fetchedWallets);
    } catch (err) {
      console.error('Error fetching wallets:', err);
    }
  };

  const handleAddWallet = async () => {
    setError('');
    setSuccess('');
    setLoading(true);

    try {
      await axios.post(
        `${API}/api/wallets/save`,
        newWallet,
        { headers: getAuthHeader() }
      );
      
      setSuccess('Wallet saved successfully!');
      setNewWallet({ address: '', nickname: '', chain: 'ethereum' });
      setShowAddModal(false);
      fetchWallets();
      
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save wallet');
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteWallet = async (walletId) => {
    if (!window.confirm('Are you sure you want to delete this wallet?')) return;

    try {
      await axios.delete(
        `${API}/api/wallets/saved/${walletId}`,
        { headers: getAuthHeader() }
      );
      fetchWallets();
      setSuccess('Wallet deleted successfully!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to delete wallet');
      setTimeout(() => setError(''), 3000);
    }
  };

  const handleAnalyze = (wallet) => {
    onSelectWallet(wallet.address, wallet.chain);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h3 className="text-xl font-semibold text-white flex items-center gap-2">
          <Wallet className="w-5 h-5" />
          My Saved Wallets
        </h3>
        <Button
          onClick={() => setShowAddModal(true)}
          className="bg-purple-600 hover:bg-purple-700"
        >
          <Plus className="w-4 h-4 mr-2" />
          Add Wallet
        </Button>
      </div>

      {/* Success/Error Messages */}
      {success && (
        <Alert className="bg-green-900/20 border-green-700 text-green-300">
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert className="bg-red-900/20 border-red-700 text-red-300">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Wallets List */}
      {wallets.length === 0 ? (
        <div className="text-center py-12 bg-slate-800/50 rounded-lg border border-slate-700">
          <Wallet className="w-12 h-12 mx-auto text-gray-500 mb-4" />
          <p className="text-gray-400 mb-4">No saved wallets yet</p>
          <Button
            onClick={() => setShowAddModal(true)}
            variant="outline"
            className="border-slate-600"
          >
            Add Your First Wallet
          </Button>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {wallets.map((wallet) => (
            <div
              key={wallet.id}
              className="bg-slate-800/50 rounded-lg border border-slate-700 p-4 hover:border-purple-500 transition-all"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className={`w-8 h-8 rounded-full ${CHAIN_COLORS[wallet.chain]} flex items-center justify-center text-white text-lg`}>
                    {CHAIN_ICONS[wallet.chain]}
                  </span>
                  <div>
                    <h4 className="text-white font-semibold">{wallet.nickname}</h4>
                    <p className="text-xs text-gray-400 capitalize">{wallet.chain}</p>
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteWallet(wallet.id)}
                  className="text-red-400 hover:text-red-300"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>

              <div className="bg-slate-900/50 rounded p-2 mb-3">
                <p className="text-gray-300 text-sm font-mono truncate">
                  {wallet.address}
                </p>
              </div>

              <Button
                onClick={() => handleAnalyze(wallet)}
                className="w-full bg-purple-600 hover:bg-purple-700"
                size="sm"
              >
                <ExternalLink className="w-4 h-4 mr-2" />
                Analyze
              </Button>
            </div>
          ))}
        </div>
      )}

      {/* Add Wallet Modal */}
      <Dialog open={showAddModal} onOpenChange={setShowAddModal}>
        <DialogContent className="sm:max-w-md bg-slate-800 border-slate-700">
          <DialogHeader>
            <DialogTitle className="text-white">Add New Wallet</DialogTitle>
            <DialogDescription className="text-gray-400">
              Save a wallet address for quick access
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <div>
              <Label htmlFor="nickname" className="text-gray-300">Nickname</Label>
              <Input
                id="nickname"
                placeholder="My Main Wallet"
                value={newWallet.nickname}
                onChange={(e) => setNewWallet({...newWallet, nickname: e.target.value})}
                className="bg-slate-900 border-slate-600 text-white"
              />
            </div>

            <div>
              <Label htmlFor="chain" className="text-gray-300">Blockchain</Label>
              <select
                id="chain"
                value={newWallet.chain}
                onChange={(e) => setNewWallet({...newWallet, chain: e.target.value})}
                className="w-full bg-slate-900 border border-slate-600 text-white rounded-md px-3 py-2"
              >
                <option value="ethereum">Ethereum</option>
                <option value="bitcoin" disabled={userTier === 'free'}>
                  Bitcoin {userTier === 'free' ? '🔒 Premium' : ''}
                </option>
                <option value="polygon" disabled={userTier === 'free'}>
                  Polygon {userTier === 'free' ? '🔒 Premium' : ''}
                </option>
                <option value="arbitrum" disabled={userTier === 'free'}>
                  Arbitrum {userTier === 'free' ? '🔒 Premium' : ''}
                </option>
                <option value="bsc" disabled={userTier === 'free'}>
                  BNB Smart Chain {userTier === 'free' ? '🔒 Premium' : ''}
                </option>
                <option value="solana" disabled={userTier === 'free'}>
                  Solana {userTier === 'free' ? '🔒 Premium' : ''}
                </option>
              </select>
            </div>

            <div>
              <Label htmlFor="address" className="text-gray-300">Wallet Address</Label>
              <Input
                id="address"
                placeholder={newWallet.chain === 'ethereum' ? '0x...' : 'Address'}
                value={newWallet.address}
                onChange={(e) => setNewWallet({...newWallet, address: e.target.value})}
                className="bg-slate-900 border-slate-600 text-white font-mono text-sm"
              />
            </div>

            {error && (
              <Alert className="bg-red-900/20 border-red-700 text-red-300">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex gap-2">
              <Button
                onClick={handleAddWallet}
                disabled={loading || !newWallet.address || !newWallet.nickname}
                className="flex-1 bg-purple-600 hover:bg-purple-700"
              >
                {loading ? 'Saving...' : 'Save Wallet'}
              </Button>
              <Button
                onClick={() => setShowAddModal(false)}
                variant="outline"
                className="flex-1 border-slate-600"
              >
                Cancel
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
};
