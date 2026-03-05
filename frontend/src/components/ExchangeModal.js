import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  Loader2, 
  Link2, 
  RefreshCw, 
  Trash2, 
  Check,
  AlertCircle,
  ArrowUpRight,
  ArrowDownLeft,
  Coins
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Coinbase Logo SVG
const CoinbaseLogo = () => (
  <svg viewBox="0 0 1024 1024" className="w-8 h-8">
    <circle cx="512" cy="512" r="512" fill="#0052FF"/>
    <path d="M512 256c-141.4 0-256 114.6-256 256s114.6 256 256 256 256-114.6 256-256-114.6-256-256-256zm-62 334h124c8.8 0 16-7.2 16-16v-124c0-8.8-7.2-16-16-16H450c-8.8 0-16 7.2-16 16v124c0 8.8 7.2 16 16 16z" fill="white"/>
  </svg>
);

// Binance Logo SVG
const BinanceLogo = () => (
  <svg viewBox="0 0 126.61 126.61" className="w-8 h-8">
    <g fill="#F3BA2F">
      <polygon points="38.73 53.98 63.3 29.4 87.89 53.99 102.22 39.66 63.3 0.73 24.39 39.64 38.73 53.98"/>
      <polygon points="0.73 63.3 15.06 48.97 29.39 63.3 15.06 77.63 0.73 63.3"/>
      <polygon points="38.73 72.63 63.3 97.21 87.88 72.62 102.22 86.93 63.3 125.88 24.4 86.97 24.38 86.95 38.73 72.63"/>
      <polygon points="97.22 63.31 111.55 48.98 125.88 63.31 111.55 77.64 97.22 63.31"/>
      <polygon points="77.83 63.3 63.3 48.77 52.42 59.64 51.09 60.98 48.78 63.29 63.3 77.82 77.83 63.3"/>
    </g>
  </svg>
);

export const ExchangeModal = ({ isOpen, onClose, getAuthHeader }) => {
  const [loading, setLoading] = useState(true);
  const [connectedExchanges, setConnectedExchanges] = useState([]);
  const [supportedExchanges, setSupportedExchanges] = useState([]);
  const [connecting, setConnecting] = useState(null);
  const [syncing, setSyncing] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Connection form state
  const [showConnectForm, setShowConnectForm] = useState(null);
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [accessToken, setAccessToken] = useState('');
  
  // Transactions state
  const [transactions, setTransactions] = useState([]);
  const [transactionSummary, setTransactionSummary] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetchData();
    }
  }, [isOpen]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [supportedRes, connectedRes] = await Promise.all([
        axios.get(`${API}/exchanges/supported`),
        axios.get(`${API}/exchanges/connected`, { headers: getAuthHeader() })
      ]);
      
      setSupportedExchanges(supportedRes.data.exchanges);
      setConnectedExchanges(connectedRes.data.exchanges);
      
      // Fetch transactions if any exchanges connected
      if (connectedRes.data.exchanges.length > 0) {
        await fetchTransactions();
      }
    } catch (err) {
      if (err.response?.status !== 403) {
        setError('Failed to load exchange data');
      }
    } finally {
      setLoading(false);
    }
  };

  const fetchTransactions = async () => {
    try {
      const response = await axios.get(`${API}/exchanges/transactions`, {
        headers: getAuthHeader(),
        params: { limit: 50 }
      });
      setTransactions(response.data.transactions);
      setTransactionSummary(response.data.summary);
    } catch (err) {
      console.error('Error fetching transactions:', err);
    }
  };

  const handleConnect = async (exchangeId) => {
    setConnecting(exchangeId);
    setError('');
    setSuccess('');

    try {
      const payload = { exchange: exchangeId };
      
      if (exchangeId === 'coinbase') {
        payload.access_token = accessToken;
      } else if (exchangeId === 'binance') {
        payload.api_key = apiKey;
        payload.api_secret = apiSecret;
      }

      await axios.post(`${API}/exchanges/connect`, payload, {
        headers: getAuthHeader()
      });

      setSuccess(`Successfully connected to ${exchangeId}`);
      setShowConnectForm(null);
      setApiKey('');
      setApiSecret('');
      setAccessToken('');
      
      // Refresh data
      await fetchData();
      
    } catch (err) {
      setError(err.response?.data?.detail || `Failed to connect to ${exchangeId}`);
    } finally {
      setConnecting(null);
    }
  };

  const handleSync = async (exchangeId) => {
    setSyncing(exchangeId);
    setError('');
    setSuccess('');

    try {
      const response = await axios.post(
        `${API}/exchanges/${exchangeId}/sync`,
        {},
        { headers: getAuthHeader() }
      );

      setSuccess(response.data.message);
      await fetchTransactions();
      await fetchData();
      
    } catch (err) {
      setError(err.response?.data?.detail || `Failed to sync ${exchangeId}`);
    } finally {
      setSyncing(null);
    }
  };

  const handleDisconnect = async (exchangeId) => {
    if (!window.confirm(`Are you sure you want to disconnect ${exchangeId}?`)) {
      return;
    }

    try {
      await axios.delete(`${API}/exchanges/${exchangeId}`, {
        headers: getAuthHeader()
      });

      setSuccess(`Disconnected from ${exchangeId}`);
      await fetchData();
      
    } catch (err) {
      setError(err.response?.data?.detail || `Failed to disconnect ${exchangeId}`);
    }
  };

  const getExchangeLogo = (exchangeId) => {
    if (exchangeId === 'coinbase') return <CoinbaseLogo />;
    if (exchangeId === 'binance') return <BinanceLogo />;
    return <Coins className="w-8 h-8 text-gray-400" />;
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const isConnected = (exchangeId) => {
    return connectedExchanges.some(e => e.exchange === exchangeId);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-3xl bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto" data-testid="exchange-modal">
        <DialogHeader>
          <DialogTitle className="text-white text-2xl flex items-center gap-2" data-testid="exchange-modal-title">
            <Link2 className="w-6 h-6 text-purple-400" />
            Exchange Integrations
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Connect your exchange accounts to import trade history for tax tracking
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12" data-testid="exchange-loading">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Error/Success Messages */}
            {error && (
              <Alert className="bg-red-900/20 border-red-700 text-red-300" data-testid="exchange-error">
                <AlertCircle className="w-4 h-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            
            {success && (
              <Alert className="bg-green-900/20 border-green-700 text-green-300" data-testid="exchange-success">
                <Check className="w-4 h-4" />
                <AlertDescription>{success}</AlertDescription>
              </Alert>
            )}

            {/* Exchange Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4" data-testid="exchange-cards">
              {supportedExchanges.map((exchange) => {
                const connected = isConnected(exchange.id);
                const connectedData = connectedExchanges.find(e => e.exchange === exchange.id);
                
                return (
                  <Card 
                    key={exchange.id} 
                    className={`border-slate-700 ${connected ? 'bg-green-900/10 border-green-700/50' : 'bg-slate-900/50'}`}
                    data-testid={`exchange-card-${exchange.id}`}
                  >
                    <CardHeader className="pb-2">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {getExchangeLogo(exchange.id)}
                          <div>
                            <CardTitle className="text-white text-lg">{exchange.name}</CardTitle>
                            {connected && (
                              <Badge className="bg-green-900/50 text-green-300 text-xs mt-1">
                                Connected
                              </Badge>
                            )}
                          </div>
                        </div>
                      </div>
                    </CardHeader>
                    <CardContent>
                      <p className="text-sm text-gray-400 mb-4">{exchange.description}</p>
                      
                      {connected ? (
                        <div className="space-y-3">
                          <div className="text-xs text-gray-500">
                            Last synced: {formatDate(connectedData?.last_sync)}
                          </div>
                          <div className="flex gap-2">
                            <Button
                              onClick={() => handleSync(exchange.id)}
                              disabled={syncing === exchange.id}
                              size="sm"
                              className="flex-1 bg-purple-600 hover:bg-purple-700"
                            >
                              {syncing === exchange.id ? (
                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                              ) : (
                                <RefreshCw className="w-4 h-4 mr-2" />
                              )}
                              Sync
                            </Button>
                            <Button
                              onClick={() => handleDisconnect(exchange.id)}
                              size="sm"
                              variant="outline"
                              className="border-red-700 text-red-400 hover:bg-red-900/30"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>
                      ) : showConnectForm === exchange.id ? (
                        <div className="space-y-3" data-testid={`connect-form-${exchange.id}`}>
                          {exchange.id === 'binance' && (
                            <>
                              <Input
                                placeholder="API Key"
                                value={apiKey}
                                onChange={(e) => setApiKey(e.target.value)}
                                className="bg-slate-800 border-slate-600 text-white"
                                data-testid="binance-api-key-input"
                              />
                              <Input
                                type="password"
                                placeholder="API Secret"
                                value={apiSecret}
                                onChange={(e) => setApiSecret(e.target.value)}
                                className="bg-slate-800 border-slate-600 text-white"
                                data-testid="binance-api-secret-input"
                              />
                              <p className="text-xs text-gray-500">
                                Create API keys in your Binance account settings. Only enable "Read" permissions.
                              </p>
                            </>
                          )}
                          
                          {exchange.id === 'coinbase' && (
                            <>
                              <Input
                                placeholder="OAuth Access Token"
                                value={accessToken}
                                onChange={(e) => setAccessToken(e.target.value)}
                                className="bg-slate-800 border-slate-600 text-white"
                                data-testid="coinbase-token-input"
                              />
                              <p className="text-xs text-gray-500">
                                Complete Coinbase OAuth flow to get your access token.
                              </p>
                            </>
                          )}
                          
                          <div className="flex gap-2">
                            <Button
                              onClick={() => handleConnect(exchange.id)}
                              disabled={connecting === exchange.id}
                              size="sm"
                              className="flex-1 bg-purple-600 hover:bg-purple-700"
                              data-testid={`connect-submit-${exchange.id}`}
                            >
                              {connecting === exchange.id ? (
                                <Loader2 className="w-4 h-4 animate-spin mr-2" />
                              ) : (
                                <Check className="w-4 h-4 mr-2" />
                              )}
                              Connect
                            </Button>
                            <Button
                              onClick={() => setShowConnectForm(null)}
                              size="sm"
                              variant="outline"
                              className="border-slate-600"
                            >
                              Cancel
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <Button
                          onClick={() => setShowConnectForm(exchange.id)}
                          size="sm"
                          className="w-full bg-slate-700 hover:bg-slate-600"
                          data-testid={`connect-button-${exchange.id}`}
                        >
                          <Link2 className="w-4 h-4 mr-2" />
                          Connect {exchange.name}
                        </Button>
                      )}
                    </CardContent>
                  </Card>
                );
              })}
            </div>

            {/* Transaction Summary */}
            {transactionSummary && transactionSummary.total_transactions > 0 && (
              <Card className="bg-slate-900/50 border-slate-700" data-testid="transaction-summary">
                <CardHeader>
                  <CardTitle className="text-white">Imported Transactions Summary</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-white">
                        {transactionSummary.total_transactions}
                      </div>
                      <div className="text-sm text-gray-400">Total Transactions</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-400">
                        {transactionSummary.by_type?.buy || 0}
                      </div>
                      <div className="text-sm text-gray-400">Buys</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-red-400">
                        {transactionSummary.by_type?.sell || 0}
                      </div>
                      <div className="text-sm text-gray-400">Sells</div>
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-orange-400">
                        ${transactionSummary.total_fees_usd?.toFixed(2) || '0.00'}
                      </div>
                      <div className="text-sm text-gray-400">Total Fees</div>
                    </div>
                  </div>
                  
                  {/* Asset breakdown */}
                  {Object.keys(transactionSummary.by_asset || {}).length > 0 && (
                    <div className="mt-4 pt-4 border-t border-slate-700">
                      <div className="text-sm text-gray-400 mb-2">Assets Traded</div>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(transactionSummary.by_asset).map(([asset, data]) => (
                          <Badge key={asset} className="bg-slate-700">
                            {asset}: {data.total} trades
                          </Badge>
                        ))}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Recent Transactions */}
            {transactions.length > 0 && (
              <Card className="bg-slate-900/50 border-slate-700" data-testid="exchange-transactions">
                <CardHeader>
                  <CardTitle className="text-white">Recent Exchange Transactions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-64 overflow-y-auto">
                    {transactions.slice(0, 10).map((tx, idx) => (
                      <div 
                        key={idx}
                        className="flex items-center justify-between py-2 border-b border-slate-700 last:border-0"
                      >
                        <div className="flex items-center gap-3">
                          {tx.tx_type === 'buy' || tx.tx_type === 'receive' ? (
                            <ArrowDownLeft className="w-4 h-4 text-green-400" />
                          ) : (
                            <ArrowUpRight className="w-4 h-4 text-red-400" />
                          )}
                          <div>
                            <span className="text-white font-medium">
                              {tx.amount?.toFixed(6)} {tx.asset}
                            </span>
                            <span className="text-gray-400 text-sm ml-2">
                              ({tx.tx_type})
                            </span>
                          </div>
                        </div>
                        <div className="text-right">
                          <Badge className="bg-slate-700 text-xs">{tx.exchange}</Badge>
                          <div className="text-xs text-gray-500 mt-1">
                            {formatDate(tx.timestamp)}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Info Note */}
            <Alert className="bg-blue-900/20 border-blue-700 text-blue-300">
              <AlertCircle className="w-4 h-4" />
              <AlertDescription>
                Exchange data is synced on-demand. Click "Sync" to import your latest transactions.
                This data will be combined with your on-chain analysis for comprehensive tax reporting.
              </AlertDescription>
            </Alert>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
