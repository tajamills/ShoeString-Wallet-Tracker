/**
 * AddDataModal - Unified Data Import (CoinTracker-style)
 * 
 * Single entry point for all data:
 * 1. Wallet Address (primary) - Enter address to sync on-chain data
 * 2. CSV Import - Upload exchange exports
 * 3. Exchange API - Connect for auto-sync
 * 
 * Updated: December 2025
 */
import React, { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { 
  Loader2, 
  Wallet, 
  Upload, 
  Key, 
  CheckCircle, 
  AlertCircle,
  Plus,
  RefreshCw,
  FileText,
  ArrowRight,
  Calendar,
  Info
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Supported chains for wallet address input
const SUPPORTED_CHAINS = [
  { id: 'ethereum', name: 'Ethereum', prefix: '0x', icon: '⟠' },
  { id: 'bitcoin', name: 'Bitcoin', prefix: 'bc1,1,3,xpub', icon: '₿' },
  { id: 'solana', name: 'Solana', prefix: '', icon: '◎' },
  { id: 'polygon', name: 'Polygon', prefix: '0x', icon: '🔺' },
  { id: 'arbitrum', name: 'Arbitrum', prefix: '0x', icon: '🔷' },
];

// Supported exchanges for CSV import
const SUPPORTED_EXCHANGES = [
  { id: 'coinbase', name: 'Coinbase', color: '#0052FF' },
  { id: 'kraken', name: 'Kraken', color: '#5741D9' },
  { id: 'binance', name: 'Binance', color: '#F3BA2F' },
  { id: 'gemini', name: 'Gemini', color: '#00DCFA' },
  { id: 'ledger', name: 'Ledger Live', color: '#FF5300' },
  { id: 'kucoin', name: 'KuCoin', color: '#24AE8F' },
];

// Auto-detect chain from address format
const detectChainFromAddress = (address) => {
  if (!address || address.length < 10) return null;
  const trimmed = address.trim();
  
  if (trimmed.startsWith('0x') && trimmed.length === 42) return 'ethereum';
  if (trimmed.startsWith('bc1') || trimmed.startsWith('1') || trimmed.startsWith('3') || trimmed.startsWith('xpub')) return 'bitcoin';
  if (trimmed.length >= 32 && trimmed.length <= 44 && /^[1-9A-HJ-NP-Za-km-z]+$/.test(trimmed)) return 'solana';
  
  return null;
};

// Manual Acquisition Form Component
const ManualAcquisitionForm = ({ getAuthHeader, onSuccess, onError }) => {
  const [loading, setLoading] = useState(false);
  const [orphanSummary, setOrphanSummary] = useState(null);
  const [formData, setFormData] = useState({
    asset: '',
    amount: '',
    price_usd: '',
    timestamp: '',
    source: 'OTC/Manual',
    notes: ''
  });

  // Fetch orphan disposal summary on mount
  useEffect(() => {
    fetchOrphanSummary();
  }, []);

  const fetchOrphanSummary = async () => {
    try {
      const response = await axios.get(`${API}/exchanges/orphan-disposal-summary`, {
        headers: getAuthHeader()
      });
      setOrphanSummary(response.data);
    } catch (err) {
      console.error('Error fetching orphan summary:', err);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    onError('');
    
    if (!formData.asset || !formData.amount || !formData.price_usd || !formData.timestamp) {
      onError('Please fill in all required fields');
      return;
    }

    setLoading(true);
    try {
      const response = await axios.post(
        `${API}/exchanges/manual-acquisition`,
        {
          asset: formData.asset.toUpperCase(),
          amount: parseFloat(formData.amount),
          price_usd: parseFloat(formData.price_usd),
          timestamp: formData.timestamp,
          source: formData.source,
          notes: formData.notes || null
        },
        { headers: getAuthHeader() }
      );
      
      onSuccess(`Added ${formData.amount} ${formData.asset.toUpperCase()} acquisition`);
      setFormData({
        asset: '',
        amount: '',
        price_usd: '',
        timestamp: '',
        source: 'OTC/Manual',
        notes: ''
      });
      fetchOrphanSummary(); // Refresh summary
    } catch (err) {
      onError(err.response?.data?.detail || 'Failed to add acquisition');
    } finally {
      setLoading(false);
    }
  };

  const fillFromOrphan = (orphan) => {
    setFormData({
      ...formData,
      asset: orphan.asset,
      amount: orphan.shortfall.toFixed(4),
      timestamp: orphan.first_disposal_date ? orphan.first_disposal_date.split('T')[0] : ''
    });
  };

  return (
    <div className="space-y-4">
      <div className="text-center pb-2">
        <Plus className="w-10 h-10 text-green-400 mx-auto mb-2" />
        <h3 className="text-lg font-semibold text-white">Manual Acquisition Entry</h3>
        <p className="text-xs text-gray-400">
          Add missing buy/acquisition records to fix orphan disposals
        </p>
      </div>

      {/* Orphan Summary Alert */}
      {orphanSummary?.has_orphans && (
        <Alert className="bg-yellow-900/20 border-yellow-700/50 py-2">
          <AlertCircle className="w-4 h-4 text-yellow-400" />
          <AlertDescription className="text-yellow-300 text-xs">
            <strong>{orphanSummary.orphan_assets.length} assets</strong> have orphan disposals. 
            Click an asset below to auto-fill.
          </AlertDescription>
        </Alert>
      )}

      {/* Quick Fill Buttons */}
      {orphanSummary?.orphan_assets?.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {orphanSummary.orphan_assets.slice(0, 6).map((orphan) => (
            <Button
              key={orphan.asset}
              variant="outline"
              size="sm"
              onClick={() => fillFromOrphan(orphan)}
              className="text-xs border-yellow-700 text-yellow-300 hover:bg-yellow-900/30"
              data-testid={`fill-orphan-${orphan.asset.toLowerCase()}`}
            >
              {orphan.asset}: {orphan.shortfall.toFixed(2)}
            </Button>
          ))}
        </div>
      )}

      {/* Manual Entry Form */}
      <form onSubmit={handleSubmit} className="space-y-3">
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-300 mb-1 block">Asset *</label>
            <Input
              value={formData.asset}
              onChange={(e) => setFormData({...formData, asset: e.target.value})}
              placeholder="BTC, ETH, USDC..."
              className="bg-slate-700 border-slate-600 text-white text-sm"
              data-testid="manual-asset-input"
            />
          </div>
          <div>
            <label className="text-xs text-gray-300 mb-1 block">Amount *</label>
            <Input
              type="number"
              step="any"
              value={formData.amount}
              onChange={(e) => setFormData({...formData, amount: e.target.value})}
              placeholder="0.00"
              className="bg-slate-700 border-slate-600 text-white text-sm"
              data-testid="manual-amount-input"
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-gray-300 mb-1 block">Price per Unit (USD) *</label>
            <Input
              type="number"
              step="any"
              value={formData.price_usd}
              onChange={(e) => setFormData({...formData, price_usd: e.target.value})}
              placeholder="0.00"
              className="bg-slate-700 border-slate-600 text-white text-sm"
              data-testid="manual-price-input"
            />
          </div>
          <div>
            <label className="text-xs text-gray-300 mb-1 block">Date Acquired *</label>
            <Input
              type="date"
              value={formData.timestamp}
              onChange={(e) => setFormData({...formData, timestamp: e.target.value})}
              className="bg-slate-700 border-slate-600 text-white text-sm"
              data-testid="manual-date-input"
            />
          </div>
        </div>

        <div>
          <label className="text-xs text-gray-300 mb-1 block">Source</label>
          <Input
            value={formData.source}
            onChange={(e) => setFormData({...formData, source: e.target.value})}
            placeholder="OTC, Gift, Mining, etc."
            className="bg-slate-700 border-slate-600 text-white text-sm"
            data-testid="manual-source-input"
          />
        </div>

        <div>
          <label className="text-xs text-gray-300 mb-1 block">Notes (optional)</label>
          <Input
            value={formData.notes}
            onChange={(e) => setFormData({...formData, notes: e.target.value})}
            placeholder="Any additional details..."
            className="bg-slate-700 border-slate-600 text-white text-sm"
            data-testid="manual-notes-input"
          />
        </div>

        <Button 
          type="submit" 
          disabled={loading}
          className="w-full bg-green-600 hover:bg-green-700 text-white"
          data-testid="add-manual-acquisition-btn"
        >
          {loading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Adding...
            </>
          ) : (
            <>
              <Plus className="w-4 h-4 mr-2" />
              Add Acquisition
            </>
          )}
        </Button>
      </form>

      <Alert className="bg-blue-900/20 border-blue-700/50 py-2">
        <Info className="w-3 h-3 text-blue-400" />
        <AlertDescription className="text-blue-300 text-[10px]">
          <strong>Tip:</strong> Enter acquisitions dated BEFORE the disposal date to establish cost basis.
        </AlertDescription>
      </Alert>
    </div>
  );
};

export const AddDataModal = ({ isOpen, onClose, onDataAdded, onOpenExchangeApi }) => {
  const { getAuthHeader, user } = useAuth();
  const [activeTab, setActiveTab] = useState('wallet');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Wallet input state
  const [walletAddress, setWalletAddress] = useState('');
  const [detectedChain, setDetectedChain] = useState(null);
  const [asOfDate, setAsOfDate] = useState(getDefaultAsOfDate());
  
  // CSV upload state
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);
  
  // Data summary
  const [dataSummary, setDataSummary] = useState(null);
  
  useEffect(() => {
    if (isOpen) {
      fetchDataSummary();
      setError('');
      setSuccess('');
    }
  }, [isOpen]);
  
  // Get default "as of" date (end of current tax year or today)
  function getDefaultAsOfDate() {
    const today = new Date();
    const currentYear = today.getFullYear();
    // Default to end of previous year for tax purposes, or today if we're early in the year
    if (today.getMonth() < 3) { // Jan-Mar, likely doing taxes for previous year
      return `${currentYear - 1}-12-31`;
    }
    return today.toISOString().split('T')[0];
  }
  
  const fetchDataSummary = async () => {
    try {
      const response = await axios.get(`${API}/exchanges/transactions?limit=1`, {
        headers: getAuthHeader()
      });
      setDataSummary(response.data.summary);
    } catch (err) {
      console.log('Could not fetch data summary');
    }
  };
  
  // Handle wallet address input
  const handleAddressChange = (e) => {
    const addr = e.target.value;
    setWalletAddress(addr);
    const chain = detectChainFromAddress(addr);
    setDetectedChain(chain);
  };
  
  // Add wallet address
  const handleAddWallet = async () => {
    if (!walletAddress.trim()) {
      setError('Please enter a wallet address');
      return;
    }
    
    setLoading(true);
    setError('');
    setSuccess('');
    
    try {
      // For now, we'll save the wallet and fetch its data
      // The backend will pull transactions from blockchain APIs
      const chain = detectedChain || 'ethereum';
      
      const response = await axios.post(
        `${API}/wallets/add`,
        {
          address: walletAddress.trim(),
          chain: chain,
          as_of_date: asOfDate,
          sync_transactions: true
        },
        { headers: getAuthHeader() }
      );
      
      setSuccess(`Added ${chain} wallet! ${response.data.transactions_found || 0} transactions found.`);
      setWalletAddress('');
      setDetectedChain(null);
      fetchDataSummary();
      
      if (onDataAdded) onDataAdded();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to add wallet');
    } finally {
      setLoading(false);
    }
  };
  
  // Handle CSV file upload
  const handleFileSelect = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith('.csv')) {
      setError('Please upload a CSV file');
      return;
    }

    setUploading(true);
    setError('');
    setSuccess('');

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await axios.post(`${API}/exchanges/import-csv`, formData, {
        headers: {
          ...getAuthHeader(),
          'Content-Type': 'multipart/form-data'
        }
      });

      setSuccess(`Imported ${response.data.imported_count || 0} transactions from ${response.data.exchange || 'exchange'}`);
      fetchDataSummary();
      
      if (onDataAdded) onDataAdded();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to import CSV. Make sure it\'s from a supported exchange.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const isPaidUser = user?.subscription_tier !== 'free';

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="w-[95vw] max-w-2xl bg-slate-800 border-slate-700 max-h-[85vh] overflow-y-auto mx-auto" data-testid="add-data-modal">
        <DialogHeader className="pb-2">
          <DialogTitle className="text-white text-lg sm:text-xl flex items-center gap-2">
            <Plus className="w-4 h-4 sm:w-5 sm:h-5 text-purple-400" />
            Add Your Crypto Data
          </DialogTitle>
          <DialogDescription className="text-gray-400 text-sm">
            Import transactions from wallets or exchanges
          </DialogDescription>
        </DialogHeader>

        {/* Data Summary Bar */}
        {dataSummary && dataSummary.total_transactions > 0 && (
          <div className="bg-slate-700/50 rounded-lg p-2 sm:p-3 flex items-center justify-between">
            <div className="flex items-center gap-2 sm:gap-4">
              <div className="text-center">
                <p className="text-base sm:text-lg font-bold text-white">{dataSummary.total_transactions}</p>
                <p className="text-[10px] sm:text-xs text-gray-400">Transactions</p>
              </div>
              <div className="text-center">
                <p className="text-base sm:text-lg font-bold text-purple-400">{Object.keys(dataSummary.by_asset || {}).length}</p>
                <p className="text-[10px] sm:text-xs text-gray-400">Assets</p>
              </div>
              <div className="text-center">
                <p className="text-base sm:text-lg font-bold text-blue-400">{Object.keys(dataSummary.by_exchange || {}).length}</p>
                <p className="text-[10px] sm:text-xs text-gray-400">Sources</p>
              </div>
            </div>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={fetchDataSummary}
              className="text-gray-400 hover:text-white p-1 sm:p-2"
            >
              <RefreshCw className="w-3 h-3 sm:w-4 sm:h-4" />
            </Button>
          </div>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-4 bg-slate-700 h-auto">
            <TabsTrigger value="wallet" className="data-[state=active]:bg-purple-600 text-xs sm:text-sm py-2">
              <Wallet className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
              <span className="hidden sm:inline">Wallet</span>
            </TabsTrigger>
            <TabsTrigger value="csv" className="data-[state=active]:bg-purple-600 text-xs sm:text-sm py-2">
              <Upload className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
              <span className="hidden sm:inline">CSV</span>
            </TabsTrigger>
            <TabsTrigger value="api" className="data-[state=active]:bg-purple-600 text-xs sm:text-sm py-2">
              <Key className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
              <span className="hidden sm:inline">API</span>
            </TabsTrigger>
            <TabsTrigger value="manual" className="data-[state=active]:bg-purple-600 text-xs sm:text-sm py-2">
              <Plus className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
              <span className="hidden sm:inline">Manual</span>
            </TabsTrigger>
          </TabsList>

          {/* Wallet Address Tab */}
          <TabsContent value="wallet" className="space-y-3 sm:space-y-4 mt-3 sm:mt-4">
            <div className="space-y-3 sm:space-y-4">
              {/* Address Input */}
              <div>
                <label className="text-xs sm:text-sm text-gray-300 mb-1 sm:mb-2 block">
                  Wallet Address or xPub
                </label>
                <div className="relative">
                  <Input
                    value={walletAddress}
                    onChange={handleAddressChange}
                    placeholder="0x... or bc1... or xpub..."
                    className="bg-slate-700 border-slate-600 text-white text-sm pr-20 sm:pr-24"
                    data-testid="wallet-address-input"
                  />
                  {detectedChain && (
                    <Badge className="absolute right-2 top-1/2 -translate-y-1/2 bg-green-600 text-[10px] sm:text-xs px-1 sm:px-2">
                      {SUPPORTED_CHAINS.find(c => c.id === detectedChain)?.icon} {detectedChain}
                    </Badge>
                  )}
                </div>
                <p className="text-[10px] sm:text-xs text-gray-500 mt-1">
                  Auto-detects: ETH, BTC, SOL, Polygon
                </p>
              </div>
              
              {/* As Of Date */}
              <div>
                <label className="text-xs sm:text-sm text-gray-300 mb-1 sm:mb-2 flex items-center gap-1 sm:gap-2">
                  <Calendar className="w-3 h-3 sm:w-4 sm:h-4" />
                  Value As Of Date
                </label>
                <Input
                  type="date"
                  value={asOfDate}
                  onChange={(e) => setAsOfDate(e.target.value)}
                  className="bg-slate-700 border-slate-600 text-white text-sm"
                />
                <p className="text-[10px] sm:text-xs text-gray-500 mt-1">
                  For tax year calculations. Holdings are valued at this date.
                </p>
              </div>

              {/* Info Box */}
              <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-2 sm:p-3">
                <div className="flex gap-2">
                  <Info className="w-3 h-3 sm:w-4 sm:h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                  <div className="text-xs sm:text-sm text-blue-300">
                    <p className="font-medium mb-1">How "As Of Date" works:</p>
                    <ul className="text-[10px] sm:text-xs text-blue-300/80 space-y-0.5 sm:space-y-1">
                      <li>• Sold/transferred → valued at tx date</li>
                      <li>• Holdings held → valued at selected date</li>
                      <li>• Use 12/31 for tax year reporting</li>
                    </ul>
                  </div>
                </div>
              </div>

              <Button
                onClick={handleAddWallet}
                disabled={loading || !walletAddress.trim()}
                className="w-full bg-purple-600 hover:bg-purple-700 text-sm sm:text-base"
                data-testid="add-wallet-button"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-1 sm:mr-2 h-3 w-3 sm:h-4 sm:w-4 animate-spin" />
                    Syncing...
                  </>
                ) : (
                  <>
                    <Plus className="mr-1 sm:mr-2 h-3 w-3 sm:h-4 sm:w-4" />
                    Add Wallet
                  </>
                )}
              </Button>
            </div>
          </TabsContent>

          {/* CSV Import Tab */}
          <TabsContent value="csv" className="space-y-3 sm:space-y-4 mt-3 sm:mt-4">
            {/* Upload Area */}
            <Card className="bg-slate-900/50 border-slate-700 border-dashed border-2">
              <CardContent className="pt-4 sm:pt-6 pb-4">
                <div className="text-center">
                  <input
                    type="file"
                    ref={fileInputRef}
                    onChange={handleFileSelect}
                    accept=".csv"
                    className="hidden"
                    data-testid="csv-file-input"
                  />
                  <Button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    className="bg-purple-600 hover:bg-purple-700 px-4 sm:px-8 py-4 sm:py-6 text-sm sm:text-lg"
                    data-testid="upload-csv-button"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="w-4 h-4 sm:w-5 sm:h-5 animate-spin mr-1 sm:mr-2" />
                        Importing...
                      </>
                    ) : (
                      <>
                        <Upload className="w-4 h-4 sm:w-5 sm:h-5 mr-1 sm:mr-2" />
                        Upload CSV
                      </>
                    )}
                  </Button>
                  <p className="text-gray-400 text-xs sm:text-sm mt-2 sm:mt-3">
                    Auto-detects Coinbase, Kraken, Binance, etc.
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Supported Exchanges */}
            <div>
              <p className="text-xs sm:text-sm text-gray-400 mb-2 sm:mb-3">Supported formats:</p>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-1.5 sm:gap-2">
                {SUPPORTED_EXCHANGES.map(exchange => (
                  <div
                    key={exchange.id}
                    className="bg-slate-700/50 rounded-lg p-1.5 sm:p-2 flex items-center gap-1.5 sm:gap-2"
                  >
                    <div 
                      className="w-5 h-5 sm:w-6 sm:h-6 rounded-full flex items-center justify-center text-white text-[10px] sm:text-xs font-bold flex-shrink-0"
                      style={{ backgroundColor: exchange.color }}
                    >
                      {exchange.name[0]}
                    </div>
                    <span className="text-xs sm:text-sm text-gray-300 truncate">{exchange.name}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Ledger Note */}
            <Alert className="bg-orange-900/20 border-orange-700/50 py-2">
              <FileText className="w-3 h-3 sm:w-4 sm:h-4 text-orange-400" />
              <AlertDescription className="text-orange-300 text-[10px] sm:text-sm">
                <strong>Ledger:</strong> Export from Portfolio → Export operations
              </AlertDescription>
            </Alert>
          </TabsContent>

          {/* API Connection Tab */}
          <TabsContent value="api" className="space-y-3 sm:space-y-4 mt-3 sm:mt-4">
            <div className="space-y-4">
              <div className="text-center py-4">
                <Key className="w-12 h-12 text-purple-400 mx-auto mb-3" />
                <h3 className="text-lg font-semibold text-white mb-2">Connect Exchange API</h3>
                <p className="text-sm text-gray-400 mb-4">
                  Auto-sync your transactions directly from exchanges like Coinbase, Binance, and more.
                </p>
                <Button 
                  onClick={() => {
                    onClose();
                    if (onOpenExchangeApi) onOpenExchangeApi();
                  }}
                  className="bg-purple-600 hover:bg-purple-700 text-white"
                  data-testid="open-api-connection-btn"
                >
                  <Key className="w-4 h-4 mr-2" />
                  Connect Exchange API
                </Button>
              </div>
              
              <Alert className="bg-blue-900/20 border-blue-700/50 py-2">
                <Info className="w-3 h-3 sm:w-4 sm:h-4 text-blue-400" />
                <AlertDescription className="text-blue-300 text-[10px] sm:text-sm">
                  <strong>Read-only access:</strong> We only request permission to read your transaction history. Your funds are always safe.
                </AlertDescription>
              </Alert>
            </div>
          </TabsContent>

          {/* Manual Entry Tab */}
          <TabsContent value="manual" className="space-y-3 sm:space-y-4 mt-3 sm:mt-4">
            <ManualAcquisitionForm 
              getAuthHeader={getAuthHeader}
              onSuccess={(msg) => {
                setSuccess(msg);
                fetchDataSummary();
                if (onDataAdded) onDataAdded();
              }}
              onError={setError}
            />
          </TabsContent>
        </Tabs>

        {/* Messages */}
        {error && (
          <Alert className="bg-red-900/20 border-red-700 text-red-300 py-2">
            <AlertCircle className="w-3 h-3 sm:w-4 sm:h-4" />
            <AlertDescription className="text-xs sm:text-sm">{error}</AlertDescription>
          </Alert>
        )}
        
        {success && (
          <Alert className="bg-green-900/20 border-green-700 text-green-300 py-2">
            <CheckCircle className="w-3 h-3 sm:w-4 sm:h-4" />
            <AlertDescription className="text-xs sm:text-sm">{success}</AlertDescription>
          </Alert>
        )}

        {/* Quick Links */}
        <div className="border-t border-slate-700 pt-2 sm:pt-4 mt-1 sm:mt-2">
          <p className="text-[10px] sm:text-xs text-gray-500 text-center">
            All data processed securely. No API keys stored.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
