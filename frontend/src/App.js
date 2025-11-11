import { useState, useEffect } from 'react';
import '@/App.css';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, Wallet, TrendingUp, TrendingDown, DollarSign, Activity, LogOut, User, Crown } from 'lucide-react';
import axios from 'axios';
import { useAuth } from '@/contexts/AuthContext';
import { AuthModal } from '@/components/AuthModal';
import { UpgradeModal } from '@/components/UpgradeModal';
import { SavedWallets } from '@/components/SavedWallets';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const { user, logout, getAuthHeader, loading: authLoading, fetchUserProfile } = useAuth();
  const [walletAddress, setWalletAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState('');
  const [showAuthModal, setShowAuthModal] = useState(false);
  const [showUpgradeModal, setShowUpgradeModal] = useState(false);
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [selectedChain, setSelectedChain] = useState('ethereum');
  const [showSavedWallets, setShowSavedWallets] = useState(false);

  // Check for payment success on component mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');
    
    if (sessionId && user) {
      // Poll payment status
      pollPaymentStatus(sessionId);
    }
  }, [user]);

  const pollPaymentStatus = async (sessionId, attempts = 0) => {
    const maxAttempts = 5;
    
    if (attempts >= maxAttempts) {
      setError('Payment verification timed out. Please check your subscription status.');
      return;
    }

    try {
      const response = await axios.get(
        `${API}/payments/status/${sessionId}`,
        { headers: getAuthHeader() }
      );

      if (response.data.payment_status === 'paid') {
        setPaymentSuccess(true);
        setError('');
        // Refresh user profile to get updated subscription tier
        await fetchUserProfile();
        // Remove session_id from URL
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
      }

      // Continue polling if still pending
      if (response.data.status !== 'expired') {
        setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2000);
      } else {
        setError('Payment session expired.');
      }
    } catch (err) {
      console.error('Error checking payment status:', err);
      if (attempts < maxAttempts) {
        setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2000);
      }
    }
  };

  const getChainSymbol = (chain) => {
    const symbols = {
      ethereum: 'ETH',
      bitcoin: 'BTC',
      arbitrum: 'ETH',
      bsc: 'BNB',
      solana: 'SOL'
    };
    return symbols[chain] || 'ETH';
  };

  const getChainIcon = (chain) => {
    const icons = {
      ethereum: '⟠',
      bitcoin: '₿',
      arbitrum: '🔷',
      bsc: '🟡',
      solana: '◎'
    };
    return icons[chain] || '⟠';
  };

  const analyzeWallet = async (addressOverride = null, chainOverride = null) => {
    if (!user) {
      setShowAuthModal(true);
      return;
    }

    const address = addressOverride || walletAddress;
    const chain = chainOverride || selectedChain;

    // Basic validation - chain-specific
    if (!address) {
      setError('Please enter a wallet address');
      return;
    }

    if (chain === 'ethereum' || chain === 'arbitrum' || chain === 'bsc') {
      if (!address.startsWith('0x') || address.length !== 42) {
        setError('Please enter a valid address (0x...)');
        return;
      }
    }

    setLoading(true);
    setError('');
    setAnalysis(null);

    try {
      const payload = { 
        address: address,
        chain: chain
      };
      
      // Add date range if provided
      if (startDate) {
        payload.start_date = startDate;
      }
      if (endDate) {
        payload.end_date = endDate;
      }
      
      const response = await axios.post(
        `${API}/wallet/analyze`,
        payload,
        { headers: getAuthHeader() }
      );
      setAnalysis(response.data);
      // Refresh user data to update usage count
      await fetchUserProfile();
    } catch (err) {
      if (err.response?.status === 429) {
        setError('Daily limit reached! Upgrade to Premium for unlimited wallet analyses.');
      } else if (err.response?.status === 401) {
        setError('Please login to continue');
        setShowAuthModal(true);
      } else {
        setError(err.response?.data?.detail || 'Failed to analyze wallet. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    try {
      const response = await axios.get(`${API}/wallet/history?limit=5`);
      setHistory(response.data);
    } catch (err) {
      console.error('Failed to load history:', err);
    }
  };

  const formatAddress = (addr) => {
    if (!addr) return '';
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };

  const formatNumber = (num) => {
    if (num === null || num === undefined) return '0';
    return new Intl.NumberFormat('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 6
    }).format(num);
  };

  if (authLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900 flex items-center justify-center">
        <Loader2 className="w-12 h-12 text-purple-400 animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-8">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Wallet className="w-12 h-12 text-purple-400" />
            <h1 className="text-5xl font-bold text-white">ShoeString Wallet Tracker</h1>
          </div>
          <p className="text-gray-300 text-lg">
            Review your transactions on the blockchain. Perfect for taxes.
          </p>
        </div>

        {/* Payment Success Alert */}
        {paymentSuccess && (
          <div className="max-w-3xl mx-auto mb-6">
            <Alert className="bg-green-900/20 border-green-700 text-green-300">
              <AlertDescription className="flex items-center">
                <Crown className="w-4 h-4 mr-2" />
                Payment successful! Your subscription has been upgraded.
              </AlertDescription>
            </Alert>
          </div>
        )}

        {/* User Info Bar */}
        <div className="max-w-3xl mx-auto mb-6">
          {user ? (
            <Card className="bg-slate-800/50 border-slate-700" data-testid="user-info-bar">
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <User className="w-5 h-5 text-purple-400" />
                    <div>
                      <p className="text-white font-medium">{user.email}</p>
                      <div className="flex items-center gap-2 mt-1">
                        <Badge className={`${user.subscription_tier === 'free' ? 'bg-gray-600' : 'bg-purple-600'}`}>
                          {user.subscription_tier === 'premium' && <Crown className="w-3 h-3 mr-1" />}
                          {user.subscription_tier === 'pro' && <Crown className="w-3 h-3 mr-1" />}
                          {user.subscription_tier.toUpperCase()}
                        </Badge>
                        <span className="text-sm text-gray-400">
                          {user.subscription_tier === 'free' 
                            ? `${user.daily_usage_count}/1 analyses today` 
                            : `${user.daily_usage_count} analyses today`}
                        </span>
                        {user.subscription_tier !== 'free' && (
                          <a 
                            href="mailto:support@shoestringwallet.com?subject=Downgrade Request"
                            className="text-xs text-gray-500 hover:text-gray-400 underline ml-2"
                          >
                            manage
                          </a>
                        )}
                      </div>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    {user.subscription_tier !== 'pro' && (
                      <Button 
                        onClick={() => setShowUpgradeModal(true)}
                        className="bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700"
                        data-testid="upgrade-button"
                      >
                        <Crown className="w-4 h-4 mr-2" />
                        {user.subscription_tier === 'free' ? 'Upgrade' : 'Upgrade to Pro'}
                      </Button>
                    )}
                    <Button 
                      variant="outline" 
                      onClick={logout}
                      className="border-slate-600 text-gray-300 hover:bg-slate-700"
                      data-testid="logout-button"
                    >
                      <LogOut className="w-4 h-4 mr-2" />
                      Logout
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ) : (
            <Card className="bg-slate-800/50 border-slate-700" data-testid="login-prompt">
              <CardContent className="py-4">
                <div className="flex items-center justify-between">
                  <p className="text-gray-300">Login to start analyzing wallets</p>
                  <Button 
                    onClick={() => setShowAuthModal(true)}
                    className="bg-purple-600 hover:bg-purple-700"
                    data-testid="login-button"
                  >
                    Login / Sign Up
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Saved Wallets Toggle */}
        {user && (
          <div className="max-w-3xl mx-auto mb-4">
            <Button
              onClick={() => setShowSavedWallets(!showSavedWallets)}
              variant="outline"
              className="border-slate-600 text-gray-300"
            >
              <Wallet className="w-4 h-4 mr-2" />
              {showSavedWallets ? 'Hide' : 'Show'} Saved Wallets
            </Button>
          </div>
        )}

        {/* Saved Wallets Section */}
        {showSavedWallets && user && (
          <div className="max-w-3xl mx-auto mb-8">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="pt-6">
                <SavedWallets 
                  getAuthHeader={getAuthHeader}
                  onSelectWallet={(address, chain) => {
                    setWalletAddress(address);
                    setSelectedChain(chain);
                    setShowSavedWallets(false);
                    analyzeWallet(address, chain);
                  }}
                />
              </CardContent>
            </Card>
          </div>
        )}

        {/* Input Section */}
        <Card className="max-w-3xl mx-auto mb-8 bg-slate-800/50 border-slate-700" data-testid="wallet-input-card">
          <CardHeader>
            <CardTitle className="text-white">Analyze Wallet</CardTitle>
            <CardDescription className="text-gray-400">
              Multi-chain wallet analysis: Ethereum, Bitcoin, Arbitrum, BSC, and Solana
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Chain Selector */}
              <div>
                <label className="text-sm text-gray-400 block mb-2">Blockchain Network</label>
                <select
                  value={selectedChain}
                  onChange={(e) => setSelectedChain(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-600 text-white rounded-md px-3 py-2"
                  disabled={!user}
                >
                  <option value="ethereum">⟠ Ethereum</option>
                  <option value="bitcoin">₿ Bitcoin</option>
                  <option value="arbitrum">🔷 Arbitrum</option>
                  <option value="bsc">🟡 BNB Smart Chain</option>
                  <option value="solana">◎ Solana</option>
                </select>
              </div>

              <div className="flex gap-4">
                <Input
                  data-testid="wallet-address-input"
                  type="text"
                  placeholder={selectedChain === 'ethereum' || selectedChain === 'arbitrum' || selectedChain === 'bsc' ? '0x...' : 'Wallet address'}
                  value={walletAddress}
                  onChange={(e) => setWalletAddress(e.target.value)}
                  className="flex-1 bg-slate-700 border-slate-600 text-white placeholder:text-gray-500"
                  disabled={loading}
                />
                <Button
                  data-testid="analyze-button"
                  onClick={() => analyzeWallet()}
                  disabled={loading || !user}
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
            {error && (
              <Alert className="mt-4 bg-red-900/20 border-red-900 text-red-300" data-testid="error-alert">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>

        {/* Analysis Results */}
        {analysis && (
          <div className="max-w-7xl mx-auto space-y-6" data-testid="analysis-results">
            {/* Chain Badge */}
            <div className="flex items-center gap-2">
              <Badge className="bg-purple-900/50 text-purple-300 border-purple-700">
                {getChainIcon(analysis.chain || selectedChain)} {(analysis.chain || selectedChain).toUpperCase()}
              </Badge>
              <span className="text-gray-400 text-sm">Analyzing {getChainSymbol(analysis.chain || selectedChain)} wallet</span>
            </div>

            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="bg-gradient-to-br from-green-900/30 to-green-800/20 border-green-700" data-testid="received-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-green-300 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />
                    Total Flow In
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-white">
                    {formatNumber(analysis.totalEthReceived)} {getChainSymbol(analysis.chain || selectedChain)}
                  </div>
                  <p className="text-xs text-green-300 mt-1">
                    {analysis.incomingTransactionCount} transactions
                  </p>
                  <p className="text-xs text-gray-400 mt-2">
                    All incoming transfers
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-red-900/30 to-red-800/20 border-red-700" data-testid="sent-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-red-300 flex items-center gap-2">
                    <TrendingDown className="w-4 h-4" />
                    Total Flow Out
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-white">
                    {formatNumber(analysis.totalEthSent)} {getChainSymbol(analysis.chain || selectedChain)}
                  </div>
                  <p className="text-xs text-red-300 mt-1">
                    {analysis.outgoingTransactionCount} transactions
                  </p>
                  <p className="text-xs text-gray-400 mt-2">
                    All outgoing transfers
                  </p>
                </CardContent>
              </Card>

              {(analysis.totalGasFees > 0 || selectedChain === 'ethereum' || selectedChain === 'arbitrum') && (
                <Card className="bg-gradient-to-br from-orange-900/30 to-orange-800/20 border-orange-700" data-testid="gas-fees-card">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-sm font-medium text-orange-300 flex items-center gap-2">
                      <Activity className="w-4 h-4" />
                      Gas Fees
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="text-3xl font-bold text-white">
                      {formatNumber(analysis.totalGasFees)} {getChainSymbol(analysis.chain || selectedChain)}
                    </div>
                    <p className="text-xs text-orange-300 mt-1">
                      Transaction costs
                    </p>
                    <p className="text-xs text-gray-400 mt-2">
                      Network fees paid
                    </p>
                  </CardContent>
                </Card>
              )}

              <Card className={`bg-gradient-to-br ${analysis.netEth >= 0 ? 'from-blue-900/30 to-blue-800/20 border-blue-700' : 'from-purple-900/30 to-purple-800/20 border-purple-700'}`} data-testid="net-card">
                <CardHeader className="pb-3">
                  <CardTitle className={`text-sm font-medium ${analysis.netEth >= 0 ? 'text-blue-300' : 'text-purple-300'} flex items-center gap-2`}>
                    <DollarSign className="w-4 h-4" />
                    Current Balance
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-white">
                    {formatNumber(analysis.netEth)} {getChainSymbol(analysis.chain || selectedChain)}
                  </div>
                  <p className="text-xs text-gray-300 mt-1">
                    Net position
                  </p>
                  <p className="text-xs text-gray-400 mt-2">
                    Received - Sent{analysis.totalGasFees > 0 ? ' - Gas' : ''}
                  </p>
                </CardContent>
              </Card>
            </div>

            {/* Wallet Address Info */}
            <Card className="bg-slate-800/50 border-slate-700" data-testid="wallet-info-card">
              <CardHeader>
                <CardTitle className="text-white">Wallet Information</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Address:</span>
                    <span className="text-white font-mono text-sm">{analysis.address}</span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-gray-400">Total Transactions:</span>
                    <span className="text-white">
                      {analysis.incomingTransactionCount + analysis.outgoingTransactionCount}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* ERC-20 Tokens */}
            {(Object.keys(analysis.tokensSent || {}).length > 0 || Object.keys(analysis.tokensReceived || {}).length > 0) && (
              <Card className="bg-slate-800/50 border-slate-700" data-testid="tokens-card">
                <CardHeader>
                  <CardTitle className="text-white">ERC-20 Token Activity</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {Object.keys(analysis.tokensReceived || {}).length > 0 && (
                      <div>
                        <h3 className="text-green-300 font-semibold mb-3">Tokens Received</h3>
                        <div className="space-y-2">
                          {Object.entries(analysis.tokensReceived).map(([token, amount]) => (
                            <div key={token} className="flex items-center justify-between bg-green-900/10 p-2 rounded">
                              <Badge variant="outline" className="text-green-300 border-green-700">{token}</Badge>
                              <span className="text-white font-mono text-sm">{formatNumber(amount)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                    {Object.keys(analysis.tokensSent || {}).length > 0 && (
                      <div>
                        <h3 className="text-red-300 font-semibold mb-3">Tokens Sent</h3>
                        <div className="space-y-2">
                          {Object.entries(analysis.tokensSent).map(([token, amount]) => (
                            <div key={token} className="flex items-center justify-between bg-red-900/10 p-2 rounded">
                              <Badge variant="outline" className="text-red-300 border-red-700">{token}</Badge>
                              <span className="text-white font-mono text-sm">{formatNumber(amount)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Recent Transactions */}
            {analysis.recentTransactions && analysis.recentTransactions.length > 0 && (
              <Card className="bg-slate-800/50 border-slate-700" data-testid="transactions-table">
                <CardHeader>
                  <CardTitle className="text-white">Recent Transactions</CardTitle>
                  <CardDescription className="text-gray-400">
                    Showing up to 20 most recent transactions
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full">
                      <thead>
                        <tr className="border-b border-slate-700">
                          <th className="text-left py-3 px-4 text-gray-400 font-medium">Type</th>
                          <th className="text-left py-3 px-4 text-gray-400 font-medium">Hash</th>
                          <th className="text-left py-3 px-4 text-gray-400 font-medium">Asset</th>
                          <th className="text-right py-3 px-4 text-gray-400 font-medium">Amount</th>
                          <th className="text-left py-3 px-4 text-gray-400 font-medium">Address</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analysis.recentTransactions.map((tx, idx) => (
                          <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                            <td className="py-3 px-4">
                              <Badge
                                variant="outline"
                                className={tx.type === 'sent' ? 'text-red-300 border-red-700' : 'text-green-300 border-green-700'}
                              >
                                {tx.type === 'sent' ? 'Sent' : 'Received'}
                              </Badge>
                            </td>
                            <td className="py-3 px-4">
                              <a
                                href={`https://etherscan.io/tx/${tx.hash}`}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-purple-400 hover:text-purple-300 font-mono text-sm"
                              >
                                {formatAddress(tx.hash)}
                              </a>
                            </td>
                            <td className="py-3 px-4">
                              <span className="text-white font-medium">{tx.asset}</span>
                            </td>
                            <td className="py-3 px-4 text-right">
                              <span className="text-white font-mono">{formatNumber(tx.value)}</span>
                            </td>
                            <td className="py-3 px-4">
                              <span className="text-gray-400 font-mono text-sm">
                                {tx.type === 'sent' ? formatAddress(tx.to) : formatAddress(tx.from)}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        )}

        {/* Auth Modal */}
        <AuthModal isOpen={showAuthModal} onClose={() => setShowAuthModal(false)} />
        
        {/* Upgrade Modal */}
        <UpgradeModal isOpen={showUpgradeModal} onClose={() => setShowUpgradeModal(false)} />
      </div>
    </div>
  );
}

export default App;
