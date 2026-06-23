import React, { useState, useMemo } from 'react';
import { Plus, Trash, Calculator, TrendingUp, DollarSign, Percent, Coins } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Cell } from 'recharts';

// Exit Strategy Dashboard Component
const ExitStrategyDashboard = () => {
  // Tax Profile State
  const [taxProfile, setTaxProfile] = useState({
    capitalGainsRate: 15, // Default 15%
    incomeBracket: 'middle' // low, middle, high
  });

  // Asset State
  const [asset, setAsset] = useState({
    symbol: 'BTC',
    averageCostBasis: 30000,
    totalQuantity: 1.5
  });

  // Exit Tiers State
  const [exitTiers, setExitTiers] = useState([
    { id: 1, name: 'Tier 1', sellPercentage: 25, targetPrice: 80000 },
    { id: 2, name: 'Tier 2', sellPercentage: 25, targetPrice: 100000 },
    { id: 3, name: 'Tier 3', sellPercentage: 25, targetPrice: 150000 },
    { id: 4, name: 'Tier 4', sellPercentage: 25, targetPrice: 200000 },
  ]);

  // Add new tier
  const addTier = () => {
    const newId = Math.max(...exitTiers.map(t => t.id), 0) + 1;
    setExitTiers([...exitTiers, {
      id: newId,
      name: `Tier ${newId}`,
      sellPercentage: 10,
      targetPrice: 50000
    }]);
  };

  // Remove tier
  const removeTier = (id) => {
    if (exitTiers.length > 1) {
      setExitTiers(exitTiers.filter(t => t.id !== id));
    }
  };

  // Update tier
  const updateTier = (id, field, value) => {
    setExitTiers(exitTiers.map(t => 
      t.id === id ? { ...t, [field]: parseFloat(value) || 0 } : t
    ));
  };

  // Calculate results for each tier
  const calculations = useMemo(() => {
    let remainingQuantity = asset.totalQuantity;
    
    return exitTiers.map(tier => {
      const tokensToSell = (tier.sellPercentage / 100) * asset.totalQuantity;
      const actualTokensSold = Math.min(tokensToSell, remainingQuantity);
      remainingQuantity -= actualTokensSold;
      
      const grossRevenue = actualTokensSold * tier.targetPrice;
      const costBasisUsed = actualTokensSold * asset.averageCostBasis;
      const capitalGains = grossRevenue - costBasisUsed;
      const taxOwed = capitalGains > 0 ? capitalGains * (taxProfile.capitalGainsRate / 100) : 0;
      const netTakeHome = grossRevenue - taxOwed;
      
      return {
        ...tier,
        tokensSold: actualTokensSold,
        grossRevenue,
        costBasisUsed,
        capitalGains,
        taxOwed,
        netTakeHome,
        effectiveTaxRate: grossRevenue > 0 ? (taxOwed / grossRevenue) * 100 : 0
      };
    });
  }, [exitTiers, asset, taxProfile]);

  // Summary totals
  const totals = useMemo(() => {
    return calculations.reduce((acc, tier) => ({
      tokensSold: acc.tokensSold + tier.tokensSold,
      grossRevenue: acc.grossRevenue + tier.grossRevenue,
      costBasisUsed: acc.costBasisUsed + tier.costBasisUsed,
      capitalGains: acc.capitalGains + tier.capitalGains,
      taxOwed: acc.taxOwed + tier.taxOwed,
      netTakeHome: acc.netTakeHome + tier.netTakeHome
    }), { tokensSold: 0, grossRevenue: 0, costBasisUsed: 0, capitalGains: 0, taxOwed: 0, netTakeHome: 0 });
  }, [calculations]);

  // Chart data
  const chartData = calculations.map(tier => ({
    name: tier.name,
    'Gross Revenue': Math.round(tier.grossRevenue),
    'Net Take-Home': Math.round(tier.netTakeHome),
    'Tax Owed': Math.round(tier.taxOwed)
  }));

  const formatCurrency = (value) => {
    return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
  };

  const formatNumber = (value, decimals = 4) => {
    return new Intl.NumberFormat('en-US', { maximumFractionDigits: decimals }).format(value);
  };

  return (
    <div className="min-h-screen bg-[#050505] text-white p-4 sm:p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="border-b border-[#1F1F22] pb-4">
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
            CRYPTO EXIT STRATEGY
            <span className="text-[#00C805] ml-2">CALCULATOR</span>
          </h1>
          <p className="text-[#8A8A93] text-sm mt-1 font-mono">
            Plan your exit. Know your take-home.
          </p>
        </div>

        {/* Configuration Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Tax Profile Card */}
          <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
            <div className="flex items-center gap-2 mb-4">
              <Percent className="w-5 h-5 text-[#00C805]" />
              <h2 className="text-white font-semibold">TAX PROFILE</h2>
            </div>
            <div className="space-y-4">
              <div>
                <label className="text-[#8A8A93] text-xs font-mono block mb-2">
                  CAPITAL GAINS TAX RATE (%)
                </label>
                <input
                  type="number"
                  value={taxProfile.capitalGainsRate}
                  onChange={(e) => setTaxProfile({ ...taxProfile, capitalGainsRate: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-[#161618] border border-[#1F1F22] text-white px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-[#00C805]"
                  min="0"
                  max="100"
                  step="0.1"
                />
              </div>
              <div className="grid grid-cols-3 gap-2">
                {[
                  { label: '0%', value: 0 },
                  { label: '15%', value: 15 },
                  { label: '20%', value: 20 },
                  { label: '25%', value: 25 },
                  { label: '30%', value: 30 },
                  { label: '37%', value: 37 },
                ].map(preset => (
                  <button
                    key={preset.value}
                    onClick={() => setTaxProfile({ ...taxProfile, capitalGainsRate: preset.value })}
                    className={`px-2 py-1.5 text-xs font-mono border transition-colors ${
                      taxProfile.capitalGainsRate === preset.value
                        ? 'bg-[#00C805] text-black border-[#00C805]'
                        : 'border-[#1F1F22] text-[#8A8A93] hover:border-[#00C805]'
                    }`}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Asset Card */}
          <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
            <div className="flex items-center gap-2 mb-4">
              <Coins className="w-5 h-5 text-[#00C805]" />
              <h2 className="text-white font-semibold">YOUR ASSET</h2>
            </div>
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-[#8A8A93] text-xs font-mono block mb-2">TOKEN SYMBOL</label>
                  <input
                    type="text"
                    value={asset.symbol}
                    onChange={(e) => setAsset({ ...asset, symbol: e.target.value.toUpperCase() })}
                    className="w-full bg-[#161618] border border-[#1F1F22] text-white px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-[#00C805]"
                    maxLength={10}
                  />
                </div>
                <div>
                  <label className="text-[#8A8A93] text-xs font-mono block mb-2">QUANTITY HELD</label>
                  <input
                    type="number"
                    value={asset.totalQuantity}
                    onChange={(e) => setAsset({ ...asset, totalQuantity: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-[#161618] border border-[#1F1F22] text-white px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-[#00C805]"
                    min="0"
                    step="0.0001"
                  />
                </div>
              </div>
              <div>
                <label className="text-[#8A8A93] text-xs font-mono block mb-2">AVERAGE COST BASIS (USD)</label>
                <input
                  type="number"
                  value={asset.averageCostBasis}
                  onChange={(e) => setAsset({ ...asset, averageCostBasis: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-[#161618] border border-[#1F1F22] text-white px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-[#00C805]"
                  min="0"
                  step="0.01"
                />
              </div>
              <div className="bg-[#161618] border border-[#1F1F22] p-3">
                <div className="flex justify-between items-center">
                  <span className="text-[#8A8A93] text-xs font-mono">TOTAL INVESTED</span>
                  <span className="text-white font-mono font-bold">
                    {formatCurrency(asset.totalQuantity * asset.averageCostBasis)}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Exit Tiers Table */}
        <div className="bg-[#0C0C0E] border border-[#1F1F22]">
          <div className="flex items-center justify-between p-4 border-b border-[#1F1F22]">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-[#00C805]" />
              <h2 className="text-white font-semibold">EXIT STRATEGY TIERS</h2>
            </div>
            <button
              onClick={addTier}
              className="flex items-center gap-1 bg-[#00C805] text-black px-3 py-1.5 text-sm font-semibold hover:bg-[#00a804] transition-colors"
            >
              <Plus className="w-4 h-4" />
              ADD TIER
            </button>
          </div>

          {/* Desktop Table */}
          <div className="hidden md:block overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-[#1F1F22] bg-[#161618]">
                  <th className="text-left px-4 py-3 text-[#8A8A93] text-xs font-mono font-semibold">TIER</th>
                  <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono font-semibold">SELL %</th>
                  <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono font-semibold">TARGET PRICE</th>
                  <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono font-semibold">TOKENS SOLD</th>
                  <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono font-semibold">GROSS REVENUE</th>
                  <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono font-semibold">CAPITAL GAINS</th>
                  <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono font-semibold">TAX OWED</th>
                  <th className="text-right px-4 py-3 text-[#00C805] text-xs font-mono font-semibold">NET TAKE-HOME</th>
                  <th className="px-4 py-3"></th>
                </tr>
              </thead>
              <tbody>
                {calculations.map((tier, index) => (
                  <tr key={tier.id} className="border-b border-[#1F1F22] hover:bg-[#161618]">
                    <td className="px-4 py-3">
                      <span className="text-white font-mono">{tier.name}</span>
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type="number"
                        value={tier.sellPercentage}
                        onChange={(e) => updateTier(tier.id, 'sellPercentage', e.target.value)}
                        className="w-20 bg-[#161618] border border-[#1F1F22] text-white px-2 py-1 text-right font-mono text-sm focus:outline-none focus:ring-1 focus:ring-[#00C805]"
                        min="0"
                        max="100"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <input
                        type="number"
                        value={tier.targetPrice}
                        onChange={(e) => updateTier(tier.id, 'targetPrice', e.target.value)}
                        className="w-28 bg-[#161618] border border-[#1F1F22] text-white px-2 py-1 text-right font-mono text-sm focus:outline-none focus:ring-1 focus:ring-[#00C805]"
                        min="0"
                      />
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-[#8A8A93]">
                      {formatNumber(tier.tokensSold)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-white">
                      {formatCurrency(tier.grossRevenue)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono">
                      <span className={tier.capitalGains >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'}>
                        {formatCurrency(tier.capitalGains)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-[#FF3B30]">
                      -{formatCurrency(tier.taxOwed)}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-[#00C805] font-bold">
                      {formatCurrency(tier.netTakeHome)}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => removeTier(tier.id)}
                        className="p-1 text-[#8A8A93] hover:text-[#FF3B30] transition-colors"
                        disabled={exitTiers.length <= 1}
                      >
                        <Trash className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
                {/* Totals Row */}
                <tr className="bg-[#161618] font-bold">
                  <td className="px-4 py-3 text-white font-mono">TOTAL</td>
                  <td className="px-4 py-3 text-right font-mono text-[#8A8A93]">
                    {exitTiers.reduce((sum, t) => sum + t.sellPercentage, 0)}%
                  </td>
                  <td className="px-4 py-3"></td>
                  <td className="px-4 py-3 text-right font-mono text-[#8A8A93]">
                    {formatNumber(totals.tokensSold)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-white">
                    {formatCurrency(totals.grossRevenue)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-[#00C805]">
                    {formatCurrency(totals.capitalGains)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-[#FF3B30]">
                    -{formatCurrency(totals.taxOwed)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-[#00C805]">
                    {formatCurrency(totals.netTakeHome)}
                  </td>
                  <td className="px-4 py-3"></td>
                </tr>
              </tbody>
            </table>
          </div>

          {/* Mobile Cards */}
          <div className="md:hidden p-4 space-y-4">
            {calculations.map((tier) => (
              <div key={tier.id} className="bg-[#161618] border border-[#1F1F22] p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-white font-mono font-bold">{tier.name}</span>
                  <button
                    onClick={() => removeTier(tier.id)}
                    className="p-1 text-[#8A8A93] hover:text-[#FF3B30]"
                    disabled={exitTiers.length <= 1}
                  >
                    <Trash className="w-4 h-4" />
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-[#8A8A93] text-xs block mb-1">SELL %</label>
                    <input
                      type="number"
                      value={tier.sellPercentage}
                      onChange={(e) => updateTier(tier.id, 'sellPercentage', e.target.value)}
                      className="w-full bg-[#0C0C0E] border border-[#1F1F22] text-white px-2 py-1.5 font-mono text-sm"
                    />
                  </div>
                  <div>
                    <label className="text-[#8A8A93] text-xs block mb-1">TARGET PRICE</label>
                    <input
                      type="number"
                      value={tier.targetPrice}
                      onChange={(e) => updateTier(tier.id, 'targetPrice', e.target.value)}
                      className="w-full bg-[#0C0C0E] border border-[#1F1F22] text-white px-2 py-1.5 font-mono text-sm"
                    />
                  </div>
                </div>
                <div className="pt-2 border-t border-[#1F1F22] space-y-1">
                  <div className="flex justify-between text-sm">
                    <span className="text-[#8A8A93]">Gross Revenue</span>
                    <span className="text-white font-mono">{formatCurrency(tier.grossRevenue)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-[#8A8A93]">Tax Owed</span>
                    <span className="text-[#FF3B30] font-mono">-{formatCurrency(tier.taxOwed)}</span>
                  </div>
                  <div className="flex justify-between text-sm font-bold">
                    <span className="text-[#8A8A93]">Net Take-Home</span>
                    <span className="text-[#00C805] font-mono">{formatCurrency(tier.netTakeHome)}</span>
                  </div>
                </div>
              </div>
            ))}

            {/* Mobile Totals */}
            <div className="bg-[#00C805]/10 border border-[#00C805]/30 p-4">
              <div className="text-[#00C805] font-bold mb-2">TOTAL SUMMARY</div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-[#8A8A93]">Gross Revenue</span>
                  <span className="text-white font-mono">{formatCurrency(totals.grossRevenue)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#8A8A93]">Total Tax</span>
                  <span className="text-[#FF3B30] font-mono">-{formatCurrency(totals.taxOwed)}</span>
                </div>
                <div className="flex justify-between font-bold text-base pt-1 border-t border-[#00C805]/30">
                  <span className="text-white">Net Take-Home</span>
                  <span className="text-[#00C805] font-mono">{formatCurrency(totals.netTakeHome)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Chart Section */}
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="flex items-center gap-2 mb-4">
            <Calculator className="w-5 h-5 text-[#00C805]" />
            <h2 className="text-white font-semibold">REVENUE BREAKDOWN BY TIER</h2>
          </div>
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F1F22" />
                <XAxis 
                  dataKey="name" 
                  stroke="#8A8A93" 
                  tick={{ fill: '#8A8A93', fontSize: 12 }}
                />
                <YAxis 
                  stroke="#8A8A93" 
                  tick={{ fill: '#8A8A93', fontSize: 12 }}
                  tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#0C0C0E', 
                    border: '1px solid #1F1F22',
                    borderRadius: 0
                  }}
                  labelStyle={{ color: '#fff' }}
                  formatter={(value) => [formatCurrency(value), '']}
                />
                <Legend />
                <Bar dataKey="Gross Revenue" fill="#8A8A93" />
                <Bar dataKey="Net Take-Home" fill="#00C805" />
                <Bar dataKey="Tax Owed" fill="#FF3B30" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
            <div className="text-[#8A8A93] text-xs font-mono mb-1">TOTAL INVESTED</div>
            <div className="text-white text-xl font-mono font-bold">
              {formatCurrency(asset.totalQuantity * asset.averageCostBasis)}
            </div>
          </div>
          <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
            <div className="text-[#8A8A93] text-xs font-mono mb-1">GROSS REVENUE</div>
            <div className="text-white text-xl font-mono font-bold">
              {formatCurrency(totals.grossRevenue)}
            </div>
          </div>
          <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
            <div className="text-[#8A8A93] text-xs font-mono mb-1">TOTAL TAX</div>
            <div className="text-[#FF3B30] text-xl font-mono font-bold">
              -{formatCurrency(totals.taxOwed)}
            </div>
          </div>
          <div className="bg-[#00C805]/10 border border-[#00C805]/30 p-4">
            <div className="text-[#00C805] text-xs font-mono mb-1">NET TAKE-HOME</div>
            <div className="text-[#00C805] text-xl font-mono font-bold">
              {formatCurrency(totals.netTakeHome)}
            </div>
          </div>
        </div>

        {/* ROI Summary */}
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-center">
            <div>
              <div className="text-[#8A8A93] text-xs font-mono mb-1">GROSS PROFIT</div>
              <div className={`text-2xl font-mono font-bold ${totals.capitalGains >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'}`}>
                {totals.capitalGains >= 0 ? '+' : ''}{formatCurrency(totals.capitalGains)}
              </div>
            </div>
            <div>
              <div className="text-[#8A8A93] text-xs font-mono mb-1">ROI (BEFORE TAX)</div>
              <div className={`text-2xl font-mono font-bold ${totals.capitalGains >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'}`}>
                {((totals.capitalGains / (asset.totalQuantity * asset.averageCostBasis)) * 100).toFixed(1)}%
              </div>
            </div>
            <div>
              <div className="text-[#8A8A93] text-xs font-mono mb-1">ROI (AFTER TAX)</div>
              <div className={`text-2xl font-mono font-bold ${(totals.netTakeHome - (asset.totalQuantity * asset.averageCostBasis)) >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'}`}>
                {(((totals.netTakeHome - (asset.totalQuantity * asset.averageCostBasis)) / (asset.totalQuantity * asset.averageCostBasis)) * 100).toFixed(1)}%
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ExitStrategyDashboard;
