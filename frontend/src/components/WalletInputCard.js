import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Loader2, Crown } from 'lucide-react';

export const CHAIN_SYMBOLS = {
  ethereum: 'ETH',
  bitcoin: 'BTC',
  polygon: 'MATIC',
  arbitrum: 'ETH',
  bsc: 'BNB',
  solana: 'SOL'
};

export const CHAIN_ICONS = {
  ethereum: '\u27e0',
  bitcoin: '\u20bf',
  polygon: '\ud83d\udd3a',
  arbitrum: '\ud83d\udd37',
  bsc: '\ud83d\udfe1',
  solana: '\u25ce'
};

export const getChainSymbol = (chain) => CHAIN_SYMBOLS[chain] || 'ETH';
export const getChainIcon = (chain) => CHAIN_ICONS[chain] || '\u27e0';

export const WalletInputCard = ({
  user,
  walletAddress,
  setWalletAddress,
  selectedChain,
  setSelectedChain,
  startDate,
  setStartDate,
  endDate,
  setEndDate,
  loading,
  analyzingAll,
  onAnalyze,
  onAnalyzeAll,
  onChainRequest,
  onUpgrade,
  setError
}) => {
  const handleChainChange = (e) => {
    const newChain = e.target.value;
    if (user?.subscription_tier === 'free' && newChain !== 'ethereum') {
      setError('Multi-chain analysis requires Premium. Upgrade to unlock!');
      onUpgrade();
      return;
    }
    setSelectedChain(newChain);
    setError('');
  };

  const getPlaceholder = () => {
    if (['ethereum', 'polygon', 'arbitrum', 'bsc'].includes(selectedChain)) {
      return '0x...';
    }
    if (selectedChain === 'bitcoin') {
      return user?.subscription_tier === 'pro'
        ? 'Address or xPub/yPub/zPub (Pro)'
        : 'Bitcoin address (e.g., 1A1z...)';
    }
    if (selectedChain === 'solana') {
      return 'Solana address (base58)';
    }
    return 'Wallet address';
  };

  return (
    <Card className="bg-slate-800/50 border-slate-700" data-testid="wallet-input-card">
      <CardHeader>
        <CardTitle className="text-white">Analyze Wallet</CardTitle>
        <CardDescription className="text-gray-400">
          Multi-chain wallet analysis: Ethereum, Bitcoin, Polygon, Arbitrum, BSC, and Solana
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Chain Selector */}
          <div>
            <label className="text-sm text-gray-400 block mb-2">
              Blockchain Network
              {user?.subscription_tier === 'free' && (
                <span className="ml-2 text-xs text-purple-400">(Upgrade for multi-chain)</span>
              )}
            </label>
            <select
              value={selectedChain}
              onChange={handleChainChange}
              className="w-full bg-slate-900 border border-slate-600 text-white rounded-md px-3 py-2"
              disabled={!user}
            >
              <option value="ethereum">{CHAIN_ICONS.ethereum} Ethereum</option>
              <option value="bitcoin" disabled={user?.subscription_tier === 'free'}>
                {CHAIN_ICONS.bitcoin} Bitcoin {user?.subscription_tier === 'free' ? '\ud83d\udd12' : ''}
              </option>
              <option value="polygon" disabled={user?.subscription_tier === 'free'}>
                {CHAIN_ICONS.polygon} Polygon {user?.subscription_tier === 'free' ? '\ud83d\udd12' : ''}
              </option>
              <option value="arbitrum" disabled={user?.subscription_tier === 'free'}>
                {CHAIN_ICONS.arbitrum} Arbitrum {user?.subscription_tier === 'free' ? '\ud83d\udd12' : ''}
              </option>
              <option value="bsc" disabled={user?.subscription_tier === 'free'}>
                {CHAIN_ICONS.bsc} BNB Smart Chain {user?.subscription_tier === 'free' ? '\ud83d\udd12' : ''}
              </option>
              <option value="solana" disabled={user?.subscription_tier === 'free'}>
                {CHAIN_ICONS.solana} Solana {user?.subscription_tier === 'free' ? '\ud83d\udd12' : ''}
              </option>
            </select>
            {user?.subscription_tier === 'pro' && (
              <button
                onClick={onChainRequest}
                className="text-xs text-purple-400 hover:text-purple-300 underline mt-2"
              >
                Need a different chain? Request it here
              </button>
            )}
          </div>

          {/* Address Input */}
          <div className="flex gap-4">
            <div className="flex-1">
              <Input
                data-testid="wallet-address-input"
                type="text"
                placeholder={getPlaceholder()}
                value={walletAddress}
                onChange={(e) => setWalletAddress(e.target.value)}
                className="bg-slate-700 border-slate-600 text-white placeholder:text-gray-500"
                disabled={loading}
              />
              {selectedChain === 'bitcoin' && user?.subscription_tier === 'pro' && (
                <p className="text-xs text-gray-400 mt-1">
                  Pro tip: Enter your Ledger xPub to analyze your entire wallet
                </p>
              )}
            </div>
            <Button
              data-testid="analyze-button"
              onClick={() => onAnalyze(walletAddress, selectedChain)}
              disabled={loading || analyzingAll || !user}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Analyzing...
                </>
              ) : (
                'Analyze'
              )}
            </Button>

            {user?.subscription_tier === 'pro' && (
              <Button
                onClick={() => onAnalyzeAll(walletAddress)}
                disabled={loading || analyzingAll || !user}
                className="bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-700 hover:to-orange-700"
              >
                {analyzingAll ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Analyzing All...
                  </>
                ) : (
                  <>
                    <Crown className="mr-2 h-4 w-4" />
                    Analyze All Chains
                  </>
                )}
              </Button>
            )}
          </div>

          {/* Date Range Filter */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-gray-400 block mb-2">Start Date (Optional)</label>
              <Input
                data-testid="start-date-input"
                type="date"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                className="bg-slate-700 border-slate-600 text-white"
                disabled={loading}
              />
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-2">End Date (Optional)</label>
              <Input
                data-testid="end-date-input"
                type="date"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                className="bg-slate-700 border-slate-600 text-white"
                disabled={loading}
              />
            </div>
          </div>

          {(startDate || endDate) && (
            <div className="text-sm text-gray-400">
              Filtering transactions {startDate && `from ${startDate}`} {endDate && `to ${endDate}`}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
