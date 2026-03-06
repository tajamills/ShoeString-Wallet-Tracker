import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Calculator,
  Wallet,
  ArrowLeftRight,
  TrendingUp,
  TrendingDown,
  FileText,
  Download,
  RefreshCw,
  Loader2,
  Info,
  ChevronDown,
  ChevronUp,
  Filter
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const UnifiedTaxDashboard = ({ 
  walletAddress, 
  chain, 
  getAuthHeader, 
  formatUSD, 
  formatNumber,
  onExportForm8949,
  onExportScheduleD
}) => {
  const [loading, setLoading] = useState(false);
  const [taxData, setTaxData] = useState(null);
  const [assetsSummary, setAssetsSummary] = useState([]);
  const [error, setError] = useState('');
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [selectedYear, setSelectedYear] = useState(null);
  const [showSources, setShowSources] = useState(false);
  const [showRealizedDetails, setShowRealizedDetails] = useState(false);

  const currentYear = new Date().getFullYear();
  const taxYears = Array.from({ length: 5 }, (_, i) => currentYear - i);

  const fetchUnifiedTaxData = async () => {
    if (!walletAddress) return;
    
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API}/tax/unified`, {
        address: walletAddress,
        chain: chain,
        include_exchanges: true,
        asset_filter: selectedAsset,
        tax_year: selectedYear
      }, { headers: getAuthHeader() });
      
      setTaxData(response.data.tax_data);
      setAssetsSummary(response.data.assets_summary || []);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to calculate unified tax data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (walletAddress) {
      fetchUnifiedTaxData();
    }
  }, [walletAddress, chain, selectedAsset, selectedYear]);

  const formatGainLoss = (value) => {
    if (value === undefined || value === null) return '$0.00';
    const formatted = formatUSD(Math.abs(value));
    if (value >= 0) {
      return <span className="text-green-400">+{formatted}</span>;
    }
    return <span className="text-red-400">-{formatted}</span>;
  };

  if (!walletAddress) {
    return null;
  }

  return (
    <div className="space-y-6" data-testid="unified-tax-dashboard">
      {/* Header with Filters */}
      <Card className="bg-gradient-to-br from-purple-900/40 to-indigo-900/30 border-purple-700">
        <CardHeader>
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <CardTitle className="text-white flex items-center gap-2">
                <Calculator className="w-6 h-6 text-purple-400" />
                Unified Tax Calculator
                <Badge className="bg-purple-600 ml-2">FIFO</Badge>
              </CardTitle>
              <CardDescription className="text-gray-400 mt-1">
                Combined on-chain wallet + exchange CSV imports
              </CardDescription>
            </div>
            
            <div className="flex items-center gap-3">
              {/* Year Filter */}
              <select
                value={selectedYear || ''}
                onChange={(e) => setSelectedYear(e.target.value ? parseInt(e.target.value) : null)}
                className="bg-slate-800 border border-slate-600 text-white rounded-md px-3 py-2 text-sm"
                data-testid="tax-year-filter"
              >
                <option value="">All Years</option>
                {taxYears.map(year => (
                  <option key={year} value={year}>{year}</option>
                ))}
              </select>
              
              {/* Asset Filter */}
              {assetsSummary.length > 1 && (
                <select
                  value={selectedAsset || ''}
                  onChange={(e) => setSelectedAsset(e.target.value || null)}
                  className="bg-slate-800 border border-slate-600 text-white rounded-md px-3 py-2 text-sm"
                  data-testid="asset-filter"
                >
                  <option value="">All Assets</option>
                  {assetsSummary.map(a => (
                    <option key={a.asset} value={a.asset}>{a.asset}</option>
                  ))}
                </select>
              )}
              
              <Button
                onClick={fetchUnifiedTaxData}
                disabled={loading}
                size="sm"
                className="bg-purple-600 hover:bg-purple-700"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>

      {error && (
        <Alert className="bg-red-900/20 border-red-700 text-red-300">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          <span className="ml-3 text-gray-400">Calculating unified tax data...</span>
        </div>
      ) : taxData ? (
        <>
          {/* Data Sources Card */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader 
              className="cursor-pointer py-3"
              onClick={() => setShowSources(!showSources)}
            >
              <div className="flex items-center justify-between">
                <CardTitle className="text-white text-lg flex items-center gap-2">
                  <ArrowLeftRight className="w-5 h-5 text-blue-400" />
                  Data Sources
                </CardTitle>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    <Badge className="bg-blue-900/50 text-blue-300">
                      <Wallet className="w-3 h-3 mr-1" />
                      {taxData.sources?.wallet_count || 0} on-chain
                    </Badge>
                    <Badge className="bg-green-900/50 text-green-300">
                      <FileText className="w-3 h-3 mr-1" />
                      {taxData.sources?.exchange_count || 0} exchange
                    </Badge>
                  </div>
                  {showSources ? <ChevronUp className="w-4 h-4 text-gray-400" /> : <ChevronDown className="w-4 h-4 text-gray-400" />}
                </div>
              </div>
            </CardHeader>
            {showSources && (
              <CardContent className="pt-0">
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div className="bg-slate-900/50 rounded p-3">
                    <div className="text-xs text-gray-400">Total Transactions</div>
                    <div className="text-xl font-bold text-white">{taxData.summary?.total_transactions || 0}</div>
                  </div>
                  <div className="bg-slate-900/50 rounded p-3">
                    <div className="text-xs text-gray-400">Buy Transactions</div>
                    <div className="text-xl font-bold text-green-400">{taxData.summary?.buy_count || 0}</div>
                  </div>
                  <div className="bg-slate-900/50 rounded p-3">
                    <div className="text-xs text-gray-400">Sell Transactions</div>
                    <div className="text-xl font-bold text-red-400">{taxData.summary?.sell_count || 0}</div>
                  </div>
                  <div className="bg-slate-900/50 rounded p-3">
                    <div className="text-xs text-gray-400">Method</div>
                    <div className="text-xl font-bold text-purple-400">{taxData.method}</div>
                  </div>
                </div>
                
                {/* Assets Summary */}
                {assetsSummary.length > 0 && (
                  <div className="mt-4">
                    <div className="text-sm text-gray-400 mb-2">Assets Tracked</div>
                    <div className="flex flex-wrap gap-2">
                      {assetsSummary.map(a => (
                        <Badge 
                          key={a.asset} 
                          className={`cursor-pointer ${selectedAsset === a.asset ? 'bg-purple-600' : 'bg-slate-700'}`}
                          onClick={() => setSelectedAsset(selectedAsset === a.asset ? null : a.asset)}
                        >
                          {a.asset}: {a.wallet_txs + a.exchange_txs} txs
                        </Badge>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            )}
          </Card>

          {/* Summary Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                  <TrendingUp className="w-4 h-4" />
                  Total Realized Gains
                </div>
                <div className="text-2xl font-bold">
                  {formatGainLoss(taxData.summary?.total_realized_gain)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  {selectedYear ? `Tax Year ${selectedYear}` : 'All time'}
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
                  {formatGainLoss(taxData.summary?.short_term_gains)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Held &lt; 1 year (ordinary income rates)
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
                  {formatGainLoss(taxData.summary?.long_term_gains)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Held ≥ 1 year (preferential rates)
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="pt-6">
                <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                  <Calculator className="w-4 h-4 text-blue-400" />
                  Unrealized Gains
                </div>
                <div className="text-2xl font-bold">
                  {formatGainLoss(taxData.summary?.total_unrealized_gain)}
                </div>
                <div className="text-xs text-gray-500 mt-1">
                  Current holdings
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Realized Gains Details */}
          {taxData.realized_gains?.length > 0 && (
            <Card className="bg-slate-800/50 border-slate-700">
              <CardHeader 
                className="cursor-pointer"
                onClick={() => setShowRealizedDetails(!showRealizedDetails)}
              >
                <div className="flex items-center justify-between">
                  <CardTitle className="text-white flex items-center gap-2">
                    <FileText className="w-5 h-5 text-green-400" />
                    Realized Gains Detail ({taxData.realized_gains.length} dispositions)
                  </CardTitle>
                  {showRealizedDetails ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </div>
              </CardHeader>
              {showRealizedDetails && (
                <CardContent>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="border-b border-slate-700">
                          <th className="text-left py-2 px-2 text-gray-400">Source</th>
                          <th className="text-left py-2 px-2 text-gray-400">Asset</th>
                          <th className="text-left py-2 px-2 text-gray-400">Buy Date</th>
                          <th className="text-left py-2 px-2 text-gray-400">Sell Date</th>
                          <th className="text-right py-2 px-2 text-gray-400">Amount</th>
                          <th className="text-right py-2 px-2 text-gray-400">Cost Basis</th>
                          <th className="text-right py-2 px-2 text-gray-400">Proceeds</th>
                          <th className="text-right py-2 px-2 text-gray-400">Gain/Loss</th>
                          <th className="text-center py-2 px-2 text-gray-400">Term</th>
                        </tr>
                      </thead>
                      <tbody>
                        {taxData.realized_gains.slice(0, 25).map((gain, idx) => (
                          <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                            <td className="py-2 px-2">
                              <Badge className={gain.sell_source?.includes('exchange') ? 'bg-green-900/50 text-green-300' : 'bg-blue-900/50 text-blue-300'}>
                                {gain.sell_source?.includes('exchange') ? gain.sell_source.split(':')[1] : 'wallet'}
                              </Badge>
                            </td>
                            <td className="py-2 px-2 text-white font-medium">{gain.asset}</td>
                            <td className="py-2 px-2 text-gray-300">{gain.buy_date}</td>
                            <td className="py-2 px-2 text-gray-300">{gain.sell_date}</td>
                            <td className="py-2 px-2 text-right text-white font-mono">
                              {formatNumber(gain.amount)}
                            </td>
                            <td className="py-2 px-2 text-right text-gray-300">
                              {formatUSD(gain.cost_basis)}
                            </td>
                            <td className="py-2 px-2 text-right text-gray-300">
                              {formatUSD(gain.proceeds)}
                            </td>
                            <td className="py-2 px-2 text-right font-semibold">
                              {formatGainLoss(gain.gain_loss)}
                            </td>
                            <td className="py-2 px-2 text-center">
                              <Badge className={gain.holding_period === 'long-term' ? 'bg-green-900/50' : 'bg-orange-900/50'}>
                                {gain.holding_period === 'long-term' ? 'Long' : 'Short'}
                              </Badge>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                    {taxData.realized_gains.length > 25 && (
                      <p className="text-center text-gray-500 text-sm mt-3">
                        Showing 25 of {taxData.realized_gains.length}. Export Form 8949 for complete list.
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
                  onClick={() => onExportForm8949?.('all')}
                  className="bg-green-600 hover:bg-green-700"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export Unified Form 8949
                </Button>
                <Button
                  onClick={onExportScheduleD}
                  variant="outline"
                  className="border-green-600 text-green-300 hover:bg-green-900/30"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  Export Schedule D
                </Button>
              </div>
              
              <Alert className="mt-4 bg-blue-900/20 border-blue-700 text-blue-300">
                <Info className="w-4 h-4" />
                <AlertDescription>
                  This unified view combines your on-chain transactions with imported exchange data.
                  FIFO cost basis is calculated across all sources chronologically.
                </AlertDescription>
              </Alert>
            </CardContent>
          </Card>
        </>
      ) : null}
    </div>
  );
};
