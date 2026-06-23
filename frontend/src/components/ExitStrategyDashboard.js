import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { Plus, Trash, Calculator, TrendingUp, TrendingDown, DollarSign, Percent, Coins, Bell, Check, Save, RefreshCw } from 'lucide-react';
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const ExitStrategyDashboard = ({ getAuthHeader }) => {
  const [strategies, setStrategies] = useState([]);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [currentStrategy, setCurrentStrategy] = useState({
    asset_symbol: 'BTC',
    quantity: 1.0,
    average_cost_basis: 30000,
    tax_rate: 15,
    tiers: []
  });

  const [newAssetSymbol, setNewAssetSymbol] = useState('');
  const [showNewAssetForm, setShowNewAssetForm] = useState(false);

  const fetchStrategies = useCallback(async (preserveSelection = false) => {
    if (!getAuthHeader) return;
    try {
      setLoading(true);
      const response = await axios.get(`${API}/exit-strategy/strategies`, { headers: getAuthHeader() });
      const newStrategies = response.data.strategies || [];
      setStrategies(newStrategies);
      
      // Only auto-select first item if no selection exists and not preserving
      if (newStrategies.length > 0 && !preserveSelection) {
        setSelectedAsset(prev => {
          // If there's already a selection, keep it if the strategy still exists
          if (prev) {
            const existingStrategy = newStrategies.find(s => s.asset_symbol === prev);
            if (existingStrategy) {
              setCurrentStrategy(existingStrategy);
              return prev;
            }
          }
          // Otherwise select the first one
          const first = newStrategies[0];
          setCurrentStrategy(first);
          return first.asset_symbol;
        });
      } else if (preserveSelection && newStrategies.length > 0) {
        // Update currentStrategy with fresh data from server
        setSelectedAsset(prev => {
          if (prev) {
            const updatedStrategy = newStrategies.find(s => s.asset_symbol === prev);
            if (updatedStrategy) {
              setCurrentStrategy(updatedStrategy);
            }
          }
          return prev;
        });
      }
    } catch (err) {
      console.error('Error fetching strategies:', err);
    } finally {
      setLoading(false);
    }
  }, [getAuthHeader]);

  useEffect(() => { fetchStrategies(); }, [fetchStrategies]);

  const saveStrategy = async () => {
    if (!getAuthHeader) return;
    setSaving(true);
    setError('');
    setSuccess('');
    
    try {
      const existingStrategy = strategies.find(s => s.asset_symbol === currentStrategy.asset_symbol);
      
      if (existingStrategy) {
        const response = await axios.put(`${API}/exit-strategy/strategies/${existingStrategy.strategy_id}`, {
          quantity: currentStrategy.quantity,
          average_cost_basis: currentStrategy.average_cost_basis,
          tax_rate: currentStrategy.tax_rate,
          tiers: currentStrategy.tiers
        }, { headers: getAuthHeader() });
        setSuccess(`Strategy updated! ${response.data.alerts_created || 0} alerts created.`);
      } else {
        const response = await axios.post(`${API}/exit-strategy/strategies`, {
          asset_symbol: currentStrategy.asset_symbol,
          quantity: currentStrategy.quantity,
          average_cost_basis: currentStrategy.average_cost_basis,
          tax_rate: currentStrategy.tax_rate,
          tiers: currentStrategy.tiers
        }, { headers: getAuthHeader() });
        setSuccess(`Strategy created with ${response.data.alerts_created || 0} alerts!`);
      }
      
      // Preserve the current asset selection when refetching
      await fetchStrategies(true);
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save strategy');
      setTimeout(() => setError(''), 5000);
    } finally {
      setSaving(false);
    }
  };

  const addNewAsset = () => {
    if (!newAssetSymbol.trim()) return;
    const symbol = newAssetSymbol.toUpperCase().trim();
    
    if (strategies.find(s => s.asset_symbol === symbol)) {
      setSelectedAsset(symbol);
      setCurrentStrategy(strategies.find(s => s.asset_symbol === symbol));
    } else {
      setCurrentStrategy({
        asset_symbol: symbol,
        quantity: 1.0,
        average_cost_basis: 1000,
        tax_rate: 15,
        tiers: []
      });
      setSelectedAsset(symbol);
    }
    setShowNewAssetForm(false);
    setNewAssetSymbol('');
  };

  const selectAsset = (symbol) => {
    setSelectedAsset(symbol);
    const strategy = strategies.find(s => s.asset_symbol === symbol);
    if (strategy) setCurrentStrategy(strategy);
  };

  const addTier = (tierType) => {
    const typeCount = currentStrategy.tiers.filter(t => t.tier_type === tierType).length;
    const newTier = {
      tier_id: crypto.randomUUID(),
      name: `${tierType === 'entry' ? 'Entry' : 'Exit'} ${typeCount + 1}`,
      tier_type: tierType,
      sell_percentage: 25,
      target_price: tierType === 'entry' ? currentStrategy.average_cost_basis * 0.8 : currentStrategy.average_cost_basis * 2,
      alert_created: false
    };
    setCurrentStrategy({ ...currentStrategy, tiers: [...currentStrategy.tiers, newTier] });
  };

  const removeTier = (tierId) => {
    setCurrentStrategy({
      ...currentStrategy,
      tiers: currentStrategy.tiers.filter(t => t.tier_id !== tierId)
    });
  };

  const updateTier = (tierId, field, value) => {
    setCurrentStrategy({
      ...currentStrategy,
      tiers: currentStrategy.tiers.map(t =>
        t.tier_id === tierId ? { ...t, [field]: field === 'name' ? value : (parseFloat(value) || 0) } : t
      )
    });
  };

  // Separate entry and exit tiers
  const entryTiers = currentStrategy.tiers.filter(t => t.tier_type === 'entry');
  const exitTiers = currentStrategy.tiers.filter(t => t.tier_type === 'exit');

  // Calculate exit tier results
  const exitCalculations = useMemo(() => {
    let remainingQuantity = currentStrategy.quantity;
    return exitTiers.map(tier => {
      const tokensToSell = (tier.sell_percentage / 100) * currentStrategy.quantity;
      const actualTokensSold = Math.min(tokensToSell, remainingQuantity);
      remainingQuantity -= actualTokensSold;
      const grossRevenue = actualTokensSold * tier.target_price;
      const costBasisUsed = actualTokensSold * currentStrategy.average_cost_basis;
      const capitalGains = grossRevenue - costBasisUsed;
      const taxOwed = capitalGains > 0 ? capitalGains * (currentStrategy.tax_rate / 100) : 0;
      const netTakeHome = grossRevenue - taxOwed;
      return { ...tier, tokensSold: actualTokensSold, grossRevenue, costBasisUsed, capitalGains, taxOwed, netTakeHome };
    });
  }, [exitTiers, currentStrategy.quantity, currentStrategy.average_cost_basis, currentStrategy.tax_rate]);

  const exitTotals = useMemo(() => {
    return exitCalculations.reduce((acc, tier) => ({
      tokensSold: acc.tokensSold + tier.tokensSold,
      grossRevenue: acc.grossRevenue + tier.grossRevenue,
      taxOwed: acc.taxOwed + tier.taxOwed,
      netTakeHome: acc.netTakeHome + tier.netTakeHome
    }), { tokensSold: 0, grossRevenue: 0, taxOwed: 0, netTakeHome: 0 });
  }, [exitCalculations]);

  const chartData = exitCalculations.map(tier => ({
    name: tier.name,
    'Gross Revenue': Math.round(tier.grossRevenue),
    'Net Take-Home': Math.round(tier.netTakeHome),
    'Tax Owed': Math.round(tier.taxOwed)
  }));

  const formatCurrency = (value) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(value);
  const formatNumber = (value, decimals = 4) => new Intl.NumberFormat('en-US', { maximumFractionDigits: decimals }).format(value);

  if (loading) {
    return <div className="flex items-center justify-center h-64"><RefreshCw className="w-6 h-6 text-[#00C805] animate-spin" /></div>;
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold tracking-tight text-white">
            ENTRY & EXIT <span className="text-[#00C805]">STRATEGY</span>
          </h1>
          <p className="text-[#8A8A93] text-sm font-mono">Set targets. Alerts auto-created on save.</p>
        </div>
        <button
          onClick={saveStrategy}
          disabled={saving || currentStrategy.tiers.length === 0}
          className="flex items-center gap-2 bg-[#00C805] text-black px-6 py-2.5 font-semibold hover:bg-[#00a804] disabled:opacity-50 disabled:bg-[#1F1F22] disabled:text-[#8A8A93] transition-colors"
        >
          {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
          {saving ? 'SAVING...' : 'SAVE & CREATE ALERTS'}
        </button>
      </div>

      {/* Messages */}
      {error && <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 px-4 py-3 text-[#FF3B30] text-sm">{error}</div>}
      {success && <div className="bg-[#00C805]/10 border border-[#00C805]/30 px-4 py-3 text-[#00C805] text-sm flex items-center gap-2"><Check className="w-4 h-4" />{success}</div>}

      {/* Asset Selector */}
      <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
        <div className="flex items-center gap-2 mb-3">
          <Coins className="w-5 h-5 text-[#00C805]" />
          <h2 className="text-white font-semibold text-sm">SELECT ASSET</h2>
        </div>
        <div className="flex flex-wrap gap-2">
          {/* Show saved strategies */}
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
              {s.tiers?.length > 0 && <Bell className="w-3 h-3 inline ml-1" />}
            </button>
          ))}
          
          {/* Show current unsaved asset if it's not in saved strategies */}
          {selectedAsset && !strategies.find(s => s.asset_symbol === selectedAsset) && (
            <button
              className="px-4 py-2 font-mono text-sm border bg-[#00C805] text-black border-[#00C805]"
            >
              {selectedAsset}
              <span className="text-[10px] ml-1 opacity-70">(unsaved)</span>
            </button>
          )}
          
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
              <button onClick={addNewAsset} className="bg-[#00C805] text-black px-3 py-2 font-semibold">ADD</button>
              <button onClick={() => { setShowNewAssetForm(false); setNewAssetSymbol(''); }} className="text-[#8A8A93] hover:text-white px-2">✕</button>
            </div>
          ) : (
            <button
              onClick={() => setShowNewAssetForm(true)}
              className="px-4 py-2 font-mono text-sm border border-dashed border-[#1F1F22] text-[#8A8A93] hover:border-[#00C805] hover:text-[#00C805] flex items-center gap-1"
            >
              <Plus className="w-4 h-4" /> NEW ASSET
            </button>
          )}
        </div>
      </div>

      {/* Config Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Tax Rate */}
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
                  currentStrategy.tax_rate === rate ? 'bg-[#00C805] text-black border-[#00C805]' : 'border-[#1F1F22] text-[#8A8A93] hover:border-[#00C805]'
                }`}
              >
                {rate}%
              </button>
            ))}
          </div>
        </div>

        {/* Holdings */}
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
                step="any"
              />
            </div>
            <div>
              <label className="text-[#8A8A93] text-xs font-mono block mb-2">AVG COST BASIS ($)</label>
              <input
                type="number"
                value={currentStrategy.average_cost_basis}
                onChange={(e) => setCurrentStrategy({ ...currentStrategy, average_cost_basis: parseFloat(e.target.value) || 0 })}
                className="w-full bg-[#161618] border border-[#1F1F22] text-white px-3 py-2 font-mono focus:outline-none focus:ring-1 focus:ring-[#00C805]"
                step="any"
              />
            </div>
          </div>
          <div className="mt-3 bg-[#161618] border border-[#1F1F22] p-3 flex justify-between">
            <span className="text-[#8A8A93] text-sm">TOTAL INVESTED</span>
            <span className="text-white font-mono font-bold">{formatCurrency(currentStrategy.quantity * currentStrategy.average_cost_basis)}</span>
          </div>
        </div>
      </div>

      {/* Entry Tiers */}
      <div className="bg-[#0C0C0E] border border-[#1F1F22]">
        <div className="flex items-center justify-between p-4 border-b border-[#1F1F22]">
          <div className="flex items-center gap-2">
            <TrendingDown className="w-5 h-5 text-[#3B82F6]" />
            <h2 className="text-white font-semibold">ENTRY TARGETS</h2>
            <span className="text-[#8A8A93] text-xs font-mono">(Buy when price drops)</span>
          </div>
          <button onClick={() => addTier('entry')} className="flex items-center gap-1 bg-[#3B82F6] text-white px-3 py-1.5 text-sm font-semibold hover:bg-[#2563EB]">
            <Plus className="w-4 h-4" /> ADD ENTRY
          </button>
        </div>
        
        {entryTiers.length === 0 ? (
          <div className="p-8 text-center text-[#8A8A93]">
            <TrendingDown className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No entry targets set. Add targets to get alerts when price drops.</p>
          </div>
        ) : (
          <div className="p-4 space-y-3">
            {entryTiers.map((tier, index) => (
              <div key={tier.tier_id} className="bg-[#161618] border border-[#1F1F22] p-4 flex flex-wrap items-center gap-4">
                <div className="bg-[#3B82F6]/20 border border-[#3B82F6]/40 px-3 py-1.5 text-[#3B82F6] font-mono text-sm font-semibold">
                  ENTRY {index + 1}
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-[#8A8A93] text-xs">ALERT WHEN</span>
                  <span className="text-white font-mono">{currentStrategy.asset_symbol}</span>
                  <span className="text-[#8A8A93] text-xs">DROPS TO</span>
                  <span className="text-[#8A8A93]">$</span>
                  <input
                    type="number"
                    value={tier.target_price}
                    onChange={(e) => updateTier(tier.tier_id, 'target_price', e.target.value)}
                    className="w-28 bg-[#0C0C0E] border border-[#1F1F22] text-white px-2 py-1.5 font-mono text-sm text-right"
                    step="any"
                  />
                </div>
                {tier.alert_created && <Bell className="w-4 h-4 text-[#3B82F6]" />}
                <button onClick={() => removeTier(tier.tier_id)} className="ml-auto text-[#8A8A93] hover:text-[#FF3B30]">
                  <Trash className="w-4 h-4" />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Exit Tiers */}
      <div className="bg-[#0C0C0E] border border-[#1F1F22]">
        <div className="flex items-center justify-between p-4 border-b border-[#1F1F22]">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-[#00C805]" />
            <h2 className="text-white font-semibold">EXIT TARGETS</h2>
            <span className="text-[#8A8A93] text-xs font-mono">(Sell when price rises)</span>
          </div>
          <button onClick={() => addTier('exit')} className="flex items-center gap-1 bg-[#00C805] text-black px-3 py-1.5 text-sm font-semibold hover:bg-[#00a804]">
            <Plus className="w-4 h-4" /> ADD EXIT
          </button>
        </div>

        {exitTiers.length === 0 ? (
          <div className="p-8 text-center text-[#8A8A93]">
            <TrendingUp className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p className="text-sm">No exit targets set. Add targets to get alerts when price rises.</p>
          </div>
        ) : (
          <>
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
                  {exitCalculations.map((tier, index) => (
                    <tr key={tier.tier_id} className="border-b border-[#1F1F22] hover:bg-[#161618]">
                      <td className="px-4 py-3">
                        <span className="bg-[#00C805]/20 border border-[#00C805]/40 px-2 py-1 text-[#00C805] font-mono text-sm font-semibold">
                          EXIT {index + 1}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <input type="number" value={tier.sell_percentage} onChange={(e) => updateTier(tier.tier_id, 'sell_percentage', e.target.value)}
                          className="w-20 bg-[#161618] border border-[#1F1F22] text-white px-2 py-1 text-right font-mono text-sm" min="0" max="100" step="any" />
                      </td>
                      <td className="px-4 py-3">
                        <input type="number" value={tier.target_price} onChange={(e) => updateTier(tier.tier_id, 'target_price', e.target.value)}
                          className="w-28 bg-[#161618] border border-[#1F1F22] text-white px-2 py-1 text-right font-mono text-sm" min="0" step="any" />
                      </td>
                      <td className="px-4 py-3 text-right font-mono text-[#8A8A93]">{formatNumber(tier.tokensSold)}</td>
                      <td className="px-4 py-3 text-right font-mono text-white">{formatCurrency(tier.grossRevenue)}</td>
                      <td className="px-4 py-3 text-right font-mono text-[#FF3B30]">-{formatCurrency(tier.taxOwed)}</td>
                      <td className="px-4 py-3 text-right font-mono text-[#00C805] font-bold">{formatCurrency(tier.netTakeHome)}</td>
                      <td className="px-4 py-3 text-center">{tier.alert_created ? <Bell className="w-4 h-4 inline text-[#00C805]" /> : <span className="text-[#8A8A93]">—</span>}</td>
                      <td className="px-4 py-3"><button onClick={() => removeTier(tier.tier_id)} className="p-1 text-[#8A8A93] hover:text-[#FF3B30]"><Trash className="w-4 h-4" /></button></td>
                    </tr>
                  ))}
                  <tr className="bg-[#161618] font-bold">
                    <td className="px-4 py-3 text-white font-mono">TOTAL</td>
                    <td className="px-4 py-3 text-right font-mono text-[#8A8A93]">{exitTiers.reduce((sum, t) => sum + t.sell_percentage, 0)}%</td>
                    <td className="px-4 py-3"></td>
                    <td className="px-4 py-3 text-right font-mono text-[#8A8A93]">{formatNumber(exitTotals.tokensSold)}</td>
                    <td className="px-4 py-3 text-right font-mono text-white">{formatCurrency(exitTotals.grossRevenue)}</td>
                    <td className="px-4 py-3 text-right font-mono text-[#FF3B30]">-{formatCurrency(exitTotals.taxOwed)}</td>
                    <td className="px-4 py-3 text-right font-mono text-[#00C805]">{formatCurrency(exitTotals.netTakeHome)}</td>
                    <td colSpan="2"></td>
                  </tr>
                </tbody>
              </table>
            </div>

            {/* Mobile Cards */}
            <div className="md:hidden p-4 space-y-3">
              {exitCalculations.map((tier, index) => (
                <div key={tier.tier_id} className="bg-[#161618] border border-[#1F1F22] p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="bg-[#00C805]/20 border border-[#00C805]/40 px-2 py-1 text-[#00C805] font-mono text-sm font-semibold">
                      EXIT {index + 1}
                    </span>
                    <div className="flex items-center gap-2">
                      {tier.alert_created && <Bell className="w-4 h-4 text-[#00C805]" />}
                      <button onClick={() => removeTier(tier.tier_id)} className="text-[#8A8A93] hover:text-[#FF3B30]"><Trash className="w-4 h-4" /></button>
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-[#8A8A93] text-xs block mb-1">SELL %</label>
                      <input type="number" value={tier.sell_percentage} onChange={(e) => updateTier(tier.tier_id, 'sell_percentage', e.target.value)}
                        className="w-full bg-[#0C0C0E] border border-[#1F1F22] text-white px-2 py-1.5 font-mono text-sm" step="any" />
                    </div>
                    <div>
                      <label className="text-[#8A8A93] text-xs block mb-1">TARGET ($)</label>
                      <input type="number" value={tier.target_price} onChange={(e) => updateTier(tier.tier_id, 'target_price', e.target.value)}
                        className="w-full bg-[#0C0C0E] border border-[#1F1F22] text-white px-2 py-1.5 font-mono text-sm" step="any" />
                    </div>
                  </div>
                  <div className="pt-2 border-t border-[#1F1F22] space-y-1 text-sm">
                    <div className="flex justify-between"><span className="text-[#8A8A93]">Gross</span><span className="text-white font-mono">{formatCurrency(tier.grossRevenue)}</span></div>
                    <div className="flex justify-between"><span className="text-[#8A8A93]">Tax</span><span className="text-[#FF3B30] font-mono">-{formatCurrency(tier.taxOwed)}</span></div>
                    <div className="flex justify-between font-bold"><span className="text-[#8A8A93]">Net</span><span className="text-[#00C805] font-mono">{formatCurrency(tier.netTakeHome)}</span></div>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Chart */}
      {exitCalculations.length > 0 && (
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="flex items-center gap-2 mb-4">
            <Calculator className="w-5 h-5 text-[#00C805]" />
            <h2 className="text-white font-semibold">EXIT REVENUE BY TIER</h2>
          </div>
          <div className="h-64 sm:h-80">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1F1F22" />
                <XAxis dataKey="name" stroke="#8A8A93" tick={{ fill: '#8A8A93', fontSize: 12 }} />
                <YAxis stroke="#8A8A93" tick={{ fill: '#8A8A93', fontSize: 12 }} tickFormatter={(v) => `$${(v/1000).toFixed(0)}k`} />
                <Tooltip contentStyle={{ backgroundColor: '#0C0C0E', border: '1px solid #1F1F22' }} labelStyle={{ color: '#fff' }} formatter={(value) => [formatCurrency(value), '']} />
                <Legend />
                <Bar dataKey="Gross Revenue" fill="#8A8A93" />
                <Bar dataKey="Net Take-Home" fill="#00C805" />
                <Bar dataKey="Tax Owed" fill="#FF3B30" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="text-[#8A8A93] text-xs font-mono mb-1">INVESTED</div>
          <div className="text-white text-lg sm:text-xl font-mono font-bold">{formatCurrency(currentStrategy.quantity * currentStrategy.average_cost_basis)}</div>
        </div>
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="text-[#8A8A93] text-xs font-mono mb-1">GROSS REVENUE</div>
          <div className="text-white text-lg sm:text-xl font-mono font-bold">{formatCurrency(exitTotals.grossRevenue)}</div>
        </div>
        <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
          <div className="text-[#8A8A93] text-xs font-mono mb-1">TOTAL TAX</div>
          <div className="text-[#FF3B30] text-lg sm:text-xl font-mono font-bold">-{formatCurrency(exitTotals.taxOwed)}</div>
        </div>
        <div className="bg-[#00C805]/10 border border-[#00C805]/30 p-4">
          <div className="text-[#00C805] text-xs font-mono mb-1">NET TAKE-HOME</div>
          <div className="text-[#00C805] text-lg sm:text-xl font-mono font-bold">{formatCurrency(exitTotals.netTakeHome)}</div>
        </div>
      </div>
    </div>
  );
};

export default ExitStrategyDashboard;
