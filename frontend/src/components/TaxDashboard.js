import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { 
  TrendingUp, 
  TrendingDown, 
  DollarSign, 
  Calculator,
  FileText,
  Download,
  Info,
  ChevronDown,
  ChevronUp,
  Clock,
  Calendar,
  Wand2,
  Wallet,
  ArrowRightLeft,
  Layers,
  AlertTriangle,
  Shield
} from 'lucide-react';

export const TaxDashboard = ({ 
  taxData, 
  symbol, 
  formatUSD, 
  formatNumber, 
  onExportForm8949,
  onExportScheduleD,
  onBatchCategorize,
  dataSource = "wallet_only",
  onDataSourceChange,
  dataSourcesUsed,
  hasWalletData = false,
  hasExchangeData = false
}) => {
  const [showRealizedDetails, setShowRealizedDetails] = useState(false);
  const [showUnrealizedDetails, setShowUnrealizedDetails] = useState(false);
  const [showTaxLots, setShowTaxLots] = useState(false);

  if (!taxData || !taxData.summary) {
    return null;
  }

  const { summary, realized_gains, unrealized_gains, remaining_lots, method } = taxData;

  const formatGainLoss = (value) => {
    const formatted = formatUSD(Math.abs(value));
    if (value >= 0) {
      return <span className="text-[#00C805]">+{formatted}</span>;
    }
    return <span className="text-[#FF3B30]">-{formatted}</span>;
  };

  const dataSourceOptions = [
    { id: 'wallet_only', label: 'Wallet Only', icon: Wallet, disabled: !hasWalletData },
    { id: 'exchange_only', label: 'Exchange Only', icon: ArrowRightLeft, disabled: !hasExchangeData },
    { id: 'combined', label: 'Combined', icon: Layers, disabled: !hasWalletData && !hasExchangeData }
  ];

  return (
    <div className="space-y-6">
      {/* CPA Disclaimer */}
      <Alert className="bg-amber-900/30 border-amber-600 text-amber-200">
        <AlertTriangle className="w-5 h-5 text-[#FFB800]" />
        <AlertTitle className="text-[#FFB800] font-semibold">Important Tax Disclaimer</AlertTitle>
        <AlertDescription className="text-amber-200/90 mt-1">
          <p>
            <strong>This tool provides estimates for informational purposes only.</strong> Tax calculations 
            should be <strong>verified by a qualified CPA or tax professional</strong> before filing.
          </p>
        </AlertDescription>
      </Alert>

      {/* Data Source Selector */}
      {onDataSourceChange && (
        <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]">
          <CardHeader className="pb-3">
            <CardTitle className="text-white text-lg flex items-center gap-2">
              <Layers className="w-5 h-5 text-[#00C805]" />
              Data Source
            </CardTitle>
            <CardDescription className="text-[#8A8A93]">
              Choose which transaction data to include in tax calculations
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {dataSourceOptions.map((option) => {
                const Icon = option.icon;
                const isActive = dataSource === option.id;
                return (
                  <Button
                    key={option.id}
                    onClick={() => onDataSourceChange(option.id)}
                    disabled={option.disabled}
                    variant={isActive ? "default" : "outline"}
                    className={`
                      ${isActive 
                        ? 'bg-white text-black hover:bg-gray-200 text-white' 
                        : 'border-[#1F1F22] text-white hover:bg-[#161618]'
                      }
                      ${option.disabled ? 'opacity-50 cursor-not-allowed' : ''}
                    `}
                    data-testid={`data-source-${option.id}`}
                  >
                    <Icon className="w-4 h-4 mr-2" />
                    {option.label}
                  </Button>
                );
              })}
            </div>
            
            {/* Data Source Info */}
            {dataSourcesUsed && (
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                {dataSourcesUsed.wallet && (
                  <Badge className="bg-blue-900/50 text-blue-300">
                    <Wallet className="w-3 h-3 mr-1" />
                    {dataSourcesUsed.wallet_tx_count || 0} wallet txns
                  </Badge>
                )}
                {dataSourcesUsed.exchange && (
                  <Badge className="bg-green-900/50 text-[#00C805]">
                    <ArrowRightLeft className="w-3 h-3 mr-1" />
                    {dataSourcesUsed.exchange_tx_count || 0} exchange txns
                  </Badge>
                )}
              </div>
            )}

            {/* Calculation Info */}
            <div className="mt-3 p-3 bg-[#050505]/50 rounded border border-[#1F1F22]">
              <p className="text-xs text-[#8A8A93] flex items-center gap-1">
                <Shield className="w-3 h-3 text-[#00C805]" />
                <strong className="text-white">FIFO Method</strong> • Stablecoins excluded • 
                {dataSource === 'combined' && ' Transactions merged chronologically'}
                {dataSource === 'wallet_only' && ' On-chain transactions only'}
                {dataSource === 'exchange_only' && ' Exchange CSV transactions only'}
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Tax Summary Header */}
      <Card className="bg-gradient-to-br from-[#0C0C0E] to-[#0C0C0E] border-[#1F1F22]">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Calculator className="w-6 h-6 text-indigo-400" />
            Tax Summary
            <Badge className="bg-indigo-600 ml-2">{method}</Badge>
          </CardTitle>
          <CardDescription className="text-[#8A8A93]">
            Cost basis and capital gains calculated using {method} method
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Realized Gains */}
            <div className="bg-[#050505]/50 rounded-lg p-4 border border-[#1F1F22]">
              <div className="flex items-center gap-2 text-sm text-[#8A8A93] mb-2">
                <DollarSign className="w-4 h-4" />
                Total Realized Gains
              </div>
              <div className="text-2xl font-bold">
                {formatGainLoss(summary.total_realized_gain)}
              </div>
              <div className="text-xs text-[#4A4A52] mt-1">
                From {summary.sell_count} sell transactions
              </div>
            </div>

            {/* Short-term vs Long-term */}
            <div className="bg-[#050505]/50 rounded-lg p-4 border border-[#1F1F22]">
              <div className="flex items-center gap-2 text-sm text-[#8A8A93] mb-2">
                <Clock className="w-4 h-4" />
                Gains by Holding Period
              </div>
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-xs text-[#8A8A93]">Short-term (&lt;1yr):</span>
                  <span className="text-sm font-semibold">
                    {formatGainLoss(summary.short_term_gains)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-[#8A8A93]">Long-term (≥1yr):</span>
                  <span className="text-sm font-semibold">
                    {formatGainLoss(summary.long_term_gains)}
                  </span>
                </div>
              </div>
            </div>

            {/* Unrealized Gains */}
            <div className="bg-[#050505]/50 rounded-lg p-4 border border-[#1F1F22]">
              <div className="flex items-center gap-2 text-sm text-[#8A8A93] mb-2">
                <TrendingUp className="w-4 h-4" />
                Unrealized Gains
              </div>
              <div className="text-2xl font-bold">
                {formatGainLoss(summary.total_unrealized_gain)}
              </div>
              <div className="text-xs text-[#4A4A52] mt-1">
                Current holdings value change
              </div>
            </div>

            {/* Total Cost Basis */}
            <div className="bg-[#050505]/50 rounded-lg p-4 border border-[#1F1F22]">
              <div className="flex items-center gap-2 text-sm text-[#8A8A93] mb-2">
                <FileText className="w-4 h-4" />
                Total Cost Basis
              </div>
              <div className="text-2xl font-bold text-white">
                {formatUSD(unrealized_gains?.total_cost_basis || 0)}
              </div>
              <div className="text-xs text-[#4A4A52] mt-1">
                Of remaining holdings
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Export Tax Forms */}
      <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-[#00C805]" />
            Export Tax Report
          </CardTitle>
          <CardDescription className="text-[#8A8A93]">
            Download IRS Form 8949 compatible CSV
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            {/* Form 8949 - Primary Export */}
            <div>
              <h4 className="text-sm font-medium text-white mb-2">Form 8949 (Sales & Dispositions)</h4>
              <div className="flex flex-wrap gap-3">
                <Button
                  onClick={() => onExportForm8949('all')}
                  className="bg-[#00C805] hover:bg-[#00C805]/80"
                  data-testid="export-form-8949-btn"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export Form 8949 CSV
                </Button>
                <Button
                  onClick={() => onExportForm8949('short-term')}
                  variant="outline"
                  className="border-[#1F1F22] text-white"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Short-term Only
                </Button>
                <Button
                  onClick={() => onExportForm8949('long-term')}
                  variant="outline"
                  className="border-[#1F1F22] text-white"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Long-term Only
                </Button>
              </div>
            </div>
          </div>

          <Alert className="mt-4 bg-blue-900/20 border-blue-700 text-blue-300">
            <Info className="h-4 w-4" />
            <AlertDescription className="text-sm">
              Form 8949 reports individual capital gains and losses from crypto sales.
              Consult a tax professional for advice specific to your situation.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* Realized Gains Details */}
      {realized_gains && realized_gains.length > 0 && (
        <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]">
          <CardHeader 
            className="cursor-pointer"
            onClick={() => setShowRealizedDetails(!showRealizedDetails)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-[#FF3B30]" />
                Realized Gains/Losses ({realized_gains.length} dispositions)
              </CardTitle>
              {showRealizedDetails ? (
                <ChevronUp className="w-5 h-5 text-[#8A8A93]" />
              ) : (
                <ChevronDown className="w-5 h-5 text-[#8A8A93]" />
              )}
            </div>
          </CardHeader>
          {showRealizedDetails && (
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#1F1F22]">
                      <th className="text-left py-2 px-3 text-[#8A8A93]">Buy Date</th>
                      <th className="text-left py-2 px-3 text-[#8A8A93]">Sell Date</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Amount</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Cost Basis</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Proceeds</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Gain/Loss</th>
                      <th className="text-center py-2 px-3 text-[#8A8A93]">Term</th>
                    </tr>
                  </thead>
                  <tbody>
                    {realized_gains.slice(0, 20).map((gain, idx) => (
                      <tr key={idx} className="border-b border-[#1F1F22]/50 hover:bg-[#161618]/30">
                        <td className="py-2 px-3 text-white">{gain.buy_date}</td>
                        <td className="py-2 px-3 text-white">{gain.sell_date}</td>
                        <td className="py-2 px-3 text-right text-white font-mono">
                          {formatNumber(gain.amount)} {symbol}
                        </td>
                        <td className="py-2 px-3 text-right text-white">
                          {formatUSD(gain.cost_basis)}
                        </td>
                        <td className="py-2 px-3 text-right text-white">
                          {formatUSD(gain.proceeds)}
                        </td>
                        <td className="py-2 px-3 text-right font-semibold">
                          {formatGainLoss(gain.gain_loss)}
                        </td>
                        <td className="py-2 px-3 text-center">
                          <Badge className={gain.holding_period === 'long-term' ? 'bg-green-900/50 text-[#00C805]' : 'bg-orange-900/50 text-orange-300'}>
                            {gain.holding_period === 'long-term' ? 'Long' : 'Short'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {realized_gains.length > 20 && (
                  <p className="text-center text-[#4A4A52] text-sm mt-3">
                    Showing 20 of {realized_gains.length} dispositions. Export Form 8949 for complete list.
                  </p>
                )}
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Unrealized Gains Details */}
      {unrealized_gains && unrealized_gains.lots && unrealized_gains.lots.length > 0 && (
        <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]">
          <CardHeader 
            className="cursor-pointer"
            onClick={() => setShowUnrealizedDetails(!showUnrealizedDetails)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-[#00C805]" />
                Unrealized Gains ({unrealized_gains.lots.length} open positions)
              </CardTitle>
              {showUnrealizedDetails ? (
                <ChevronUp className="w-5 h-5 text-[#8A8A93]" />
              ) : (
                <ChevronDown className="w-5 h-5 text-[#8A8A93]" />
              )}
            </div>
          </CardHeader>
          {showUnrealizedDetails && (
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#1F1F22]">
                      <th className="text-left py-2 px-3 text-[#8A8A93]">Acquisition Date</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Amount</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Buy Price</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Current Price</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Cost Basis</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Current Value</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Unrealized Gain</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">% Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unrealized_gains.lots.slice(0, 15).map((lot, idx) => (
                      <tr key={idx} className="border-b border-[#1F1F22]/50 hover:bg-[#161618]/30">
                        <td className="py-2 px-3 text-white">{lot.buy_date}</td>
                        <td className="py-2 px-3 text-right text-white font-mono">
                          {formatNumber(lot.amount)} {symbol}
                        </td>
                        <td className="py-2 px-3 text-right text-white">
                          {formatUSD(lot.buy_price)}
                        </td>
                        <td className="py-2 px-3 text-right text-white">
                          {formatUSD(lot.current_price)}
                        </td>
                        <td className="py-2 px-3 text-right text-white">
                          {formatUSD(lot.cost_basis)}
                        </td>
                        <td className="py-2 px-3 text-right text-white">
                          {formatUSD(lot.current_value)}
                        </td>
                        <td className="py-2 px-3 text-right font-semibold">
                          {formatGainLoss(lot.unrealized_gain)}
                        </td>
                        <td className="py-2 px-3 text-right">
                          <span className={(lot.gain_percentage || 0) >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'}>
                            {(lot.gain_percentage || 0) >= 0 ? '+' : ''}{(lot.gain_percentage || 0).toFixed(2)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {unrealized_gains.lots.length > 15 && (
                  <p className="text-center text-[#4A4A52] text-sm mt-3">
                    Showing 15 of {unrealized_gains.lots.length} open positions.
                  </p>
                )}
              </div>

              {/* Unrealized Summary */}
              <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-[#050505]/50 rounded p-3">
                  <div className="text-xs text-[#8A8A93]">Total Cost Basis</div>
                  <div className="text-lg font-bold text-white">{formatUSD(unrealized_gains.total_cost_basis)}</div>
                </div>
                <div className="bg-[#050505]/50 rounded p-3">
                  <div className="text-xs text-[#8A8A93]">Current Value</div>
                  <div className="text-lg font-bold text-white">{formatUSD(unrealized_gains.total_current_value)}</div>
                </div>
                <div className="bg-[#050505]/50 rounded p-3">
                  <div className="text-xs text-[#8A8A93]">Total Unrealized</div>
                  <div className="text-lg font-bold">{formatGainLoss(unrealized_gains.total_gain)}</div>
                </div>
                <div className="bg-[#050505]/50 rounded p-3">
                  <div className="text-xs text-[#8A8A93]">Overall % Change</div>
                  <div className={`text-lg font-bold ${unrealized_gains.total_gain_percentage >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'}`}>
                    {unrealized_gains.total_gain_percentage >= 0 ? '+' : ''}{unrealized_gains.total_gain_percentage.toFixed(2)}%
                  </div>
                </div>
              </div>
            </CardContent>
          )}
        </Card>
      )}

      {/* Remaining Tax Lots */}
      {remaining_lots && remaining_lots.length > 0 && (
        <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]">
          <CardHeader 
            className="cursor-pointer"
            onClick={() => setShowTaxLots(!showTaxLots)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2">
                <FileText className="w-5 h-5 text-blue-400" />
                Tax Lots ({remaining_lots.length} lots)
              </CardTitle>
              {showTaxLots ? (
                <ChevronUp className="w-5 h-5 text-[#8A8A93]" />
              ) : (
                <ChevronDown className="w-5 h-5 text-[#8A8A93]" />
              )}
            </div>
          </CardHeader>
          {showTaxLots && (
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-[#1F1F22]">
                      <th className="text-left py-2 px-3 text-[#8A8A93]">Date Acquired</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Amount</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Price per Unit</th>
                      <th className="text-right py-2 px-3 text-[#8A8A93]">Total Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {remaining_lots.map((lot, idx) => (
                      <tr key={idx} className="border-b border-[#1F1F22]/50 hover:bg-[#161618]/30">
                        <td className="py-2 px-3 text-white">{lot.date}</td>
                        <td className="py-2 px-3 text-right text-white font-mono">
                          {formatNumber(lot.amount)} {symbol}
                        </td>
                        <td className="py-2 px-3 text-right text-white">
                          {formatUSD(lot.price_usd)}
                        </td>
                        <td className="py-2 px-3 text-right text-white">
                          {formatUSD(lot.amount * lot.price_usd)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
};
