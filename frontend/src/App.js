import { useState } from 'react';
import '@/App.css';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, Wallet, TrendingUp, TrendingDown, DollarSign, Activity } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [walletAddress, setWalletAddress] = useState('');
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState('');
  const [history, setHistory] = useState([]);

  const analyzeWallet = async () => {
    if (!walletAddress || !walletAddress.startsWith('0x') || walletAddress.length !== 42) {
      setError('Please enter a valid Ethereum address (0x...)');
      return;
    }

    setLoading(true);
    setError('');
    setAnalysis(null);

    try {
      const response = await axios.post(`${API}/wallet/analyze`, {
        address: walletAddress
      });
      setAnalysis(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to analyze wallet. Please try again.');
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

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      <div className="container mx-auto px-4 py-8">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="flex items-center justify-center gap-3 mb-4">
            <Wallet className="w-12 h-12 text-purple-400" />
            <h1 className="text-5xl font-bold text-white">Crypto Wallet Tracker</h1>
          </div>
          <p className="text-gray-300 text-lg">
            Analyze your Ethereum wallet transactions and calculate costs
          </p>
        </div>

        {/* Input Section */}
        <Card className="max-w-3xl mx-auto mb-8 bg-slate-800/50 border-slate-700" data-testid="wallet-input-card">
          <CardHeader>
            <CardTitle className="text-white">Enter Wallet Address</CardTitle>
            <CardDescription className="text-gray-400">
              Enter an Ethereum wallet address to analyze transactions and calculate costs
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <Input
                data-testid="wallet-address-input"
                type="text"
                placeholder="0x..."
                value={walletAddress}
                onChange={(e) => setWalletAddress(e.target.value)}
                className="flex-1 bg-slate-700 border-slate-600 text-white placeholder:text-gray-500"
                disabled={loading}
              />
              <Button
                data-testid="analyze-button"
                onClick={analyzeWallet}
                disabled={loading}
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
            {/* Summary Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
              <Card className="bg-gradient-to-br from-green-900/30 to-green-800/20 border-green-700" data-testid="received-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-green-300 flex items-center gap-2">
                    <TrendingUp className="w-4 h-4" />
                    Total Received
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-white">
                    {formatNumber(analysis.totalEthReceived)} ETH
                  </div>
                  <p className="text-xs text-green-300 mt-1">
                    {analysis.incomingTransactionCount} transactions
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-red-900/30 to-red-800/20 border-red-700" data-testid="sent-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-red-300 flex items-center gap-2">
                    <TrendingDown className="w-4 h-4" />
                    Total Sent
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-white">
                    {formatNumber(analysis.totalEthSent)} ETH
                  </div>
                  <p className="text-xs text-red-300 mt-1">
                    {analysis.outgoingTransactionCount} transactions
                  </p>
                </CardContent>
              </Card>

              <Card className="bg-gradient-to-br from-orange-900/30 to-orange-800/20 border-orange-700" data-testid="gas-fees-card">
                <CardHeader className="pb-3">
                  <CardTitle className="text-sm font-medium text-orange-300 flex items-center gap-2">
                    <Activity className="w-4 h-4" />
                    Gas Fees
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-white">
                    {formatNumber(analysis.totalGasFees)} ETH
                  </div>
                  <p className="text-xs text-orange-300 mt-1">
                    Transaction costs
                  </p>
                </CardContent>
              </Card>

              <Card className={`bg-gradient-to-br ${analysis.netEth >= 0 ? 'from-blue-900/30 to-blue-800/20 border-blue-700' : 'from-purple-900/30 to-purple-800/20 border-purple-700'}`} data-testid="net-card">
                <CardHeader className="pb-3">
                  <CardTitle className={`text-sm font-medium ${analysis.netEth >= 0 ? 'text-blue-300' : 'text-purple-300'} flex items-center gap-2`}>
                    <DollarSign className="w-4 h-4" />
                    Net Balance
                  </CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-bold text-white">
                    {formatNumber(analysis.netEth)} ETH
                  </div>
                  <p className="text-xs text-gray-300 mt-1">
                    {analysis.netEth >= 0 ? 'Profit' : 'Loss'}
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
      </div>
    </div>
  );
}

export default App;
