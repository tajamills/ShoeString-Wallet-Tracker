/**
 * ExchangeTaxCalculator - Standalone tax calculator from exchange CSV imports
 * 
 * Features:
 * - FIFO cost basis calculation
 * - Realized/unrealized capital gains
 * - Form 8949 export (CSV)
 * - Filter by tax year and asset
 * 
 * No wallet required - works purely from imported exchange data.
 * Updated: March 2026
 */
import React, { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { 
  Calculator,
  Upload,
  FileText,
  Download,
  TrendingUp,
  TrendingDown,
  Loader2,
  RefreshCw,
  Info,
  ChevronDown,
  ChevronUp,
  DollarSign,
  PieChart,
  AlertTriangle,
  Shield
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const ExchangeTaxCalculator = ({ getAuthHeader, isVisible }) => {
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [taxData, setTaxData] = useState(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [selectedYear, setSelectedYear] = useState(null);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  const [exportingCSV, setExportingCSV] = useState(false);
  const fileInputRef = useRef(null);

  const currentYear = new Date().getFullYear();
  const taxYears = Array.from({ length: 5 }, (_, i) => currentYear - i);

  useEffect(() => {
    if (isVisible) {
      calculateTax();
    }
  }, [isVisible, selectedYear, selectedAsset]);

  const calculateTax = async () => {
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API}/exchanges/tax/calculate`, {
        asset_filter: selectedAsset,
        tax_year: selectedYear
      }, { headers: getAuthHeader() });
      
      setTaxData(response.data);
    } catch (err) {
      if (err.response?.status !== 403) {
        setError(err.response?.data?.detail || 'Failed to calculate tax');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files?.[0];
    if (!file) return;

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

      setSuccess(`Imported ${response.data.transaction_count} transactions from ${response.data.exchange_detected}`);
      
      // Recalculate tax
      await calculateTax();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to import CSV');
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const exportForm8949 = async (holdingPeriod = null) => {
    setExportingCSV(true);
    try {
      const params = new URLSearchParams();
      if (selectedYear) params.append('tax_year', selectedYear);
      if (holdingPeriod) params.append('holding_period', holdingPeriod);
      
      const response = await axios.get(
        `${API}/exchanges/tax/form-8949/csv?${params.toString()}`,
        { 
          headers: getAuthHeader(),
          responseType: 'blob'
        }
      );
      
      // Download file
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `Form_8949_${selectedYear || 'All'}_${holdingPeriod || 'All'}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      
      setSuccess('Form 8949 CSV downloaded');
    } catch (err) {
      setError('Failed to export CSV');
    } finally {
      setExportingCSV(false);
    }
  };

  const formatUSD = (num) => {
    if (num === undefined || num === null) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2
    }).format(num);
  };

  const formatGain = (value) => {
    if (value >= 0) {
      return <span className="text-green-400">+{formatUSD(value)}</span>;
    }
    return <span className="text-red-400">{formatUSD(value)}</span>;
  };

  if (!isVisible) return null;

  return (
    <div className="space-y-4 sm:space-y-6" data-testid="exchange-tax-calculator">
      {/* Header */}
      <Card className="bg-gradient-to-br from-green-900/40 to-emerald-900/30 border-green-700">
        <CardHeader className="px-3 sm:px-6 py-3 sm:py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <CardTitle className="text-white text-lg sm:text-2xl flex items-center gap-2">
                <Calculator className="w-5 h-5 sm:w-7 sm:h-7 text-green-400" />
                Exchange Tax Calculator
              </CardTitle>
              <CardDescription className="text-gray-400 text-xs sm:text-sm mt-1">
                Upload CSVs → Get cost basis & gains
              </CardDescription>
            </div>
            
            <div className="flex items-center gap-2 flex-wrap">
              {/* Upload Button */}
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileUpload}
                accept=".csv"
                className="hidden"
              />
              <Button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploading}
                size="sm"
                className="bg-green-600 hover:bg-green-700 text-xs sm:text-sm"
              >
                {uploading ? (
                  <Loader2 className="w-3 h-3 sm:w-4 sm:h-4 animate-spin mr-1 sm:mr-2" />
                ) : (
                  <Upload className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
                )}
                <span className="hidden sm:inline">Upload CSV</span>
                <span className="sm:hidden">Upload</span>
              </Button>
              
              {/* Year Filter */}
              <select
                value={selectedYear || ''}
                onChange={(e) => setSelectedYear(e.target.value ? parseInt(e.target.value) : null)}
                className="bg-slate-800 border border-slate-600 text-white rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm"
              >
                <option value="">All Years</option>
                {taxYears.map(year => (
                  <option key={year} value={year}>{year}</option>
                ))}
              </select>
              
              {/* Asset Filter */}
              {taxData?.tax_data?.asset_summary?.length > 1 && (
                <select
                  value={selectedAsset || ''}
                  onChange={(e) => setSelectedAsset(e.target.value || null)}
                  className="bg-slate-800 border border-slate-600 text-white rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm max-w-[80px] sm:max-w-none"
                >
                  <option value="">All Assets</option>
                  {taxData.tax_data.asset_summary.map(a => (
                    <option key={a.asset} value={a.asset}>{a.asset}</option>
                  ))}
                </select>
              )}
              
              <Button
                onClick={calculateTax}
                disabled={loading}
                size="sm"
                variant="outline"
                className="border-slate-600"
              >
                <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* CPA DISCLAIMER - Important Legal Notice */}
      <Alert className="bg-amber-900/30 border-amber-600 text-amber-200 px-3 sm:px-4 py-2 sm:py-3">
        <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-amber-400 flex-shrink-0" />
        <AlertTitle className="text-amber-300 font-semibold text-xs sm:text-sm">Tax Disclaimer</AlertTitle>
        <AlertDescription className="text-amber-200/90 text-[10px] sm:text-sm mt-1">
          Estimates only. <strong>Verify with a CPA</strong> before filing.
          <span className="hidden sm:inline"> • FIFO method • Stablecoins excluded</span>
        </AlertDescription>
      </Alert>

      {/* Messages */}
      {error && (
        <Alert className="bg-red-900/20 border-red-700 text-red-300">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      
      {success && (
        <Alert className="bg-green-900/20 border-green-700 text-green-300">
          <AlertDescription>{success}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-green-400" />
          <span className="ml-3 text-gray-400">Calculating cost basis...</span>
        </div>
      ) : !taxData?.has_data ? (
        <Card className="bg-slate-800/50 border-slate-700 border-dashed border-2">
          <CardContent className="py-12 text-center">
            <Upload className="w-12 h-12 text-gray-500 mx-auto mb-4" />
            <h3 className="text-xl text-white mb-2">No Exchange Data Yet</h3>
            <p className="text-gray-400 mb-4">
              Upload your exchange CSV exports to calculate cost basis and capital gains
            </p>
            <Button
              onClick={() => fileInputRef.current?.click()}
              className="bg-green-600 hover:bg-green-700"
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload Your First CSV
            </Button>
            <p className="text-gray-500 text-sm mt-4">
              Supports: Coinbase, Binance, Kraken, Gemini, Crypto.com, KuCoin
            </p>
          </CardContent>
        </Card>
      ) : (
        <>
          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                  <DollarSign className="w-4 h-4 text-green-400" />
                  Total Realized Gains
                </div>
                <div className="text-2xl font-bold">
                  {formatGain(taxData.tax_data.summary?.total_realized_gain)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {taxData.tax_data.summary?.dispositions_count || 0} dispositions
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                  <TrendingDown className="w-4 h-4 text-orange-400" />
                  Short-term Gains
                </div>
                <div className="text-2xl font-bold">
                  {formatGain(taxData.tax_data.summary?.short_term_gains)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Taxed as ordinary income
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                  <TrendingUp className="w-4 h-4 text-green-400" />
                  Long-term Gains
                </div>
                <div className="text-2xl font-bold">
                  {formatGain(taxData.tax_data.summary?.long_term_gains)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Preferential tax rates
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                  <PieChart className="w-4 h-4 text-blue-400" />
                  Unrealized Gains
                </div>
                <div className="text-2xl font-bold">
                  {formatGain(taxData.tax_data.summary?.total_unrealized_gain)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {taxData.tax_data.summary?.open_positions || 0} open positions
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Cost Basis Summary */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardContent className="pt-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
                <div>
                  <div className="text-sm text-gray-400 mb-1">Total Cost Basis</div>
                  <div className="text-xl font-bold text-white">
                    {formatUSD(taxData.tax_data.summary?.total_cost_basis)}
                  </div>
                  <div className="text-xs text-gray-500">What you paid</div>
                </div>
                <div>
                  <div className="text-sm text-gray-400 mb-1">Current Value</div>
                  <div className="text-xl font-bold text-white">
                    {formatUSD(taxData.tax_data.summary?.total_current_value)}
                  </div>
                  <div className="text-xs text-gray-500">Current market value</div>
                </div>
                <div>
                  <div className="text-sm text-gray-400 mb-1">Transactions</div>
                  <div className="text-xl font-bold text-white">
                    {taxData.tax_data.total_transactions}
                  </div>
                  <div className="text-xs text-gray-500">
                    From: {taxData.tax_data.exchanges?.join(', ')}
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Asset Breakdown */}
          {taxData.tax_data.asset_summary?.length > 0 && (
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader>
                <CardTitle className="text-white text-lg">Assets</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  {taxData.tax_data.asset_summary.map(asset => (
                    <div 
                      key={asset.asset}
                      className={`bg-slate-900/50 rounded-lg p-3 cursor-pointer transition-colors ${
                        selectedAsset === asset.asset ? 'ring-2 ring-green-500' : 'hover:bg-slate-800'
                      }`}
                      onClick={() => setSelectedAsset(selectedAsset === asset.asset ? null : asset.asset)}
                    >
                      <div className="font-bold text-white">{asset.asset}</div>
                      <div className="text-xs text-gray-400 mt-1">
                        {asset.buy_count} buys, {asset.sell_count} sells
                      </div>
                      <div className="text-sm text-green-400 mt-1">
                        {asset.net_position?.toFixed(4)} held
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}

          {/* Realized Gains Detail */}
          {taxData.tax_data.realized_gains?.length > 0 && (
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader 
                className="cursor-pointer"
                onClick={() => setShowDetails(!showDetails)}
              >
                <div className="flex items-center justify-between">
                  <CardTitle className="text-white flex items-center gap-2">
                    <FileText className="w-5 h-5 text-green-400" />
                    Realized Gains ({taxData.tax_data.realized_gains.length})
                  </CardTitle>
                  {showDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </div>
              </CardHeader>
              {showDetails && (
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-700">
                          <th className="text-left py-2 px-2 text-gray-400">Asset</th>
                          <th className="text-left py-2 px-2 text-gray-400">Amount</th>
                          <th className="text-left py-2 px-2 text-gray-400">Buy Date</th>
                          <th className="text-left py-2 px-2 text-gray-400">Sell Date</th>
                          <th className="text-right py-2 px-2 text-gray-400">Cost Basis</th>
                          <th className="text-right py-2 px-2 text-gray-400">Proceeds</th>
                          <th className="text-right py-2 px-2 text-gray-400">Gain/Loss</th>
                          <th className="text-center py-2 px-2 text-gray-400">Term</th>
                        </tr>
                      </thead>
                      <tbody>
                        {taxData.tax_data.realized_gains.slice(0, 50).map((gain, idx) => (
                          <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                            <td className="py-2 px-2 text-white font-medium">{gain.asset}</td>
                            <td className="py-2 px-2 text-gray-300 font-mono">{gain.amount?.toFixed(6)}</td>
                            <td className="py-2 px-2 text-gray-300">{gain.buy_date}</td>
                            <td className="py-2 px-2 text-gray-300">{gain.sell_date}</td>
                            <td className="py-2 px-2 text-right text-gray-300">{formatUSD(gain.cost_basis)}</td>
                            <td className="py-2 px-2 text-right text-gray-300">{formatUSD(gain.proceeds)}</td>
                            <td className="py-2 px-2 text-right font-semibold">{formatGain(gain.gain_loss)}</td>
                            <td className="py-2 px-2 text-center">
                              <Badge className={gain.holding_period === 'long-term' ? 'bg-green-900/50' : 'bg-orange-900/50'}>
                                {gain.holding_period === 'long-term' ? 'Long' : 'Short'}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {taxData.tax_data.realized_gains.length > 50 && (
                      <p className="text-center text-gray-500 text-sm mt-3">
                        Showing 50 of {taxData.tax_data.realized_gains.length}. Export for complete list.
                      </p>
                    )}
                  </div>
                </CardContent>
              )}
            </Card>
          )}

          {/* Export Actions */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardContent className="pt-6">
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={() => exportForm8949()}
                  disabled={exportingCSV}
                  className="bg-green-600 hover:bg-green-700"
                >
                  {exportingCSV ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Download className="w-4 h-4 mr-2" />
                  )}
                  Export Form 8949 (All)
                </Button>
                <Button
                  onClick={() => exportForm8949('short-term')}
                  disabled={exportingCSV}
                  variant="outline"
                  className="border-orange-600 text-orange-300 hover:bg-orange-900/30"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Short-term Only
                </Button>
                <Button
                  onClick={() => exportForm8949('long-term')}
                  disabled={exportingCSV}
                  variant="outline"
                  className="border-green-600 text-green-300 hover:bg-green-900/30"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Long-term Only
                </Button>
              </div>
              
              <Alert className="mt-4 bg-blue-900/20 border-blue-700 text-blue-300">
                <Info className="w-4 h-4" />
                <AlertDescription>
                  <strong>How it works:</strong> We use FIFO (First In, First Out) to match your buys with sells 
                  across all uploaded exchanges. Upload more CSVs to get a complete picture.
                </AlertDescription>
              </Alert>

              {/* Calculation Transparency */}
              <div className="mt-4 p-4 bg-slate-900/50 rounded-lg border border-slate-700">
                <h4 className="text-sm font-semibold text-white mb-2 flex items-center gap-2">
                  <Shield className="w-4 h-4 text-purple-400" />
                  What's Included in These Calculations
                </h4>
                <ul className="text-xs text-gray-400 space-y-1">
                  <li>• <strong className="text-gray-300">Crypto purchases/sales</strong> (BTC, ETH, etc.) - tracked for cost basis</li>
                  <li>• <strong className="text-gray-300">Stablecoins EXCLUDED</strong> (USDC, USDT, BUSD, DAI) - not taxable events</li>
                  <li>• <strong className="text-gray-300">Current prices</strong> from CoinGecko API for unrealized gains</li>
                  <li>• <strong className="text-gray-300">Holding period</strong>: &gt;365 days = long-term, ≤365 days = short-term</li>
                </ul>
                <p className="text-xs text-amber-400/80 mt-3">
                  ⚠️ Always verify these figures against your exchange statements and consult a tax professional.
                </p>
              </div>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
};
