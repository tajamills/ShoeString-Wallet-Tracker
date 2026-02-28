import React, { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
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
  Wand2
} from 'lucide-react';

export const TaxDashboard = ({ 
  taxData, 
  symbol, 
  formatUSD, 
  formatNumber, 
  onExportForm8949,
  onExportScheduleD,
  onBatchCategorize 
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
      return <span className="text-green-400">+{formatted}</span>;
    }
    return <span className="text-red-400">-{formatted}</span>;
  };

  return (
    <div className="space-y-6">
      {/* Tax Summary Header */}
      <Card className="bg-gradient-to-br from-indigo-900/40 to-purple-900/30 border-indigo-700">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <Calculator className="w-6 h-6 text-indigo-400" />
            Tax Summary
            <Badge className="bg-indigo-600 ml-2">{method}</Badge>
          </CardTitle>
          <CardDescription className="text-gray-400">
            Cost basis and capital gains calculated using {method} method
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Total Realized Gains */}
            <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
              <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                <DollarSign className="w-4 h-4" />
                Total Realized Gains
              </div>
              <div className="text-2xl font-bold">
                {formatGainLoss(summary.total_realized_gain)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                From {summary.sell_count} sell transactions
              </div>
            </div>

            {/* Short-term vs Long-term */}
            <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
              <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                <Clock className="w-4 h-4" />
                Gains by Holding Period
              </div>
              <div className="space-y-1">
                <div className="flex justify-between">
                  <span className="text-xs text-gray-400">Short-term (&lt;1yr):</span>
                  <span className="text-sm font-semibold">
                    {formatGainLoss(summary.short_term_gains)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-xs text-gray-400">Long-term (≥1yr):</span>
                  <span className="text-sm font-semibold">
                    {formatGainLoss(summary.long_term_gains)}
                  </span>
                </div>
              </div>
            </div>

            {/* Unrealized Gains */}
            <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
              <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                <TrendingUp className="w-4 h-4" />
                Unrealized Gains
              </div>
              <div className="text-2xl font-bold">
                {formatGainLoss(summary.total_unrealized_gain)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Current holdings value change
              </div>
            </div>

            {/* Total Cost Basis */}
            <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
              <div className="flex items-center gap-2 text-sm text-gray-400 mb-2">
                <FileText className="w-4 h-4" />
                Total Cost Basis
              </div>
              <div className="text-2xl font-bold text-white">
                {formatUSD(unrealized_gains?.total_cost_basis || 0)}
              </div>
              <div className="text-xs text-gray-500 mt-1">
                Of remaining holdings
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Export Tax Forms */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-green-400" />
            Export Tax Forms
          </CardTitle>
          <CardDescription className="text-gray-400">
            Download IRS-compatible tax reports
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-3">
            <Button
              onClick={() => onExportForm8949('all')}
              className="bg-green-600 hover:bg-green-700"
              data-testid="export-form-8949-btn"
            >
              <Download className="w-4 h-4 mr-2" />
              Export Form 8949 (All)
            </Button>
            <Button
              onClick={() => onExportForm8949('short-term')}
              variant="outline"
              className="border-slate-600 text-gray-300"
            >
              <Download className="w-4 h-4 mr-2" />
              Short-term Only
            </Button>
            <Button
              onClick={() => onExportForm8949('long-term')}
              variant="outline"
              className="border-slate-600 text-gray-300"
            >
              <Download className="w-4 h-4 mr-2" />
              Long-term Only
            </Button>
          </div>
          <Alert className="mt-4 bg-blue-900/20 border-blue-700 text-blue-300">
            <Info className="h-4 w-4" />
            <AlertDescription className="text-sm">
              Form 8949 is used to report sales and exchanges of capital assets. 
              Consult a tax professional for advice specific to your situation.
            </AlertDescription>
          </Alert>
        </CardContent>
      </Card>

      {/* Realized Gains Details */}
      {realized_gains && realized_gains.length > 0 && (
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader 
            className="cursor-pointer"
            onClick={() => setShowRealizedDetails(!showRealizedDetails)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2">
                <TrendingDown className="w-5 h-5 text-red-400" />
                Realized Gains/Losses ({realized_gains.length} dispositions)
              </CardTitle>
              {showRealizedDetails ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </div>
          </CardHeader>
          {showRealizedDetails && (
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left py-2 px-3 text-gray-400">Buy Date</th>
                      <th className="text-left py-2 px-3 text-gray-400">Sell Date</th>
                      <th className="text-right py-2 px-3 text-gray-400">Amount</th>
                      <th className="text-right py-2 px-3 text-gray-400">Cost Basis</th>
                      <th className="text-right py-2 px-3 text-gray-400">Proceeds</th>
                      <th className="text-right py-2 px-3 text-gray-400">Gain/Loss</th>
                      <th className="text-center py-2 px-3 text-gray-400">Term</th>
                    </tr>
                  </thead>
                  <tbody>
                    {realized_gains.slice(0, 20).map((gain, idx) => (
                      <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td className="py-2 px-3 text-gray-300">{gain.buy_date}</td>
                        <td className="py-2 px-3 text-gray-300">{gain.sell_date}</td>
                        <td className="py-2 px-3 text-right text-white font-mono">
                          {formatNumber(gain.amount)} {symbol}
                        </td>
                        <td className="py-2 px-3 text-right text-gray-300">
                          {formatUSD(gain.cost_basis)}
                        </td>
                        <td className="py-2 px-3 text-right text-gray-300">
                          {formatUSD(gain.proceeds)}
                        </td>
                        <td className="py-2 px-3 text-right font-semibold">
                          {formatGainLoss(gain.gain_loss)}
                        </td>
                        <td className="py-2 px-3 text-center">
                          <Badge className={gain.holding_period === 'long-term' ? 'bg-green-900/50 text-green-300' : 'bg-orange-900/50 text-orange-300'}>
                            {gain.holding_period === 'long-term' ? 'Long' : 'Short'}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {realized_gains.length > 20 && (
                  <p className="text-center text-gray-500 text-sm mt-3">
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
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader 
            className="cursor-pointer"
            onClick={() => setShowUnrealizedDetails(!showUnrealizedDetails)}
          >
            <div className="flex items-center justify-between">
              <CardTitle className="text-white flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-400" />
                Unrealized Gains ({unrealized_gains.lots.length} open positions)
              </CardTitle>
              {showUnrealizedDetails ? (
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </div>
          </CardHeader>
          {showUnrealizedDetails && (
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left py-2 px-3 text-gray-400">Acquisition Date</th>
                      <th className="text-right py-2 px-3 text-gray-400">Amount</th>
                      <th className="text-right py-2 px-3 text-gray-400">Buy Price</th>
                      <th className="text-right py-2 px-3 text-gray-400">Current Price</th>
                      <th className="text-right py-2 px-3 text-gray-400">Cost Basis</th>
                      <th className="text-right py-2 px-3 text-gray-400">Current Value</th>
                      <th className="text-right py-2 px-3 text-gray-400">Unrealized Gain</th>
                      <th className="text-right py-2 px-3 text-gray-400">% Change</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unrealized_gains.lots.slice(0, 15).map((lot, idx) => (
                      <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td className="py-2 px-3 text-gray-300">{lot.buy_date}</td>
                        <td className="py-2 px-3 text-right text-white font-mono">
                          {formatNumber(lot.amount)} {symbol}
                        </td>
                        <td className="py-2 px-3 text-right text-gray-300">
                          {formatUSD(lot.buy_price)}
                        </td>
                        <td className="py-2 px-3 text-right text-gray-300">
                          {formatUSD(lot.current_price)}
                        </td>
                        <td className="py-2 px-3 text-right text-gray-300">
                          {formatUSD(lot.cost_basis)}
                        </td>
                        <td className="py-2 px-3 text-right text-white">
                          {formatUSD(lot.current_value)}
                        </td>
                        <td className="py-2 px-3 text-right font-semibold">
                          {formatGainLoss(lot.unrealized_gain)}
                        </td>
                        <td className="py-2 px-3 text-right">
                          <span className={lot.gain_percentage >= 0 ? 'text-green-400' : 'text-red-400'}>
                            {lot.gain_percentage >= 0 ? '+' : ''}{lot.gain_percentage.toFixed(2)}%
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {unrealized_gains.lots.length > 15 && (
                  <p className="text-center text-gray-500 text-sm mt-3">
                    Showing 15 of {unrealized_gains.lots.length} open positions.
                  </p>
                )}
              </div>

              {/* Unrealized Summary */}
              <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-3">
                <div className="bg-slate-900/50 rounded p-3">
                  <div className="text-xs text-gray-400">Total Cost Basis</div>
                  <div className="text-lg font-bold text-white">{formatUSD(unrealized_gains.total_cost_basis)}</div>
                </div>
                <div className="bg-slate-900/50 rounded p-3">
                  <div className="text-xs text-gray-400">Current Value</div>
                  <div className="text-lg font-bold text-white">{formatUSD(unrealized_gains.total_current_value)}</div>
                </div>
                <div className="bg-slate-900/50 rounded p-3">
                  <div className="text-xs text-gray-400">Total Unrealized</div>
                  <div className="text-lg font-bold">{formatGainLoss(unrealized_gains.total_gain)}</div>
                </div>
                <div className="bg-slate-900/50 rounded p-3">
                  <div className="text-xs text-gray-400">Overall % Change</div>
                  <div className={`text-lg font-bold ${unrealized_gains.total_gain_percentage >= 0 ? 'text-green-400' : 'text-red-400'}`}>
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
        <Card className="bg-slate-800/50 border-slate-700">
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
                <ChevronUp className="w-5 h-5 text-gray-400" />
              ) : (
                <ChevronDown className="w-5 h-5 text-gray-400" />
              )}
            </div>
          </CardHeader>
          {showTaxLots && (
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-slate-700">
                      <th className="text-left py-2 px-3 text-gray-400">Date Acquired</th>
                      <th className="text-right py-2 px-3 text-gray-400">Amount</th>
                      <th className="text-right py-2 px-3 text-gray-400">Price per Unit</th>
                      <th className="text-right py-2 px-3 text-gray-400">Total Cost</th>
                    </tr>
                  </thead>
                  <tbody>
                    {remaining_lots.map((lot, idx) => (
                      <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                        <td className="py-2 px-3 text-gray-300">{lot.date}</td>
                        <td className="py-2 px-3 text-right text-white font-mono">
                          {formatNumber(lot.amount)} {symbol}
                        </td>
                        <td className="py-2 px-3 text-right text-gray-300">
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
