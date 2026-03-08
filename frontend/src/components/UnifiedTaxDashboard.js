import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
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
  Filter,
  Layers,
  AlertTriangle,
  Shield
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
  onExportScheduleD,
  hasExchangeData = false
}) => {
  const [loading, setLoading] = useState(false);
  const [taxData, setTaxData] = useState(null);
  const [assetsSummary, setAssetsSummary] = useState([]);
  const [error, setError] = useState('');
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [selectedYear, setSelectedYear] = useState(null);
  const [showSources, setShowSources] = useState(false);
  const [showRealizedDetails, setShowRealizedDetails] = useState(false);
  const [dataSource, setDataSource] = useState('combined');
  const [dataSourcesUsed, setDataSourcesUsed] = useState(null);
  const [detectedTransfers, setDetectedTransfers] = useState(null);

  const currentYear = new Date().getFullYear();
  const taxYears = Array.from({ length: 5 }, (_, i) => currentYear - i);

  const hasWalletData = !!walletAddress;

  const fetchUnifiedTaxData = async () => {
    // For exchange_only, we don't need a wallet address
    if (dataSource !== 'exchange_only' && !walletAddress) return;
    
    setLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API}/tax/unified`, {
        address: walletAddress || null,
        chain: chain,
        data_source: dataSource,
        asset_filter: selectedAsset,
        tax_year: selectedYear
      }, { headers: getAuthHeader() });
      
      setTaxData(response.data.tax_data);
      setAssetsSummary(response.data.assets_summary || []);
      setDataSourcesUsed(response.data.data_sources_used);
      
      // Store detected transfers info if available
      if (response.data.tax_data?.detected_transfers) {
        setDetectedTransfers(response.data.tax_data.detected_transfers);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to calculate unified tax data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Only fetch if we have the required data for the selected source
    if (dataSource === 'exchange_only' || walletAddress) {
      fetchUnifiedTaxData();
    }
  }, [walletAddress, chain, selectedAsset, selectedYear, dataSource]);

  const formatGainLoss = (value) => {
    if (value === undefined || value === null) return '$0.00';
    const formatted = formatUSD(Math.abs(value));
    if (value >= 0) {
      return <span className="text-green-400">+{formatted}</span>;
    }
    return <span className="text-red-400">-{formatted}</span>;
  };

  const dataSourceOptions = [
    { id: 'wallet_only', label: 'Wallet Only', icon: Wallet, disabled: !hasWalletData, desc: 'On-chain transactions only' },
    { id: 'exchange_only', label: 'Exchange Only', icon: ArrowLeftRight, disabled: !hasExchangeData, desc: 'Imported CSV transactions' },
    { id: 'combined', label: 'Combined', icon: Layers, disabled: false, desc: 'All sources merged' }
  ];

  return (
    <div className="space-y-6" data-testid="unified-tax-dashboard">
      {/* CPA Disclaimer */}
      <Alert className="bg-amber-900/30 border-amber-600 text-amber-200 px-3 sm:px-4 py-2 sm:py-3">
        <AlertTriangle className="w-4 h-4 sm:w-5 sm:h-5 text-amber-400 flex-shrink-0" />
        <AlertTitle className="text-amber-300 font-semibold text-xs sm:text-sm">Tax Disclaimer</AlertTitle>
        <AlertDescription className="text-amber-200/90 text-[10px] sm:text-sm mt-1">
          Estimates only. <strong>Verify with a CPA</strong> before filing.
        </AlertDescription>
      </Alert>

      {/* Data Source Selector */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader className="pb-3 px-3 sm:px-6">
          <CardTitle className="text-white text-base sm:text-lg flex items-center gap-2">
            <Layers className="w-4 h-4 sm:w-5 sm:h-5 text-purple-400" />
            Select Data Source
          </CardTitle>
          <CardDescription className="text-gray-400 text-xs sm:text-sm">
            Choose which transaction data to include
          </CardDescription>
        </CardHeader>
        <CardContent className="px-3 sm:px-6">
          <div className="grid grid-cols-3 gap-1 sm:flex sm:flex-wrap sm:gap-2">
            {dataSourceOptions.map((option) => {
              const Icon = option.icon;
              const isActive = dataSource === option.id;
              return (
                <Button
                  key={option.id}
                  onClick={() => setDataSource(option.id)}
                  disabled={option.disabled}
                  variant={isActive ? "default" : "outline"}
                  size="sm"
                  className={`
                    text-xs sm:text-sm px-2 sm:px-4 py-1 sm:py-2
                    ${isActive 
                      ? 'bg-purple-600 hover:bg-purple-700 text-white' 
                      : 'border-slate-600 text-gray-300 hover:bg-slate-700'
                    }
                    ${option.disabled ? 'opacity-50 cursor-not-allowed' : ''}
                  `}
                  data-testid={`data-source-${option.id}`}
                >
                  <Icon className="w-3 h-3 sm:w-4 sm:h-4 mr-1 sm:mr-2" />
                  <span className="hidden sm:inline">{option.label}</span>
                  <span className="sm:hidden">{option.label.split(' ')[0]}</span>
                </Button>
              );
            })}
          </div>
          
          {/* Selected source description - hidden on mobile */}
          <p className="hidden sm:block mt-3 text-sm text-gray-400">
            {dataSourceOptions.find(o => o.id === dataSource)?.desc}
          </p>
          
          {/* Calculation Method Info */}
          <div className="mt-2 sm:mt-3 p-2 sm:p-3 bg-slate-900/50 rounded border border-slate-700">
            <p className="text-[10px] sm:text-xs text-gray-400 flex items-center gap-1 flex-wrap">
              <Shield className="w-3 h-3 text-purple-400 flex-shrink-0" />
              <strong className="text-gray-300">FIFO</strong> 
              <span className="hidden sm:inline">• Stablecoins excluded</span>
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Header with Filters */}
      <Card className="bg-gradient-to-br from-purple-900/40 to-indigo-900/30 border-purple-700">
        <CardHeader className="px-3 sm:px-6 py-3 sm:py-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div className="min-w-0">
              <CardTitle className="text-white text-sm sm:text-base flex items-center gap-1 sm:gap-2 flex-wrap">
                <Calculator className="w-4 h-4 sm:w-6 sm:h-6 text-purple-400 flex-shrink-0" />
                <span>Tax Calculator</span>
                <Badge className="bg-purple-600 text-[10px] sm:text-xs">FIFO</Badge>
                <Badge className={`text-[10px] sm:text-xs ${
                  dataSource === 'combined' ? 'bg-green-600' : 
                  dataSource === 'wallet_only' ? 'bg-blue-600' : 'bg-orange-600'
                }`}>
                  {dataSource === 'combined' ? 'Combined' : 
                   dataSource === 'wallet_only' ? 'Wallet' : 'Exchange'}
                </Badge>
              </CardTitle>
              <CardDescription className="text-gray-400 text-xs sm:text-sm mt-1 truncate">
                {dataSource === 'combined' && 'Wallet + Exchange combined'}
                {dataSource === 'wallet_only' && 'On-chain only'}
                {dataSource === 'exchange_only' && 'Exchange CSV only'}
              </CardDescription>
            </div>
            
            <div className="flex items-center gap-2 flex-wrap">
              {/* Year Filter */}
              <select
                value={selectedYear || ''}
                onChange={(e) => setSelectedYear(e.target.value ? parseInt(e.target.value) : null)}
                className="bg-slate-800 border border-slate-600 text-white rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm"
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
                  className="bg-slate-800 border border-slate-600 text-white rounded-md px-2 sm:px-3 py-1.5 sm:py-2 text-xs sm:text-sm max-w-[100px] sm:max-w-none"
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
                className="bg-purple-600 hover:bg-purple-700 px-2 sm:px-3"
              >
                {loading ? (
                  <Loader2 className="w-3 h-3 sm:w-4 sm:h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-3 h-3 sm:w-4 sm:h-4" />
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
                  Data Sources Used
                </CardTitle>
                <div className="flex items-center gap-4">
                  <div className="flex items-center gap-2">
                    {dataSourcesUsed?.wallet && (
                      <Badge className="bg-blue-900/50 text-blue-300">
                        <Wallet className="w-3 h-3 mr-1" />
                        {dataSourcesUsed.wallet_tx_count || 0} on-chain
                      </Badge>
                    )}
                    {dataSourcesUsed?.exchange && (
                      <Badge className="bg-green-900/50 text-green-300">
                        <FileText className="w-3 h-3 mr-1" />
                        {dataSourcesUsed.exchange_tx_count || 0} exchange
                      </Badge>
                    )}
                    {!dataSourcesUsed?.wallet && !dataSourcesUsed?.exchange && (
                      <Badge className="bg-gray-700 text-gray-300">No data</Badge>
                    )}
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

          {/* Detected Transfers Notification */}
          {detectedTransfers && detectedTransfers.count > 0 && dataSource === 'combined' && (
            <Alert className="bg-blue-900/30 border-blue-600 text-blue-200">
              <Info className="w-4 h-4 text-blue-400" />
              <AlertDescription className="text-sm">
                <strong className="text-blue-300">Auto-detected {detectedTransfers.count} transfer(s)</strong> from your wallet to exchange.
                {detectedTransfers.assets?.length > 0 && (
                  <span> Assets: {detectedTransfers.assets.join(', ')}</span>
                )}
                <p className="text-xs text-blue-400/80 mt-1">
                  We matched wallet sends with exchange receives by amount and timestamp. 
                  The original wallet acquisition date is used for holding period calculations.
                </p>
              </AlertDescription>
            </Alert>
          )}

          {/* Summary Cards */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 sm:gap-4">
            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-3 sm:pt-6 sm:px-6">
                <div className="flex items-center gap-1 sm:gap-2 text-[10px] sm:text-sm text-gray-400 mb-1 sm:mb-2">
                  <TrendingUp className="w-3 h-3 sm:w-4 sm:h-4" />
                  <span className="truncate">Realized Gains</span>
                </div>
                <div className="text-lg sm:text-2xl font-bold">
                  {formatGainLoss(taxData.summary?.total_realized_gain)}
                </div>
                <div className="text-[9px] sm:text-xs text-gray-500 mt-0.5 sm:mt-1">
                  {selectedYear ? `${selectedYear}` : 'All time'}
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-3 sm:pt-6 sm:px-6">
                <div className="flex items-center gap-1 sm:gap-2 text-[10px] sm:text-sm text-gray-400 mb-1 sm:mb-2">
                  <TrendingDown className="w-3 h-3 sm:w-4 sm:h-4 text-orange-400" />
                  <span className="truncate">Short-term</span>
                </div>
                <div className="text-lg sm:text-2xl font-bold">
                  {formatGainLoss(taxData.summary?.short_term_gains)}
                </div>
                <div className="text-[9px] sm:text-xs text-gray-500 mt-0.5 sm:mt-1">
                  &lt;1 year
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-3 sm:pt-6 sm:px-6">
                <div className="flex items-center gap-1 sm:gap-2 text-[10px] sm:text-sm text-gray-400 mb-1 sm:mb-2">
                  <TrendingUp className="w-3 h-3 sm:w-4 sm:h-4 text-green-400" />
                  <span className="truncate">Long-term</span>
                </div>
                <div className="text-lg sm:text-2xl font-bold">
                  {formatGainLoss(taxData.summary?.long_term_gains)}
                </div>
                <div className="text-[9px] sm:text-xs text-gray-500 mt-0.5 sm:mt-1">
                  ≥1 year
                </div>
              </CardContent>
            </Card>

            <Card className="bg-slate-800/50 border-slate-700">
              <CardContent className="p-3 sm:pt-6 sm:px-6">
                <div className="flex items-center gap-1 sm:gap-2 text-[10px] sm:text-sm text-gray-400 mb-1 sm:mb-2">
                  <Calculator className="w-3 h-3 sm:w-4 sm:h-4 text-blue-400" />
                  <span className="truncate">Unrealized</span>
                </div>
                <div className="text-lg sm:text-2xl font-bold">
                  {formatGainLoss(taxData.summary?.total_unrealized_gain)}
                </div>
                <div className="text-[9px] sm:text-xs text-gray-500 mt-0.5 sm:mt-1">
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
