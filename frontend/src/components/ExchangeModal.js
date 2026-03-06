import React, { useState, useEffect, useRef } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  Loader2, 
  Upload, 
  FileText, 
  Trash2, 
  Check,
  AlertCircle,
  ArrowUpRight,
  ArrowDownLeft,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  Calculator
} from 'lucide-react';
import axios from 'axios';
import { ExchangeTaxCalculator } from './ExchangeTaxCalculator';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Exchange logos
const ExchangeLogos = {
  coinbase: (
    <svg viewBox="0 0 1024 1024" className="w-8 h-8">
      <circle cx="512" cy="512" r="512" fill="#0052FF"/>
      <path d="M512 256c-141.4 0-256 114.6-256 256s114.6 256 256 256 256-114.6 256-256-114.6-256-256-256zm-62 334h124c8.8 0 16-7.2 16-16v-124c0-8.8-7.2-16-16-16H450c-8.8 0-16 7.2-16 16v124c0 8.8 7.2 16 16 16z" fill="white"/>
    </svg>
  ),
  binance: (
    <svg viewBox="0 0 126.61 126.61" className="w-8 h-8">
      <g fill="#F3BA2F">
        <polygon points="38.73 53.98 63.3 29.4 87.89 53.99 102.22 39.66 63.3 0.73 24.39 39.64 38.73 53.98"/>
        <polygon points="0.73 63.3 15.06 48.97 29.39 63.3 15.06 77.63 0.73 63.3"/>
        <polygon points="38.73 72.63 63.3 97.21 87.88 72.62 102.22 86.93 63.3 125.88 24.4 86.97 24.38 86.95 38.73 72.63"/>
        <polygon points="97.22 63.31 111.55 48.98 125.88 63.31 111.55 77.64 97.22 63.31"/>
        <polygon points="77.83 63.3 63.3 48.77 52.42 59.64 51.09 60.98 48.78 63.29 63.3 77.82 77.83 63.3"/>
      </g>
    </svg>
  ),
  kraken: (
    <div className="w-8 h-8 bg-[#5741D9] rounded-full flex items-center justify-center text-white font-bold text-sm">K</div>
  ),
  gemini: (
    <div className="w-8 h-8 bg-[#00DCFA] rounded-full flex items-center justify-center text-black font-bold text-sm">G</div>
  ),
  crypto_com: (
    <div className="w-8 h-8 bg-[#103F68] rounded-full flex items-center justify-center text-white font-bold text-xs">CDC</div>
  ),
  kucoin: (
    <div className="w-8 h-8 bg-[#24AE8F] rounded-full flex items-center justify-center text-white font-bold text-sm">KC</div>
  )
};

export const ExchangeModal = ({ isOpen, onClose, getAuthHeader }) => {
  const [activeTab, setActiveTab] = useState('import'); // 'import' or 'tax'
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [supportedExchanges, setSupportedExchanges] = useState([]);
  const [transactions, setTransactions] = useState([]);
  const [transactionSummary, setTransactionSummary] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showInstructions, setShowInstructions] = useState(null);
  const [instructions, setInstructions] = useState(null);
  const fileInputRef = useRef(null);

  useEffect(() => {
    if (isOpen) {
      fetchData();
    }
  }, [isOpen]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [supportedRes, transactionsRes] = await Promise.all([
        axios.get(`${API}/exchanges/supported`),
        axios.get(`${API}/exchanges/transactions`, { headers: getAuthHeader() }).catch(() => ({ data: { transactions: [], summary: null } }))
      ]);
      
      setSupportedExchanges(supportedRes.data.exchanges);
      setTransactions(transactionsRes.data.transactions || []);
      setTransactionSummary(transactionsRes.data.summary);
    } catch (err) {
      // Don't show error for 403 (free users) - just show empty state
      if (err.response?.status !== 403) {
        console.error('Exchange data load error:', err);
        // Only show error if it's not a permission issue
        if (err.response?.status !== 401) {
          setError('Failed to load exchange data. Please try again.');
        }
      }
    } finally {
      setLoading(false);
    }
  };

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

      setSuccess(`${response.data.message}`);
      await fetchData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to import CSV');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleDeleteTransactions = async (exchange = null) => {
    const confirmMsg = exchange 
      ? `Delete all ${exchange} transactions?` 
      : 'Delete ALL imported transactions?';
    
    if (!window.confirm(confirmMsg)) return;

    try {
      const url = exchange 
        ? `${API}/exchanges/transactions?exchange=${exchange}`
        : `${API}/exchanges/transactions`;
      
      await axios.delete(url, { headers: getAuthHeader() });
      setSuccess('Transactions deleted');
      await fetchData();
    } catch (err) {
      setError('Failed to delete transactions');
    }
  };

  const fetchInstructions = async (exchangeId) => {
    if (showInstructions === exchangeId) {
      setShowInstructions(null);
      return;
    }
    
    try {
      const response = await axios.get(`${API}/exchanges/export-instructions/${exchangeId}`);
      setInstructions(response.data);
      setShowInstructions(exchangeId);
    } catch (err) {
      setError('Failed to load instructions');
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

  const getExchangeLogo = (id) => ExchangeLogos[id] || <FileText className="w-8 h-8 text-gray-400" />;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-4xl bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto" data-testid="exchange-modal">
        <DialogHeader>
          <DialogTitle className="text-white text-2xl flex items-center gap-2">
            {activeTab === 'import' ? (
              <>
                <Upload className="w-6 h-6 text-purple-400" />
                Exchange Data
              </>
            ) : (
              <>
                <Calculator className="w-6 h-6 text-green-400" />
                Tax Calculator
              </>
            )}
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            {activeTab === 'import' 
              ? 'Upload CSV exports from your exchanges - no API keys needed!'
              : 'Calculate cost basis and capital gains from your imported data'
            }
          </DialogDescription>
        </DialogHeader>

        {/* Tab Navigation */}
        <div className="flex border-b border-slate-700 mb-4">
          <button
            onClick={() => setActiveTab('import')}
            className={`px-4 py-2 font-medium transition-colors ${
              activeTab === 'import'
                ? 'text-purple-400 border-b-2 border-purple-400'
                : 'text-gray-400 hover:text-white'
            }`}
            data-testid="tab-import"
          >
            <Upload className="w-4 h-4 inline mr-2" />
            Import CSVs
          </button>
          <button
            onClick={() => setActiveTab('tax')}
            className={`px-4 py-2 font-medium transition-colors ${
              activeTab === 'tax'
                ? 'text-green-400 border-b-2 border-green-400'
                : 'text-gray-400 hover:text-white'
            }`}
            data-testid="tab-tax"
          >
            <Calculator className="w-4 h-4 inline mr-2" />
            Tax Calculator
          </button>
        </div>

        {/* Tax Calculator Tab */}
        {activeTab === 'tax' && (
          <ExchangeTaxCalculator 
            getAuthHeader={getAuthHeader} 
            isVisible={activeTab === 'tax'}
          />
        )}

        {/* Import Tab */}
        {activeTab === 'import' && (loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          </div>
        ) : (
          <div className="space-y-6">
            {/* Messages */}
            {error && (
              <Alert className="bg-red-900/20 border-red-700 text-red-300">
                <AlertCircle className="w-4 h-4" />
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}
            
            {success && (
              <Alert className="bg-green-900/20 border-green-700 text-green-300">
                <Check className="w-4 h-4" />
                <AlertDescription>{success}</AlertDescription>
              </Alert>
            )}

            {/* Upload Section */}
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
                    We auto-detect the exchange from your CSV columns
                  </p>
                </div>
              </CardContent>
            </Card>

            {/* Supported Exchanges */}
            <div>
              <h3 className="text-white font-semibold mb-3">Supported Exchanges</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                {supportedExchanges.map((exchange) => (
                  <Card 
                    key={exchange.id} 
                    className="bg-slate-900/30 border-slate-700 hover:border-purple-600/50 transition-colors cursor-pointer"
                    onClick={() => fetchInstructions(exchange.id)}
                  >
                    <CardContent className="p-4">
                      <div className="flex items-center gap-3">
                        {getExchangeLogo(exchange.id)}
                        <div className="flex-1">
                          <div className="text-white font-medium">{exchange.name}</div>
                          <div className="text-xs text-gray-500 flex items-center gap-1">
                            <HelpCircle className="w-3 h-3" />
                            How to export
                            {showInstructions === exchange.id ? (
                              <ChevronUp className="w-3 h-3" />
                            ) : (
                              <ChevronDown className="w-3 h-3" />
                            )}
                          </div>
                        </div>
                      </div>
                      
                      {/* Expanded Instructions */}
                      {showInstructions === exchange.id && instructions && (
                        <div className="mt-3 pt-3 border-t border-slate-700">
                          <ol className="text-xs text-gray-400 space-y-1">
                            {instructions.steps.map((step, i) => (
                              <li key={i}>{step}</li>
                            ))}
                          </ol>
                          {instructions.notes && (
                            <p className="text-xs text-yellow-400/70 mt-2 italic">
                              Note: {instructions.notes}
                            </p>
                          )}
                        </div>
                      )}
                    </CardContent>
                  </Card>
                ))}
              </div>
            </div>

            {/* Transaction Summary */}
            {transactionSummary && transactionSummary.total_transactions > 0 && (
              <Card className="bg-slate-900/50 border-slate-700">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-white">Imported Transactions</CardTitle>
                    <Button
                      onClick={() => handleDeleteTransactions()}
                      size="sm"
                      variant="outline"
                      className="border-red-700 text-red-400 hover:bg-red-900/30"
                      data-testid="delete-all-transactions"
                    >
                      <Trash2 className="w-4 h-4 mr-1" />
                      Clear All
                    </Button>
                  </div>
                </CardHeader>
                <CardContent>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
                    <div className="text-center">
                      <div className="text-2xl font-bold text-white">
                        {transactionSummary.total_transactions}
                      </div>
                      <div className="text-sm text-gray-400">Total</div>
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
                      <div className="text-2xl font-bold text-blue-400">
                        {Object.keys(transactionSummary.by_exchange || {}).length}
                      </div>
                      <div className="text-sm text-gray-400">Exchanges</div>
                    </div>
                  </div>
                  
                  {/* Exchange breakdown */}
                  {Object.keys(transactionSummary.by_exchange || {}).length > 0 && (
                    <div className="flex flex-wrap gap-2 mb-4">
                      {Object.entries(transactionSummary.by_exchange).map(([exc, count]) => (
                        <Badge key={exc} className="bg-slate-700 text-gray-300">
                          {exc}: {count}
                        </Badge>
                      ))}
                    </div>
                  )}
                  
                  {/* Asset breakdown */}
                  {Object.keys(transactionSummary.by_asset || {}).length > 0 && (
                    <div className="flex flex-wrap gap-2">
                      {Object.entries(transactionSummary.by_asset).slice(0, 10).map(([asset, count]) => (
                        <Badge key={asset} variant="outline" className="text-purple-300 border-purple-700">
                          {asset}: {count}
                        </Badge>
                      ))}
                      {Object.keys(transactionSummary.by_asset).length > 10 && (
                        <Badge variant="outline" className="text-gray-400 border-gray-600">
                          +{Object.keys(transactionSummary.by_asset).length - 10} more
                        </Badge>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            )}

            {/* Recent Transactions */}
            {transactions.length > 0 && (
              <Card className="bg-slate-900/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="text-white text-lg">Recent Imports</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    {transactions.slice(0, 10).map((tx, idx) => (
                      <div 
                        key={idx}
                        className="flex items-center justify-between py-2 border-b border-slate-700 last:border-0"
                      >
                        <div className="flex items-center gap-3">
                          {tx.tx_type === 'buy' || tx.tx_type === 'receive' || tx.tx_type === 'deposit' ? (
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

            {/* Info */}
            <Alert className="bg-blue-900/20 border-blue-700 text-blue-300">
              <AlertCircle className="w-4 h-4" />
              <AlertDescription>
                <strong>Privacy first:</strong> Your data stays with you. We never store API keys - 
                just upload your CSV exports and we parse them locally.
              </AlertDescription>
            </Alert>
          </div>
        ))}
      </DialogContent>
    </Dialog>
  );
};
