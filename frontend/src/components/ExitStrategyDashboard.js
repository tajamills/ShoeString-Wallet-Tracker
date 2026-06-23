import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Plus, Trash, Calculator, TrendingUp, DollarSign, Percent, Coins, Bell, Check, Save, RefreshCw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

// Exit Strategy Dashboard Component
const ExitStrategyDashboard = ({ getAuthHeader }) => {
  // Asset selection state
  const [strategies, setStrategies] = useState([]);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Current strategy being edited
  const [currentStrategy, setCurrentStrategy] = useState({
    asset_symbol: 'BTC',
    quantity: 1.0,
    average_cost_basis: 30000,
    tax_rate: 15,
    tiers: [
      { tier_id: '1', name: 'Tier 1', sell_percentage: 25, target_price: 80000, alert_created: false },
      { tier_id: '2', name: 'Tier 2', sell_percentage: 25, target_price: 100000, alert_created: false },
      { tier_id: '3', name: 'Tier 3', sell_percentage: 25, target_price: 150000, alert_created: false },
      { tier_id: '4', name: 'Tier 4', sell_percentage: 25, target_price: 200000, alert_created: false },
    ]
  });

  // New asset input
  const [newAssetSymbol, setNewAssetSymbol] = useState('');
  const [showNewAssetForm, setShowNewAssetForm] = useState(false);

  // Fetch strategies from backend
  const fetchStrategies = useCallback(async () => {
    if (!getAuthHeader) return;
    
    try {
      setLoading(true);
      const response = await axios.get(`${API}/exit-strategy/strategies`, {
        headers: getAuthHeader()
      });
      setStrategies(response.data.strategies || []);
      
      // Select first strategy if available
      if (response.data.strategies?.length > 0 && !selectedAsset) {
        const first = response.data.strategies[0];
        setSelectedAsset(first.asset_symbol);
        setCurrentStrategy(first);
      }
    } catch (err) {
      console.error('Error fetching strategies:', err);
    } finally {
      setLoading(false);
    }
  }, [getAuthHeader, selectedAsset]);

  useEffect(() => {
    fetchStrategies();
  }, [fetchStrategies]);

  // Save strategy to backend
  const saveStrategy = async () => {
    if (!getAuthHeader) return;
    
    setSaving(true);
    setError('');
    setSuccess('');
    
    try {
      const existingStrategy = strategies.find(s => s.asset_symbol === currentStrategy.asset_symbol);
      
      if (existingStrategy) {
        // Update existing
        await axios.put(`${API}/exit-strategy/strategies/${existingStrategy.strategy_id}`, {
          quantity: currentStrategy.quantity,
          average_cost_basis: currentStrategy.average_cost_basis,
          tax_rate: currentStrategy.tax_rate,
          tiers: currentStrategy.tiers
        }, {
          headers: getAuthHeader()
        });
        setSuccess('Strategy updated!');
      } else {
        // Create new
        await axios.post(`${API}/exit-strategy/strategies`, {
          asset_symbol: currentStrategy.asset_symbol,
          quantity: currentStrategy.quantity,
          average_cost_basis: currentStrategy.average_cost_basis,
          tax_rate: currentStrategy.tax_rate,
          tiers: currentStrategy.tiers
        }, {
          headers: getAuthHeader()
        });
        setSuccess('Strategy created!');
      }
      
      await fetchStrategies();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save strategy');
      setTimeout(() => setError(''), 5000);
    } finally {
      setSaving(false);
    }
  };

  // Create alerts from strategy
  const createAlerts = async () => {
    if (!getAuthHeader) return;
    
    const existingStrategy = strategies.find(s => s.asset_symbol === currentStrategy.asset_symbol);
    if (!existingStrategy) {
      setError('Please save the strategy first');
      return;
    }
    
    setSaving(true);
    setError('');
    setSuccess('');
    
    try {
      const response = await axios.post(`${API}/exit-strategy/strategies/${existingStrategy.strategy_id}/create-alerts`, {
        strategy_id: existingStrategy.strategy_id,
        notification_method: 'email'
      }, {
        headers: getAuthHeader()
      });
      
      setSuccess(`Created ${response.data.alerts_created} alert(s)!`);
      await fetchStrategies();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create alerts');
      setTimeout(() => setError(''), 5000);
    } finally {
      setSaving(false);
    }
  };

  // Add new asset
  const addNewAsset = () => {
    if (!newAssetSymbol.trim()) return;
    
    const symbol = newAssetSymbol.toUpperCase().trim();
    
    // Check if already exists
    if (strategies.find(s => s.asset_symbol === symbol)) {
      setSelectedAsset(symbol);
      const existing = strategies.find(s => s.asset_symbol === symbol);
      setCurrentStrategy(existing);
      setShowNewAssetForm(false);
      setNewAssetSymbol('');
      return;
    }
    
    // Create new local strategy
    setCurrentStrategy({
      asset_symbol: symbol,
      quantity: 1.0,
      average_cost_basis: 1000,
      tax_rate: 15,
      tiers: [
        { tier_id: crypto.randomUUID(), name: 'Tier 1', sell_percentage: 25, target_price: 5000, alert_created: false },
      ]
    });
    setSelectedAsset(symbol);
    setShowNewAssetForm(false);
    setNewAssetSymbol('');
  };

  // Select asset
  const selectAsset = (symbol) => {
    setSelectedAsset(symbol);
    const strategy = strategies.find(s => s.asset_symbol === symbol);
    if (strategy) {
      setCurrentStrategy(strategy);
    }
  };

  // Add new tier
  const addTier = () => {
    const newTier = {
      tier_id: crypto.randomUUID(),
      name: `Tier ${currentStrategy.tiers.length + 1}`,
      sell_percentage: 10,
      target_price: 50000,
      alert_created: false
    };
    setCurrentStrategy({
      ...currentStrategy,
      tiers: [...currentStrategy.tiers, newTier]
    });
  };

  // Remove tier
  const removeTier = (tierId) => {
    if (currentStrategy.tiers.length > 1) {
      setCurrentStrategy({
        ...currentStrategy,
        tiers: currentStrategy.tiers.filter(t => t.tier_id !== tierId)
      });
    }
  };

  // Update tier
  const updateTier = (tierId, field, value) => {
    setCurrentStrategy({
      ...currentStrategy,
      tiers: currentStrategy.tiers.map(t =>
        t.tier_id === tierId ? { ...t, [field]: parseFloat(value) || 0 } : t
      )
    });
  };

  // Calculate results for each tier
  const calculations = useMemo(() => {
    let remainingQuantity = currentStrategy.quantity;

    return currentStrategy.tiers.map(tier => {
      const tokensToSell = (tier.sell_percentage / 100) * currentStrategy.quantity;
      const actualTokensSold = Math.min(tokensToSell, remainingQuantity);
      remainingQuantity -= actualTokensSold;

      const grossRevenue = actualTokensSold * tier.target_price;
      const costBasisUsed = actualTokensSold * currentStrategy.average_cost_basis;
      const capitalGains = grossRevenue - costBasisUsed;
      const taxOwed = capitalGains > 0 ? capitalGains * (currentStrategy.tax_rate / 100) : 0;
      const netTakeHome = grossRevenue - taxOwed;

      return {
        ...tier,
        tokensSold: actualTokensSold,
        grossRevenue,
        costBasisUsed,
        capitalGains,
        taxOwed,
        netTakeHome
      };
    });
  }, [currentStrategy]);

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

  // Check if any tiers need alerts
  const tiersNeedingAlerts = currentStrategy.tiers.filter(t => !t.alert_created).length;
  const hasExistingStrategy = strategies.find(s => s.asset_symbol === currentStrategy.asset_symbol);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-6 h-6 text-[#00C805] animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
            EXIT STRATEGY <span className="text-[#00C805]">PLANNER</span>
          </h1>
          <p className="text-[#8A8A93] text-sm font-mono">Plan your exit. Create alerts. Know your take-home.</p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={saveStrategy}
            disabled={saving}
            className="flex items-center gap-2 bg-white text-black px-4 py-2 font-semibold hover:bg-gray-200 disabled:opacity-50 transition-colors"
          >
            <Save className="w-4 h-4" />
            {saving ? 'SAVING...' : 'SAVE'}
          </button>
          {hasExistingStrategy && tiersNeedingAlerts > 0 && (
            <button
              onClick={createAlerts}
              disabled={saving}
              className="flex items-center gap-2 bg-[#00C805] text-black px-4 py-2 font-semibold hover:bg-[#00a804] disabled:opacity-50 transition-colors"
            >
              <Bell className="w-4 h-4" />
              CREATE ALERTS ({tiersNeedingAlerts})
            </button>
          )}
        </div>
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 px-4 py-3 text-[#FF3B30] text-sm">
          {error}
        </div>
      )}
      {success && (
        <div className="bg-[#00C805]/10 border border-[#00C805]/30 px-4 py-3 text-[#00C805] text-sm flex items-center gap-2">
          <Check className="w-4 h-4" />
          {success}
        </div>
      )}

      {/* Asset Selector */}
      <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
        <div className="flex items-center gap-2 mb-3">
          <Coins className="w-5 h-5 text-[#00C805]" />
          <h2 className="text-white font-semibold text-sm">SELECT ASSET</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {strategies.map(s => (
            <button
              key={s.asset_symbol}
              onClick={() => selectAsset(s.asset_symbol)}
              className={`px-4 py-2 font-mono text-sm border transition-colors ${
                selectedAsset === s.asset_symbol
                  ? 'bg-[#00C805] text-black border-[#00C805]'
                  : 'border-[#1F1F22] text-[#8A8A93] hover:border-[#00C805] hover:text-white'
              }`}
            >
              {s.asset_symbol}
              {s.tiers?.some(t => t.alert_created) && (
                <Bell className="w-3 h-3 inline ml-1" />
              )}
            </button>
          ))}
          
          {showNewAssetForm ? (
            <div className="flex items-center gap-2">
              <input
                type="text"
                value={newAssetSymbol}
                onChange={(e) => setNewAssetSymbol(e.target.value.toUpperCase())}
                placeholder="SYMBOL"
                className="w-24 bg-[#161618] border border-[#1F1F22] text-white px-3 py-2 font-mono text-sm focus:outline-none focus:ring-1 focus:ring-[#00C805]"
                maxLength={10}
                onKeyDown={(e) => e.key === 'Enter' && addNewAsset()}
              />
              <button
                onClick={addNewAsset}
                className="bg-[#00C805] text-black px-3 py-2 font-semibold hover:bg-[#00a804]"
              >
                ADD
              </button>
              <button
                onClick={() => { setShowNewAssetForm(false); setNewAssetSymbol(''); }}
                className="text-[#8A8A93] hover:text-white px-2"
              >
                ✕
              </button>
            </div>
          ) : (
            <button
              onClick={() => setShowNewAssetForm(true)}
              className="px-4 py-2 font-mono text-sm border border-dashed border-[#1F1F22] text-[#8A8A93] hover:border-[#00C805] hover:text-[#00C805] transition-colors flex items-center gap-1"
            >
              <Plus className="w-4 h-4" />
              NEW ASSET
            </button>
          )}
        </div>
      </div>

      {/* Configuration Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Tax Profile */}
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="flex items-center gap-2 mb-4">
            <Percent className="w-5 h-5 text-[#00C805]" />
            <h2 className="text-white font-semibold">TAX RATE</h2>
          </div>
          <div className="grid grid-cols-3 gap-2">
            {[0, 15, 20, 25, 30, 37].map(rate => (
              <button
                key={rate}
                onClick={() => setCurrentStrategy({ ...currentStrategy, tax_rate: rate })}
                className={`px-3 py-2 text-sm font-mono border transition-colors ${
                  currentStrategy.tax_rate === rate
                    ? 'bg-[#00C805] text-black border-[#00C805]'
                    : 'border-[#1F1F22] text-[#8A8A93] hover:border-[#00C805]'
                }`}
              >
                {rate}%
              </button>
            ))}
          </div>
        </div>

        {/* Asset Details */}
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="flex items-center gap-2 mb-4">
            <DollarSign className="w-5 h-5 text-[#00C805]" />
            <h2 className="text-white font-semibold">{currentStrategy.asset_symbol} HOLDINGS</h2>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-[#8A8A93] text-xs font-mono block mb-2">QUANTITY</label>
              <input
                type="number"
                value={currentStrategy.quantity}
                onChange={(e) => setCurrentStrategy({ ...currentStrategy, quantity: parseFloat(e.target.value) || 0 })}
                className="w-full bg-[#161618] border border-[#1F1F22] text-white px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-[#00C805]"
                step="0.0001"
              />
            </div>
            <div>
              <label className="text-[#8A8A93] text-xs font-mono block mb-2">AVG COST BASIS ($)</label>
              <input
                type="number"
                value={currentStrategy.average_cost_basis}
                onChange={(e) => setCurrentStrategy({ ...currentStrategy, average_cost_basis: parseFloat(e.target.value) || 0 })}
                className="w-full bg-[#161618] border border-[#1F1F22] text-white px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-[#00C805]"
              />
            </div>
          </div>
          <div className="mt-3 bg-[#161618] border border-[#1F1F22] p-3 flex justify-between">
            <span className="text-[#8A8A93] text-sm">TOTAL INVESTED</span>
            <span className="text-white font-mono font-bold">
              {formatCurrency(currentStrategy.quantity * currentStrategy.average_cost_basis)}
            </span>
          </div>
        </div>
      </div>

      {/* Exit Tiers */}
      <div className="bg-[#0C0C0E] border border-[#1F1F22]">
        <div className="flex items-center justify-between p-4 border-b border-[#1F1F22]">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-[#00C805]" />
            <h2 className="text-white font-semibold">EXIT TIERS</h2>
          </div>
          <button
            onClick={addTier}
            className="flex items-center gap-1 bg-[#00C805] text-black px-3 py-1.5 text-sm font-semibold hover:bg-[#00a804]"
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
                <th className="text-left px-4 py-3 text-[#8A8A93] text-xs font-mono">TIER</th>
                <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono">SELL %</th>
                <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono">TARGET PRICE</th>
                <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono">{currentStrategy.asset_symbol} SOLD</th>
                <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono">GROSS</th>
                <th className="text-right px-4 py-3 text-[#8A8A93] text-xs font-mono">TAX</th>
                <th className="text-right px-4 py-3 text-[#00C805] text-xs font-mono">NET</th>
                <th className="text-center px-4 py-3 text-[#8A8A93] text-xs font-mono">ALERT</th>
                <th className="px-4 py-3"></th>
              </tr>
            </thead>
            <tbody>
              {calculations.map((tier) => (
                <tr key={tier.tier_id} className="border-b border-[#1F1F22] hover:bg-[#161618]">
                  <td className="px-4 py-3 text-white font-mono">{tier.name}</td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      value={tier.sell_percentage}
                      onChange={(e) => updateTier(tier.tier_id, 'sell_percentage', e.target.value)}
                      className="w-20 bg-[#161618] border border-[#1F1F22] text-white px-2 py-1 text-right font-mono text-sm"
                      min="0" max="100"
                    />
                  </td>
                  <td className="px-4 py-3">
                    <input
                      type="number"
                      value={tier.target_price}
                      onChange={(e) => updateTier(tier.tier_id, 'target_price', e.target.value)}
                      className="w-28 bg-[#161618] border border-[#1F1F22] text-white px-2 py-1 text-right font-mono text-sm"
                      min="0"
                    />
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-[#8A8A93]">{formatNumber(tier.tokensSold)}</td>
                  <td className="px-4 py-3 text-right font-mono text-white">{formatCurrency(tier.grossRevenue)}</td>
                  <td className="px-4 py-3 text-right font-mono text-[#FF3B30]">-{formatCurrency(tier.taxOwed)}</td>
                  <td className="px-4 py-3 text-right font-mono text-[#00C805] font-bold">{formatCurrency(tier.netTakeHome)}</td>
                  <td className="px-4 py-3 text-center">
                    {tier.alert_created ? (
                      <span className="text-[#00C805]"><Bell className="w-4 h-4 inline" /></span>
                    ) : (
                      <span className="text-[#8A8A93]">—</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => removeTier(tier.tier_id)}
                      className="p-1 text-[#8A8A93] hover:text-[#FF3B30]"
                      disabled={currentStrategy.tiers.length <= 1}
                    >
                      <Trash className="w-4 h-4" />
                    </button>
                  </td>
                </tr>
              ))}
              {/* Totals */}
              <tr className="bg-[#161618] font-bold">
                <td className="px-4 py-3 text-white font-mono">TOTAL</td>
                <td className="px-4 py-3 text-right font-mono text-[#8A8A93]">
                  {currentStrategy.tiers.reduce((sum, t) => sum + t.sell_percentage, 0)}%
                </td>
                <td className="px-4 py-3"></td>
                <td className="px-4 py-3 text-right font-mono text-[#8A8A93]">{formatNumber(totals.tokensSold)}</td>
                <td className="px-4 py-3 text-right font-mono text-white">{formatCurrency(totals.grossRevenue)}</td>
                <td className="px-4 py-3 text-right font-mono text-[#FF3B30]">-{formatCurrency(totals.taxOwed)}</td>
                <td className="px-4 py-3 text-right font-mono text-[#00C805]">{formatCurrency(totals.netTakeHome)}</td>
                <td colSpan="2"></td>
              </tr>
            </tbody>
          </table>
        </div>

        {/* Mobile Cards */}
        <div className="md:hidden p-4 space-y-4">
          {calculations.map((tier) => (
            <div key={tier.tier_id} className="bg-[#161618] border border-[#1F1F22] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-white font-mono font-bold">{tier.name}</span>
                <div className="flex items-center gap-2">
                  {tier.alert_created && <Bell className="w-4 h-4 text-[#00C805]" />}
                  <button onClick={() => removeTier(tier.tier_id)} className="text-[#8A8A93] hover:text-[#FF3B30]">
                    <Trash className="w-4 h-4" />
                  </button>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-[#8A8A93] text-xs block mb-1">SELL %</label>
                  <input
                    type="number"
                    value={tier.sell_percentage}
                    onChange={(e) => updateTier(tier.tier_id, 'sell_percentage', e.target.value)}
                    className="w-full bg-[#0C0C0E] border border-[#1F1F22] text-white px-2 py-1.5 font-mono text-sm"
                  />
                </div>
                <div>
                  <label className="text-[#8A8A93] text-xs block mb-1">TARGET ($)</label>
                  <input
                    type="number"
                    value={tier.target_price}
                    onChange={(e) => updateTier(tier.tier_id, 'target_price', e.target.value)}
                    className="w-full bg-[#0C0C0E] border border-[#1F1F22] text-white px-2 py-1.5 font-mono text-sm"
                  />
                </div>
              </div>
              <div className="pt-2 border-t border-[#1F1F22] space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-[#8A8A93]">Gross</span>
                  <span className="text-white font-mono">{formatCurrency(tier.grossRevenue)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-[#8A8A93]">Tax</span>
                  <span className="text-[#FF3B30] font-mono">-{formatCurrency(tier.taxOwed)}</span>
                </div>
                <div className="flex justify-between font-bold">
                  <span className="text-[#8A8A93]">Net</span>
                  <span className="text-[#00C805] font-mono">{formatCurrency(tier.netTakeHome)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Chart */}
      <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
        <div className="flex items-center gap-2 mb-4">
          <Calculator className="w-5 h-5 text-[#00C805]" />
          <h2 className="text-white font-semibold">REVENUE BY TIER</h2>
        </div>
        <div className="h-64 sm:h-80">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#1F1F22" />
              <XAxis dataKey="name" stroke="#8A8A93" tick={{ fill: '#8A8A93', fontSize: 12 }} />
              <YAxis stroke="#8A8A93" tick={{ fill: '#8A8A93', fontSize: 12 }} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
              <Tooltip
                contentStyle={{ backgroundColor: '#0C0C0E', border: '1px solid #1F1F22' }}
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

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="text-[#8A8A93] text-xs font-mono mb-1">INVESTED</div>
          <div className="text-white text-lg sm:text-xl font-mono font-bold">
            {formatCurrency(currentStrategy.quantity * currentStrategy.average_cost_basis)}
          </div>
        </div>
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="text-[#8A8A93] text-xs font-mono mb-1">GROSS REVENUE</div>
          <div className="text-white text-lg sm:text-xl font-mono font-bold">{formatCurrency(totals.grossRevenue)}</div>
        </div>
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="text-[#8A8A93] text-xs font-mono mb-1">TOTAL TAX</div>
          <div className="text-[#FF3B30] text-lg sm:text-xl font-mono font-bold">-{formatCurrency(totals.taxOwed)}</div>
        </div>
        <div className="bg-[#00C805]/10 border border-[#00C805]/30 p-4">
          <div className="text-[#00C805] text-xs font-mono mb-1">NET TAKE-HOME</div>
          <div className="text-[#00C805] text-lg sm:text-xl font-mono font-bold">{formatCurrency(totals.netTakeHome)}</div>
        </div>
      </div>
    </div>
  );
};

export default ExitStrategyDashboard;
