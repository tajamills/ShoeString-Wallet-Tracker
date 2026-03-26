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

export const AddDataModal = ({ isOpen, onClose, onDataAdded }) => {
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
      <DialogContent className="sm:max-w-2xl bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto" data-testid="add-data-modal">
        <DialogHeader>
          <DialogTitle className="text-white text-xl flex items-center gap-2">
            <Plus className="w-5 h-5 text-purple-400" />
            Add Your Crypto Data
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Import transactions from wallets or exchanges
          </DialogDescription>
        </DialogHeader>

        {/* Data Summary Bar */}
        {dataSummary && dataSummary.total_transactions > 0 && (
          <div className="bg-slate-700/50 rounded-lg p-3 flex items-center justify-between">
            <div className="flex items-center gap-4">
              <div className="text-center">
                <p className="text-lg font-bold text-white">{dataSummary.total_transactions}</p>
                <p className="text-xs text-gray-400">Transactions</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-purple-400">{Object.keys(dataSummary.by_asset || {}).length}</p>
                <p className="text-xs text-gray-400">Assets</p>
              </div>
              <div className="text-center">
                <p className="text-lg font-bold text-blue-400">{Object.keys(dataSummary.by_exchange || {}).length}</p>
                <p className="text-xs text-gray-400">Sources</p>
              </div>
            </div>
            <Button 
              variant="ghost" 
              size="sm" 
              onClick={fetchDataSummary}
              className="text-gray-400 hover:text-white"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        )}

        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-2 bg-slate-700">
            <TabsTrigger value="wallet" className="data-[state=active]:bg-purple-600">
              <Wallet className="w-4 h-4 mr-2" />
              Wallet Address
            </TabsTrigger>
            <TabsTrigger value="csv" className="data-[state=active]:bg-purple-600">
              <Upload className="w-4 h-4 mr-2" />
              Import CSV
            </TabsTrigger>
          </TabsList>

          {/* Wallet Address Tab */}
          <TabsContent value="wallet" className="space-y-4 mt-4">
            <div className="space-y-4">
              {/* Address Input */}
              <div>
                <label className="text-sm text-gray-300 mb-2 block">
                  Wallet Address or xPub
                </label>
                <div className="relative">
                  <Input
                    value={walletAddress}
                    onChange={handleAddressChange}
                    placeholder="0x... or bc1... or xpub..."
                    className="bg-slate-700 border-slate-600 text-white pr-24"
                    data-testid="wallet-address-input"
                  />
                  {detectedChain && (
                    <Badge className="absolute right-2 top-1/2 -translate-y-1/2 bg-green-600">
                      {SUPPORTED_CHAINS.find(c => c.id === detectedChain)?.icon} {detectedChain}
                    </Badge>
                  )}
                </div>
                <p className="text-xs text-gray-500 mt-1">
                  Auto-detects: Ethereum, Bitcoin (including xPub), Solana, Polygon
                </p>
              </div>
              
              {/* As Of Date */}
              <div>
                <label className="text-sm text-gray-300 mb-2 flex items-center gap-2">
                  <Calendar className="w-4 h-4" />
                  Value As Of Date
                </label>
                <Input
                  type="date"
                  value={asOfDate}
                  onChange={(e) => setAsOfDate(e.target.value)}
                  className="bg-slate-700 border-slate-600 text-white"
                />
                <p className="text-xs text-gray-500 mt-1">
                  For tax year calculations. Holdings are valued at this date.
                </p>
              </div>

              {/* Info Box */}
              <div className="bg-blue-900/20 border border-blue-700/50 rounded-lg p-3">
                <div className="flex gap-2">
                  <Info className="w-4 h-4 text-blue-400 flex-shrink-0 mt-0.5" />
                  <div className="text-sm text-blue-300">
                    <p className="font-medium mb-1">How "As Of Date" works:</p>
                    <ul className="text-xs text-blue-300/80 space-y-1">
                      <li>• Sold/transferred assets → valued at transaction date</li>
                      <li>• Holdings still held → valued at your selected date</li>
                      <li>• Use 12/31/YYYY for end-of-year tax reporting</li>
                    </ul>
                  </div>
                </div>
              </div>

              <Button
                onClick={handleAddWallet}
                disabled={loading || !walletAddress.trim()}
                className="w-full bg-purple-600 hover:bg-purple-700"
                data-testid="add-wallet-button"
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    Syncing Wallet...
                  </>
                ) : (
                  <>
                    <Plus className="mr-2 h-4 w-4" />
                    Add Wallet
                  </>
                )}
              </Button>
            </div>
          </TabsContent>

          {/* CSV Import Tab */}
          <TabsContent value="csv" className="space-y-4 mt-4">
            {/* Upload Area */}
            <Card className="bg-slate-900/50 border-slate-700 border-dashed border-2">
              <CardContent className="pt-6">
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
                    className="bg-purple-600 hover:bg-purple-700 px-8 py-6 text-lg"
                    data-testid="upload-csv-button"
                  >
                    {uploading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin mr-2" />
                        Importing...
                      </>
                    ) : (
                      <>
                        <Upload className="w-5 h-5 mr-2" />
                        Upload CSV File
                      </>
                    )}
                  </Button>
                  <p className="text-gray-400 text-sm mt-3">
                    We auto-detect Coinbase, Kraken, Binance, Gemini, Ledger, and more
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Supported Exchanges */}
            <div>
              <p className="text-sm text-gray-400 mb-3">Supported formats:</p>
              <div className="grid grid-cols-3 gap-2">
                {SUPPORTED_EXCHANGES.map(exchange => (
                  <div
                    key={exchange.id}
                    className="bg-slate-700/50 rounded-lg p-2 flex items-center gap-2"
                  >
                    <div 
                      className="w-6 h-6 rounded-full flex items-center justify-center text-white text-xs font-bold"
                      style={{ backgroundColor: exchange.color }}
                    >
                      {exchange.name[0]}
                    </div>
                    <span className="text-sm text-gray-300">{exchange.name}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Ledger Note */}
            <Alert className="bg-orange-900/20 border-orange-700/50">
              <FileText className="w-4 h-4 text-orange-400" />
              <AlertDescription className="text-orange-300 text-sm">
                <strong>Ledger Live users:</strong> Export your transaction history from 
                Ledger Live → Portfolio → Export operations (CSV). We'll import it automatically.
              </AlertDescription>
            </Alert>
          </TabsContent>
        </Tabs>

        {/* Messages */}
        {error && (
          <Alert className="bg-red-900/20 border-red-700 text-red-300">
            <AlertCircle className="w-4 h-4" />
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
        
        {success && (
          <Alert className="bg-green-900/20 border-green-700 text-green-300">
            <CheckCircle className="w-4 h-4" />
            <AlertDescription>{success}</AlertDescription>
          </Alert>
        )}

        {/* Quick Links */}
        <div className="border-t border-slate-700 pt-4 mt-2">
          <p className="text-xs text-gray-500 text-center">
            All data is processed securely. We never store API keys or private keys.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
