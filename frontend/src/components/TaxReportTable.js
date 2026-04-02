import React, { useState, useMemo } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { 
  ArrowUpDown, 
  ArrowUp, 
  ArrowDown, 
  Download,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Clock,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

// Format currency
const formatCurrency = (value, decimals = 2) => {
  if (value === null || value === undefined || isNaN(value)) return '$0.00';
  const num = Number(value);
  if (Math.abs(num) >= 1000000) {
    return `$${(num / 1000000).toFixed(2)}M`;
  }
  if (Math.abs(num) >= 1000) {
    return `$${(num / 1000).toFixed(2)}K`;
  }
  return `$${num.toFixed(decimals)}`;
};

// Format percentage
const formatPercent = (value) => {
  if (value === null || value === undefined || isNaN(value)) return '0.00%';
  return `${Number(value) >= 0 ? '+' : ''}${Number(value).toFixed(2)}%`;
};

// Format quantity
const formatQty = (value) => {
  if (value === null || value === undefined || isNaN(value)) return '0';
  const num = Number(value);
  if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`;
  if (num >= 1000) return `${(num / 1000).toFixed(2)}K`;
  if (num < 0.0001) return num.toExponential(2);
  return num.toFixed(6);
};

// Gain/Loss cell with color coding
const GainLossCell = ({ value, isPercent = false }) => {
  const num = Number(value) || 0;
  const isPositive = num >= 0;
  const color = isPositive ? 'text-green-400' : 'text-red-400';
  
  return (
    <span className={`${color} font-medium`}>
      {isPercent ? formatPercent(num) : formatCurrency(num)}
    </span>
  );
};

// Summary Card Component
const SummaryCard = ({ title, value, subtitle, icon: Icon, trend, trendValue }) => (
  <Card className="bg-slate-800/50 border-slate-700">
    <CardContent className="p-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs text-gray-400 uppercase tracking-wide">{title}</p>
          <p className="text-xl font-bold text-white mt-1">{value}</p>
          {subtitle && <p className="text-xs text-gray-500 mt-1">{subtitle}</p>}
        </div>
        <div className="flex flex-col items-end">
          {Icon && <Icon className="w-8 h-8 text-purple-400 opacity-50" />}
          {trend && (
            <div className={`flex items-center text-xs mt-2 ${trend === 'up' ? 'text-green-400' : 'text-red-400'}`}>
              {trend === 'up' ? <TrendingUp className="w-3 h-3 mr-1" /> : <TrendingDown className="w-3 h-3 mr-1" />}
              {trendValue}
            </div>
          )}
        </div>
      </div>
    </CardContent>
  </Card>
);

export const TaxReportTable = ({ taxData, holdings, selectedYear }) => {
  const [sortColumn, setSortColumn] = useState('totalGainLoss');
  const [sortDirection, setSortDirection] = useState('desc');
  const [expandedSections, setExpandedSections] = useState({
    shortTerm: true,
    longTerm: true,
    unrealized: true
  });

  // Process holdings data into table rows
  const processedData = useMemo(() => {
    if (!taxData) return { rows: [], summary: {} };

    const realizedGains = taxData.tax_data?.realized_gains || [];
    const allTransactions = taxData.tax_data?.all_transactions || [];
    const summary = taxData.tax_data?.summary || {};
    
    // Group by asset
    const assetMap = new Map();
    
    // Process realized gains
    realizedGains.forEach(gain => {
      const asset = gain.asset;
      if (!assetMap.has(asset)) {
        assetMap.set(asset, {
          symbol: asset,
          currentPrice: 0,
          quantity: 0,
          avgCostBasis: 0,
          costBasisTotal: 0,
          currentValue: 0,
          realizedGainLoss: 0,
          realizedGainLossPercent: 0,
          unrealizedGainLoss: 0,
          unrealizedGainLossPercent: 0,
          shortTermGain: 0,
          longTermGain: 0,
          disposals: [],
          lots: []
        });
      }
      
      const entry = assetMap.get(asset);
      entry.realizedGainLoss += gain.gain_loss || 0;
      entry.costBasisTotal += gain.cost_basis || 0;
      
      if (gain.holding_period === 'short-term') {
        entry.shortTermGain += gain.gain_loss || 0;
      } else {
        entry.longTermGain += gain.gain_loss || 0;
      }
      
      entry.disposals.push(gain);
    });

    // Add unrealized positions from holdings
    if (holdings) {
      Object.entries(holdings).forEach(([asset, data]) => {
        if (!assetMap.has(asset)) {
          assetMap.set(asset, {
            symbol: asset,
            currentPrice: data.current_price || 0,
            quantity: data.quantity || 0,
            avgCostBasis: data.avg_cost_basis || 0,
            costBasisTotal: (data.quantity || 0) * (data.avg_cost_basis || 0),
            currentValue: data.current_value || 0,
            realizedGainLoss: 0,
            realizedGainLossPercent: 0,
            unrealizedGainLoss: data.unrealized_gain || 0,
            unrealizedGainLossPercent: data.unrealized_gain_pct || 0,
            shortTermGain: 0,
            longTermGain: 0,
            disposals: [],
            lots: data.lots || []
          });
        } else {
          const entry = assetMap.get(asset);
          entry.currentPrice = data.current_price || entry.currentPrice;
          entry.quantity = data.quantity || 0;
          entry.avgCostBasis = data.avg_cost_basis || 0;
          entry.currentValue = data.current_value || 0;
          entry.unrealizedGainLoss = data.unrealized_gain || 0;
          entry.unrealizedGainLossPercent = data.unrealized_gain_pct || 0;
          entry.lots = data.lots || [];
        }
      });
    }

    // Calculate percentages and totals
    const rows = Array.from(assetMap.values()).map(row => {
      if (row.costBasisTotal > 0) {
        row.realizedGainLossPercent = (row.realizedGainLoss / row.costBasisTotal) * 100;
      }
      return row;
    });

    // Calculate totals
    const totals = {
      totalRealizedGain: rows.reduce((sum, r) => sum + r.realizedGainLoss, 0),
      totalUnrealizedGain: rows.reduce((sum, r) => sum + r.unrealizedGainLoss, 0),
      totalShortTerm: rows.reduce((sum, r) => sum + r.shortTermGain, 0),
      totalLongTerm: rows.reduce((sum, r) => sum + r.longTermGain, 0),
      totalCostBasis: rows.reduce((sum, r) => sum + r.costBasisTotal, 0),
      totalCurrentValue: rows.reduce((sum, r) => sum + r.currentValue, 0),
      totalQuantityByAsset: rows.length
    };

    return { rows, totals, summary };
  }, [taxData, holdings]);

  // Sort rows
  const sortedRows = useMemo(() => {
    const sorted = [...processedData.rows];
    sorted.sort((a, b) => {
      let aVal = a[sortColumn] || 0;
      let bVal = b[sortColumn] || 0;
      
      if (typeof aVal === 'string') {
        return sortDirection === 'asc' 
          ? aVal.localeCompare(bVal) 
          : bVal.localeCompare(aVal);
      }
      
      return sortDirection === 'asc' ? aVal - bVal : bVal - aVal;
    });
    return sorted;
  }, [processedData.rows, sortColumn, sortDirection]);

  // Handle sort
  const handleSort = (column) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('desc');
    }
  };

  // Toggle section
  const toggleSection = (section) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section]
    }));
  };

  // Export to CSV
  const exportToCSV = () => {
    const headers = [
      'Symbol',
      'Last Price',
      'Quantity',
      'Avg Cost Basis',
      'Cost Basis Total',
      'Current Value',
      'Realized Gain/Loss $',
      'Realized Gain/Loss %',
      'Unrealized Gain/Loss $',
      'Unrealized Gain/Loss %',
      'Short-Term Gain',
      'Long-Term Gain'
    ];
    
    const csvRows = [headers.join(',')];
    
    sortedRows.forEach(row => {
      csvRows.push([
        row.symbol,
        row.currentPrice.toFixed(2),
        row.quantity,
        row.avgCostBasis.toFixed(2),
        row.costBasisTotal.toFixed(2),
        row.currentValue.toFixed(2),
        row.realizedGainLoss.toFixed(2),
        row.realizedGainLossPercent.toFixed(2),
        row.unrealizedGainLoss.toFixed(2),
        row.unrealizedGainLossPercent.toFixed(2),
        row.shortTermGain.toFixed(2),
        row.longTermGain.toFixed(2)
      ].join(','));
    });
    
    const blob = new Blob([csvRows.join('\n')], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `tax_report_${selectedYear}.csv`;
    a.click();
  };

  const { totals } = processedData;

  // Sort icon
  const SortIcon = ({ column }) => {
    if (sortColumn !== column) return <ArrowUpDown className="w-3 h-3 ml-1 opacity-50" />;
    return sortDirection === 'asc' 
      ? <ArrowUp className="w-3 h-3 ml-1" /> 
      : <ArrowDown className="w-3 h-3 ml-1" />;
  };

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <SummaryCard
          title="Total Realized Gain"
          value={formatCurrency(totals.totalRealizedGain)}
          subtitle={`${selectedYear} Tax Year`}
          icon={DollarSign}
          trend={totals.totalRealizedGain >= 0 ? 'up' : 'down'}
          trendValue={formatPercent((totals.totalRealizedGain / (totals.totalCostBasis || 1)) * 100)}
        />
        <SummaryCard
          title="Short-Term Gains"
          value={formatCurrency(totals.totalShortTerm)}
          subtitle="Held < 1 year"
          icon={Clock}
          trend={totals.totalShortTerm >= 0 ? 'up' : 'down'}
        />
        <SummaryCard
          title="Long-Term Gains"
          value={formatCurrency(totals.totalLongTerm)}
          subtitle="Held > 1 year"
          icon={TrendingUp}
          trend={totals.totalLongTerm >= 0 ? 'up' : 'down'}
        />
        <SummaryCard
          title="Unrealized Gain"
          value={formatCurrency(totals.totalUnrealizedGain)}
          subtitle="Current holdings"
          icon={TrendingUp}
          trend={totals.totalUnrealizedGain >= 0 ? 'up' : 'down'}
        />
      </div>

      {/* Realized vs Unrealized Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-gray-300">Realized Gains (Taxable)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-400">Short-Term (taxed as income)</span>
                <GainLossCell value={totals.totalShortTerm} />
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-400">Long-Term (capital gains rate)</span>
                <GainLossCell value={totals.totalLongTerm} />
              </div>
              <div className="border-t border-slate-600 pt-2 mt-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-white">Total Realized</span>
                  <span className={`text-lg font-bold ${totals.totalRealizedGain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(totals.totalRealizedGain)}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-gray-300">Unrealized Gains (Not Yet Taxable)</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-400">Current Holdings Value</span>
                <span className="text-white">{formatCurrency(totals.totalCurrentValue)}</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-xs text-gray-400">Total Cost Basis</span>
                <span className="text-gray-300">{formatCurrency(totals.totalCostBasis)}</span>
              </div>
              <div className="border-t border-slate-600 pt-2 mt-2">
                <div className="flex justify-between items-center">
                  <span className="text-sm font-medium text-white">Total Unrealized</span>
                  <span className={`text-lg font-bold ${totals.totalUnrealizedGain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatCurrency(totals.totalUnrealizedGain)}
                  </span>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Main Table */}
      <Card className="bg-slate-800/50 border-slate-700">
        <CardHeader className="pb-2 flex flex-row items-center justify-between">
          <CardTitle className="text-sm text-gray-300">
            Portfolio Holdings & Tax Lots ({selectedYear})
          </CardTitle>
          <Button
            size="sm"
            variant="outline"
            onClick={exportToCSV}
            className="text-xs border-slate-600"
          >
            <Download className="w-3 h-3 mr-1" />
            Export CSV
          </Button>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead className="bg-slate-900/50">
                <tr className="text-left text-gray-400 border-b border-slate-700">
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 whitespace-nowrap"
                    onClick={() => handleSort('symbol')}
                  >
                    <div className="flex items-center">
                      Symbol
                      <SortIcon column="symbol" />
                    </div>
                  </th>
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 text-right whitespace-nowrap"
                    onClick={() => handleSort('currentPrice')}
                  >
                    <div className="flex items-center justify-end">
                      Last Price
                      <SortIcon column="currentPrice" />
                    </div>
                  </th>
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 text-right whitespace-nowrap"
                    onClick={() => handleSort('quantity')}
                  >
                    <div className="flex items-center justify-end">
                      Quantity
                      <SortIcon column="quantity" />
                    </div>
                  </th>
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 text-right whitespace-nowrap"
                    onClick={() => handleSort('avgCostBasis')}
                  >
                    <div className="flex items-center justify-end">
                      Avg Cost
                      <SortIcon column="avgCostBasis" />
                    </div>
                  </th>
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 text-right whitespace-nowrap"
                    onClick={() => handleSort('costBasisTotal')}
                  >
                    <div className="flex items-center justify-end">
                      Cost Basis
                      <SortIcon column="costBasisTotal" />
                    </div>
                  </th>
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 text-right whitespace-nowrap"
                    onClick={() => handleSort('currentValue')}
                  >
                    <div className="flex items-center justify-end">
                      Current Value
                      <SortIcon column="currentValue" />
                    </div>
                  </th>
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 text-right whitespace-nowrap"
                    onClick={() => handleSort('realizedGainLoss')}
                  >
                    <div className="flex items-center justify-end">
                      Realized G/L
                      <SortIcon column="realizedGainLoss" />
                    </div>
                  </th>
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 text-right whitespace-nowrap"
                    onClick={() => handleSort('unrealizedGainLoss')}
                  >
                    <div className="flex items-center justify-end">
                      Unrealized G/L
                      <SortIcon column="unrealizedGainLoss" />
                    </div>
                  </th>
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 text-right whitespace-nowrap"
                    onClick={() => handleSort('shortTermGain')}
                  >
                    <div className="flex items-center justify-end">
                      Short-Term
                      <SortIcon column="shortTermGain" />
                    </div>
                  </th>
                  <th 
                    className="p-2 cursor-pointer hover:bg-slate-700/50 text-right whitespace-nowrap"
                    onClick={() => handleSort('longTermGain')}
                  >
                    <div className="flex items-center justify-end">
                      Long-Term
                      <SortIcon column="longTermGain" />
                    </div>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sortedRows.map((row, idx) => (
                  <tr 
                    key={row.symbol} 
                    className={`border-b border-slate-700/50 hover:bg-slate-700/30 ${idx % 2 === 0 ? 'bg-slate-800/30' : ''}`}
                  >
                    <td className="p-2">
                      <div className="flex items-center gap-2">
                        <Badge className="bg-purple-600 text-xs">{row.symbol}</Badge>
                      </div>
                    </td>
                    <td className="p-2 text-right text-gray-300">{formatCurrency(row.currentPrice)}</td>
                    <td className="p-2 text-right text-gray-300">{formatQty(row.quantity)}</td>
                    <td className="p-2 text-right text-gray-300">{formatCurrency(row.avgCostBasis)}</td>
                    <td className="p-2 text-right text-gray-300">{formatCurrency(row.costBasisTotal)}</td>
                    <td className="p-2 text-right text-white font-medium">{formatCurrency(row.currentValue)}</td>
                    <td className="p-2 text-right">
                      <GainLossCell value={row.realizedGainLoss} />
                    </td>
                    <td className="p-2 text-right">
                      <GainLossCell value={row.unrealizedGainLoss} />
                    </td>
                    <td className="p-2 text-right">
                      <GainLossCell value={row.shortTermGain} />
                    </td>
                    <td className="p-2 text-right">
                      <GainLossCell value={row.longTermGain} />
                    </td>
                  </tr>
                ))}
                {/* Totals Row */}
                <tr className="bg-slate-900/80 font-medium border-t-2 border-slate-600">
                  <td className="p-2 text-white">TOTAL</td>
                  <td className="p-2 text-right text-gray-400">—</td>
                  <td className="p-2 text-right text-gray-400">—</td>
                  <td className="p-2 text-right text-gray-400">—</td>
                  <td className="p-2 text-right text-white">{formatCurrency(totals.totalCostBasis)}</td>
                  <td className="p-2 text-right text-white">{formatCurrency(totals.totalCurrentValue)}</td>
                  <td className="p-2 text-right">
                    <GainLossCell value={totals.totalRealizedGain} />
                  </td>
                  <td className="p-2 text-right">
                    <GainLossCell value={totals.totalUnrealizedGain} />
                  </td>
                  <td className="p-2 text-right">
                    <GainLossCell value={totals.totalShortTerm} />
                  </td>
                  <td className="p-2 text-right">
                    <GainLossCell value={totals.totalLongTerm} />
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default TaxReportTable;
