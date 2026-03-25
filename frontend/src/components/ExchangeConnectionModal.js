import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Loader2, Key, Link2, Unlink, CheckCircle, AlertCircle, 
  Upload, ExternalLink, RefreshCw, Shield, List, ArrowUpRight, ArrowDownLeft
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const SUPPORTED_EXCHANGES = [
  { id: 'coinbase', name: 'Coinbase', hasPassphrase: false },
  { id: 'kraken', name: 'Kraken', hasPassphrase: false },
  { id: 'binance', name: 'Binance', hasPassphrase: false },
  { id: 'gemini', name: 'Gemini', hasPassphrase: false },
  { id: 'kucoin', name: 'KuCoin', hasPassphrase: true },
  { id: 'cryptocom', name: 'Crypto.com', hasPassphrase: false },
  { id: 'okx', name: 'OKX', hasPassphrase: true },
  { id: 'bybit', name: 'Bybit', hasPassphrase: false },
  { id: 'gateio', name: 'Gate.io', hasPassphrase: false },
];

export const ExchangeConnectionModal = ({ isOpen, onClose }) => {
  const { getAuthHeader, user } = useAuth();
  const [selectedExchange, setSelectedExchange] = useState('coinbase');
  const [apiKey, setApiKey] = useState('');
  const [apiSecret, setApiSecret] = useState('');
  const [passphrase, setPassphrase] = useState('');
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [connections, setConnections] = useState([]);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [transactions, setTransactions] = useState([]);
  const [loadingTransactions, setLoadingTransactions] = useState(false);
  const [txSummary, setTxSummary] = useState(null);

  useEffect(() => {
    if (isOpen) {
      fetchConnections();
      fetchTransactions();
    }
  }, [isOpen]);

  const fetchConnections = async () => {
    setLoadingConnections(true);
    try {
      const response = await axios.get(`${API}/exchanges/api-connections`, {
        headers: getAuthHeader()
      });
      setConnections(response.data.connections || []);
    } catch (err) {
      console.error('Failed to fetch connections:', err);
    } finally {
      setLoadingConnections(false);
    }
  };

  const fetchTransactions = async () => {
    setLoadingTransactions(true);
    try {
      const response = await axios.get(`${API}/exchanges/transactions?limit=100`, {
        headers: getAuthHeader()
      });
      setTransactions(response.data.transactions || []);
      setTxSummary(response.data.summary || null);
    } catch (err) {
      console.error('Failed to fetch transactions:', err);
    } finally {
      setLoadingTransactions(false);
    }
  };

  const handleConnect = async () => {
    setError('');
    setSuccess('');
    
    if (!apiKey || !apiSecret) {
      setError('Please enter both API Key and API Secret');
      return;
    }

    const exchange = SUPPORTED_EXCHANGES.find(e => e.id === selectedExchange);
    if (exchange?.hasPassphrase && !passphrase) {
      setError('This exchange requires a passphrase');
      return;
    }

    setLoading(true);
    try {
      await axios.post(
        `${API}/exchanges/connect-api`,
        {
          exchange: selectedExchange,
          api_key: apiKey,
          api_secret: apiSecret,
          passphrase: passphrase || null
        },
        { headers: getAuthHeader() }
      );
      
      setSuccess(`${exchange?.name || selectedExchange} connected successfully!`);
      setApiKey('');
      setApiSecret('');
      setPassphrase('');
      fetchConnections();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to connect exchange');
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = async (exchangeId) => {
    try {
      await axios.delete(`${API}/exchanges/disconnect-api/${exchangeId}`, {
        headers: getAuthHeader()
      });
      setSuccess(`${exchangeId} disconnected`);
      fetchConnections();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to disconnect');
    }
  };

  const handleSyncTransactions = async (exchangeId) => {
    setSyncing(true);
    setError('');
    setSuccess('');
    try {
      const response = await axios.post(
        `${API}/exchanges/sync-${exchangeId}`,
        {},
        { headers: getAuthHeader() }
      );
      setSuccess(`Synced ${response.data.synced_count} transactions from ${exchangeId}`);
      fetchTransactions(); // Refresh transactions after sync
    } catch (err) {
      setError(err.response?.data?.detail || `Failed to sync ${exchangeId} transactions`);
    } finally {
      setSyncing(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  const getTxTypeIcon = (txType) => {
    const type = txType?.toLowerCase();
    if (['buy', 'receive', 'deposit', 'reward'].includes(type)) {
      return <ArrowDownLeft className="w-4 h-4 text-green-400" />;
    }
    return <ArrowUpRight className="w-4 h-4 text-red-400" />;
  };

  const getTxTypeBadge = (txType) => {
    const type = txType?.toLowerCase();
    const colors = {
      buy: 'bg-green-600',
      sell: 'bg-red-600',
      deposit: 'bg-blue-600',
      withdrawal: 'bg-orange-600',
      reward: 'bg-purple-600',
      trade: 'bg-yellow-600',
      receive: 'bg-green-600',
      send: 'bg-red-600',
    };
    return colors[type] || 'bg-gray-600';
  };

  const selectedExchangeInfo = SUPPORTED_EXCHANGES.find(e => e.id === selectedExchange);
  const isPaidUser = user?.subscription_tier !== 'free';

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-3xl bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto" data-testid="exchange-connection-modal">
        <DialogHeader>
          <DialogTitle className="text-white text-xl flex items-center gap-2">
            <Key className="w-5 h-5 text-purple-400" />
            Exchange Connections
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Connect exchanges via API or view synced transactions
          </DialogDescription>
        </DialogHeader>

        {!isPaidUser && (
          <Alert className="bg-yellow-900/20 border-yellow-700 text-yellow-300">
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              Exchange API connections require an Unlimited subscription.
            </AlertDescription>
          </Alert>
        )}

        <Tabs defaultValue="transactions" className="w-full">
          <TabsList className="grid w-full grid-cols-3 bg-slate-700">
            <TabsTrigger value="transactions" className="data-[state=active]:bg-purple-600">
              <List className="w-4 h-4 mr-2" />
              Transactions ({transactions.length})
            </TabsTrigger>
            <TabsTrigger value="connect" className="data-[state=active]:bg-purple-600">
              Connect New
            </TabsTrigger>
            <TabsTrigger value="manage" className="data-[state=active]:bg-purple-600">
              Manage ({connections.length})
            </TabsTrigger>
          </TabsList>

          {/* Transactions Tab */}
          <TabsContent value="transactions" className="space-y-4 mt-4">
            {loadingTransactions ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-purple-400" />
              </div>
            ) : transactions.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <List className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>No transactions yet</p>
                <p className="text-sm">Connect an exchange and sync, or import a CSV</p>
              </div>
            ) : (
              <>
                {/* Summary */}
                {txSummary && (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-4">
                    <div className="bg-slate-700 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-white">{txSummary.total_transactions}</p>
                      <p className="text-xs text-gray-400">Total</p>
                    </div>
                    <div className="bg-slate-700 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-green-400">{txSummary.by_type?.buy || 0}</p>
                      <p className="text-xs text-gray-400">Buys</p>
                    </div>
                    <div className="bg-slate-700 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-red-400">{txSummary.by_type?.sell || 0}</p>
                      <p className="text-xs text-gray-400">Sells</p>
                    </div>
                    <div className="bg-slate-700 rounded-lg p-3 text-center">
                      <p className="text-2xl font-bold text-purple-400">{Object.keys(txSummary.by_asset || {}).length}</p>
                      <p className="text-xs text-gray-400">Assets</p>
                    </div>
                  </div>
                )}

                {/* Transactions List */}
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {transactions.map((tx, idx) => (
                    <div 
                      key={tx.tx_id || idx}
                      className="bg-slate-700 rounded-lg p-3 flex items-center justify-between"
                    >
                      <div className="flex items-center gap-3">
                        {getTxTypeIcon(tx.tx_type)}
                        <div>
                          <div className="flex items-center gap-2">
                            <Badge className={`${getTxTypeBadge(tx.tx_type)} text-xs`}>
                              {tx.tx_type?.toUpperCase()}
                            </Badge>
                            <span className="text-white font-medium">
                              {tx.amount?.toFixed(6)} {tx.asset}
                            </span>
                          </div>
                          <p className="text-xs text-gray-400">
                            {formatDate(tx.timestamp)} • {tx.exchange}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        {tx.total_usd && (
                          <p className="text-white font-medium">${tx.total_usd.toFixed(2)}</p>
                        )}
                        {tx.price_usd && (
                          <p className="text-xs text-gray-400">@ ${tx.price_usd.toFixed(2)}</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>

                <Button 
                  variant="outline" 
                  onClick={fetchTransactions}
                  className="w-full border-slate-600 text-gray-300"
                >
                  <RefreshCw className="w-4 h-4 mr-2" />
                  Refresh Transactions
                </Button>
              </>
            )}
          </TabsContent>

          {/* Connect Tab */}
          <TabsContent value="connect" className="space-y-4 mt-4">
            {/* Exchange Selection */}
            <div>
              <label className="text-sm text-gray-300 mb-2 block">Select Exchange</label>
              <div className="grid grid-cols-3 gap-2">
                {SUPPORTED_EXCHANGES.map(exchange => (
                  <Button
                    key={exchange.id}
                    variant={selectedExchange === exchange.id ? "default" : "outline"}
                    className={`${selectedExchange === exchange.id 
                      ? 'bg-purple-600 text-white' 
                      : 'bg-slate-700 text-gray-300 border-slate-600 hover:bg-slate-600'}`}
                    onClick={() => setSelectedExchange(exchange.id)}
                    disabled={!isPaidUser}
                  >
                    {exchange.name}
                  </Button>
                ))}
              </div>
            </div>

            {/* API Key Instructions */}
            <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
              <h4 className="text-white font-medium mb-2 flex items-center gap-2">
                <Shield className="w-4 h-4 text-green-400" />
                How to get your {selectedExchangeInfo?.name} API Key
              </h4>
              <ol className="text-sm text-gray-400 space-y-1 list-decimal list-inside">
                <li>Log in to your {selectedExchangeInfo?.name} account</li>
                <li>Go to Settings → API Management</li>
                <li>Create a new API key with <span className="text-yellow-400">READ-ONLY</span> permissions</li>
                <li>Copy the API Key and Secret</li>
              </ol>
              <p className="text-xs text-green-400 mt-2">
                We only need read access to view your transactions. Never enable trading permissions.
              </p>
            </div>

            {/* API Credentials Form */}
            <div className="space-y-3">
              <div>
                <label className="text-sm text-gray-300 mb-1 block">API Key</label>
                <Input
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Enter your API key"
                  className="bg-slate-700 border-slate-600 text-white"
                  disabled={!isPaidUser}
                  data-testid="exchange-api-key-input"
                />
              </div>
              <div>
                <label className="text-sm text-gray-300 mb-1 block">API Secret</label>
                <Input
                  type="password"
                  value={apiSecret}
                  onChange={(e) => setApiSecret(e.target.value)}
                  placeholder="Enter your API secret"
                  className="bg-slate-700 border-slate-600 text-white"
                  disabled={!isPaidUser}
                  data-testid="exchange-api-secret-input"
                />
              </div>
              {selectedExchangeInfo?.hasPassphrase && (
                <div>
                  <label className="text-sm text-gray-300 mb-1 block">Passphrase</label>
                  <Input
                    type="password"
                    value={passphrase}
                    onChange={(e) => setPassphrase(e.target.value)}
                    placeholder="Enter your API passphrase"
                    className="bg-slate-700 border-slate-600 text-white"
                    disabled={!isPaidUser}
                  />
                </div>
              )}
            </div>

            {error && (
              <Alert className="bg-red-900/20 border-red-700 text-red-300">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="bg-green-900/20 border-green-700 text-green-300">
                <CheckCircle className="h-4 w-4" />
                <AlertDescription>{success}</AlertDescription>
              </Alert>
            )}

            <Button
              onClick={handleConnect}
              disabled={loading || !isPaidUser || !apiKey || !apiSecret}
              className="w-full bg-purple-600 hover:bg-purple-700"
              data-testid="connect-exchange-button"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Connecting...
                </>
              ) : (
                <>
                  <Link2 className="mr-2 h-4 w-4" />
                  Connect {selectedExchangeInfo?.name}
                </>
              )}
            </Button>
          </TabsContent>

          {/* Manage Tab */}
          <TabsContent value="manage" className="space-y-4 mt-4">
            {loadingConnections ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-purple-400" />
              </div>
            ) : connections.length === 0 ? (
              <div className="text-center py-8 text-gray-400">
                <Key className="h-12 w-12 mx-auto mb-3 opacity-50" />
                <p>No exchanges connected yet</p>
                <p className="text-sm">Connect an exchange to get started</p>
              </div>
            ) : (
              <div className="space-y-3">
                {connections.map(conn => (
                  <div 
                    key={conn.exchange}
                    className="bg-slate-700 rounded-lg p-4 flex items-center justify-between"
                  >
                    <div className="flex items-center gap-3">
                      <CheckCircle className="h-5 w-5 text-green-400" />
                      <div>
                        <p className="text-white font-medium capitalize">{conn.exchange}</p>
                        <p className="text-xs text-gray-400">
                          Connected {conn.connected_at ? new Date(conn.connected_at).toLocaleDateString() : 'recently'}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {conn.exchange === 'coinbase' && (
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => handleSyncTransactions(conn.exchange)}
                          disabled={syncing}
                          className="bg-slate-600 border-slate-500 text-white hover:bg-slate-500"
                        >
                          {syncing ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <RefreshCw className="h-4 w-4 mr-1" />
                              Sync
                            </>
                          )}
                        </Button>
                      )}
                      <Button
                        size="sm"
                        variant="destructive"
                        onClick={() => handleDisconnect(conn.exchange)}
                        className="bg-red-600 hover:bg-red-700"
                      >
                        <Unlink className="h-4 w-4 mr-1" />
                        Disconnect
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}

            {error && (
              <Alert className="bg-red-900/20 border-red-700 text-red-300">
                <AlertCircle className="h-4 w-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="bg-green-900/20 border-green-700 text-green-300">
                <CheckCircle className="h-4 w-4" />
                <AlertDescription>{success}</AlertDescription>
              </Alert>
            )}
          </TabsContent>
        </Tabs>

        <div className="border-t border-slate-700 pt-4 mt-4">
          <p className="text-xs text-gray-500 text-center">
            Your API credentials are encrypted and stored securely. We only request read-only access.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
