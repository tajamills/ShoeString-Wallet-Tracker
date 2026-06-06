import React, { useState, useEffect, useCallback } from 'react';
import { 
  Bell, 
  FileText, 
  LogOut, 
  HelpCircle,
  Plus,
  Trash2,
  Pause,
  Play,
  TrendingUp,
  TrendingDown,
  ArrowUp,
  ArrowDown,
  Loader2,
  AlertCircle,
  CheckCircle,
  Clock,
  MessageCircle,
  ExternalLink,
  Zap,
  BarChart3,
  X,
  Search,
  DollarSign,
  Percent
} from 'lucide-react';
import { Input } from '@/components/ui/input';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Crypto icons as simple colored circles with letters
const CryptoIcon = ({ symbol }) => {
  const colors = {
    BTC: 'bg-orange-500',
    ETH: 'bg-purple-500',
    SOL: 'bg-gradient-to-br from-purple-500 to-teal-400',
    XRP: 'bg-gray-600',
    DOGE: 'bg-yellow-500',
    ADA: 'bg-blue-500',
    DOT: 'bg-pink-500',
    LINK: 'bg-blue-600',
    AVAX: 'bg-red-500',
    MATIC: 'bg-purple-600'
  };
  
  return (
    <div className={`w-10 h-10 rounded-full ${colors[symbol] || 'bg-gray-600'} flex items-center justify-center text-white font-bold text-sm`}>
      {symbol.slice(0, 1)}
    </div>
  );
};

const formatPrice = (price) => {
  if (!price) return '$0.00';
  if (price >= 1000) return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (price >= 1) return `$${price.toFixed(2)}`;
  if (price >= 0.01) return `$${price.toFixed(4)}`;
  return `$${price.toFixed(8)}`;
};

const ALERT_TYPE_LABELS = {
  price_above: { label: 'Price Above', icon: ArrowUp },
  price_below: { label: 'Price Below', icon: ArrowDown },
  percent_change_up: { label: '% Change Up', icon: TrendingUp },
  percent_change_down: { label: '% Change Down', icon: TrendingDown }
};

// Create Alert Modal
const CreateAlertModal = ({ isOpen, onClose, onCreated, getAuthHeader }) => {
  const [step, setStep] = useState(1);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [selectedAsset, setSelectedAsset] = useState(null);
  const [currentPrice, setCurrentPrice] = useState(null);
  const [alertType, setAlertType] = useState('price_above');
  const [targetValue, setTargetValue] = useState('');
  const [notificationMethod, setNotificationMethod] = useState('telegram');
  const [phoneNumber, setPhoneNumber] = useState('');
  const [note, setNote] = useState('');
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState('');

  const searchAssets = useCallback(async (query) => {
    if (!query || query.length < 1) {
      setSearchResults([]);
      return;
    }
    setSearching(true);
    try {
      const response = await axios.get(`${API}/alerts/search`, {
        params: { q: query },
        headers: getAuthHeader()
      });
      setSearchResults(response.data.results || []);
    } catch (err) {
      console.error('Search error:', err);
    } finally {
      setSearching(false);
    }
  }, [getAuthHeader]);

  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery) searchAssets(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, searchAssets]);

  useEffect(() => {
    if (selectedAsset) {
      fetchPrice();
    }
  }, [selectedAsset]);

  const fetchPrice = async () => {
    if (!selectedAsset) return;
    try {
      const response = await axios.get(
        `${API}/alerts/price/${selectedAsset.type}/${selectedAsset.symbol}`,
        { headers: getAuthHeader() }
      );
      setCurrentPrice(response.data);
    } catch (err) {
      console.error('Price fetch error:', err);
    }
  };

  const handleSelectAsset = (asset) => {
    setSelectedAsset(asset);
    setStep(2);
    setSearchQuery('');
    setSearchResults([]);
  };

  const handleCreate = async () => {
    if (!selectedAsset || !targetValue) {
      setError('Please fill in all required fields');
      return;
    }
    if (notificationMethod === 'sms' && !phoneNumber) {
      setError('Phone number is required for SMS notifications');
      return;
    }
    setCreating(true);
    setError('');
    try {
      const response = await axios.post(`${API}/alerts`, {
        asset_symbol: selectedAsset.symbol,
        asset_type: selectedAsset.type,
        alert_type: alertType,
        target_value: parseFloat(targetValue),
        notification_method: notificationMethod,
        phone_number: phoneNumber || null,
        note: note || null
      }, { headers: getAuthHeader() });
      onCreated(response.data);
      handleClose();
    } catch (err) {
      const detail = err.response?.data?.detail;
      if (typeof detail === 'object') {
        setError(detail.message || 'Failed to create alert');
      } else {
        setError(detail || 'Failed to create alert');
      }
    } finally {
      setCreating(false);
    }
  };

  const handleClose = () => {
    setStep(1);
    setSearchQuery('');
    setSearchResults([]);
    setSelectedAsset(null);
    setCurrentPrice(null);
    setAlertType('price_above');
    setTargetValue('');
    setNotificationMethod('telegram');
    setPhoneNumber('');
    setNote('');
    setError('');
    onClose();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
      <div className="bg-[#1a1a2e] border border-purple-500/20 rounded-xl w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-white/10">
          <h2 className="text-white font-semibold">
            {step === 1 ? 'Search Asset' : 'Configure Alert'}
          </h2>
          <button onClick={handleClose} className="text-white/40 hover:text-white">
            <X className="w-5 h-5" />
          </button>
        </div>
        
        <div className="p-4 space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 text-red-400 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}

          {step === 1 && (
            <>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search BTC, ETH, SOL..."
                  className="pl-10 bg-white/5 border-white/10 text-white placeholder:text-white/30"
                  autoFocus
                />
                {searching && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-purple-400" />}
              </div>

              <div className="space-y-2 max-h-64 overflow-y-auto">
                {searchResults.map((result) => (
                  <div
                    key={`${result.type}-${result.symbol}`}
                    onClick={() => handleSelectAsset(result)}
                    className="flex items-center justify-between p-3 bg-white/5 rounded-lg cursor-pointer hover:bg-purple-500/10 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <CryptoIcon symbol={result.symbol} />
                      <div>
                        <span className="text-white font-medium">{result.symbol}</span>
                        <p className="text-xs text-white/40">{result.name}</p>
                      </div>
                    </div>
                    <ArrowUp className="w-4 h-4 text-white/20" />
                  </div>
                ))}
                
                {searchQuery && !searching && searchResults.length === 0 && (
                  <p className="text-center text-white/40 py-4">No results found</p>
                )}
                
                {!searchQuery && (
                  <div className="text-center text-white/40 py-8">
                    <Search className="w-10 h-10 mx-auto mb-2 opacity-30" />
                    <p className="text-sm">Search for a crypto symbol</p>
                  </div>
                )}
              </div>
            </>
          )}

          {step === 2 && selectedAsset && (
            <>
              <div className="flex items-center gap-3 p-3 bg-white/5 rounded-lg">
                <CryptoIcon symbol={selectedAsset.symbol} />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium">{selectedAsset.symbol}</span>
                    <span className="text-[10px] bg-purple-500/30 text-purple-300 px-1.5 py-0.5 rounded">CRYPTO</span>
                  </div>
                  <p className="text-xs text-white/40">{selectedAsset.name}</p>
                </div>
                <div className="text-right">
                  <p className="text-white font-medium">
                    {currentPrice ? formatPrice(currentPrice.price) : '...'}
                  </p>
                </div>
              </div>

              <div>
                <label className="text-sm text-white/60 mb-2 block">Alert Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(ALERT_TYPE_LABELS).map(([key, { label, icon: Icon }]) => (
                    <button
                      key={key}
                      onClick={() => setAlertType(key)}
                      className={`flex items-center gap-2 p-3 rounded-lg border transition-colors text-sm ${
                        alertType === key 
                          ? 'bg-purple-500/20 border-purple-500 text-white' 
                          : 'bg-white/5 border-white/10 text-white/60 hover:border-white/20'
                      }`}
                    >
                      <Icon className="w-4 h-4" />
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-sm text-white/60 mb-2 block">
                  {alertType.includes('percent') ? 'Percentage' : 'Target Price'}
                </label>
                <div className="relative">
                  {alertType.includes('percent') ? (
                    <Percent className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  ) : (
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-white/40" />
                  )}
                  <Input
                    type="number"
                    value={targetValue}
                    onChange={(e) => setTargetValue(e.target.value)}
                    placeholder={alertType.includes('percent') ? '5' : '0.00'}
                    className="pl-10 bg-white/5 border-white/10 text-white"
                  />
                </div>
              </div>

              <div>
                <label className="text-sm text-white/60 mb-2 block">Notify via</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setNotificationMethod('telegram')}
                    className={`flex-1 flex items-center justify-center gap-2 p-2.5 rounded-lg border transition-colors text-sm ${
                      notificationMethod === 'telegram'
                        ? 'bg-purple-500/20 border-purple-500 text-white'
                        : 'bg-white/5 border-white/10 text-white/60'
                    }`}
                  >
                    <MessageCircle className="w-4 h-4" />
                    Telegram
                  </button>
                  <button
                    onClick={() => setNotificationMethod('sms')}
                    className={`flex-1 flex items-center justify-center gap-2 p-2.5 rounded-lg border transition-colors text-sm ${
                      notificationMethod === 'sms'
                        ? 'bg-purple-500/20 border-purple-500 text-white'
                        : 'bg-white/5 border-white/10 text-white/60'
                    }`}
                  >
                    SMS
                  </button>
                </div>
              </div>

              {notificationMethod === 'sms' && (
                <Input
                  type="tel"
                  value={phoneNumber}
                  onChange={(e) => setPhoneNumber(e.target.value)}
                  placeholder="+1 (555) 123-4567"
                  className="bg-white/5 border-white/10 text-white"
                />
              )}

              <Input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Note (optional)"
                className="bg-white/5 border-white/10 text-white"
              />

              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => setStep(1)}
                  className="flex-1 py-2.5 rounded-lg border border-white/10 text-white/60 hover:text-white transition-colors"
                >
                  Back
                </button>
                <button
                  onClick={handleCreate}
                  disabled={creating || !targetValue}
                  className="flex-1 py-2.5 rounded-lg bg-purple-600 hover:bg-purple-700 text-white font-medium transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                >
                  {creating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bell className="w-4 h-4" />}
                  Create Alert
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// Main Dashboard Component
export const AlertDashboard = ({ getAuthHeader, user, onLogout, onSwitchToPortfolio }) => {
  const [alerts, setAlerts] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [activeNav, setActiveNav] = useState('alerts');
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [telegramChatId, setTelegramChatId] = useState('');
  const [connectingTelegram, setConnectingTelegram] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const [alertsRes, subRes, tgRes] = await Promise.all([
        axios.get(`${API}/alerts`, { headers: getAuthHeader() }),
        axios.get(`${API}/alerts/subscription`, { headers: getAuthHeader() }),
        axios.get(`${API}/alerts/telegram/status`, { headers: getAuthHeader() }).catch(() => ({ data: { connected: false } }))
      ]);
      setAlerts(alertsRes.data.alerts || []);
      setSubscription(subRes.data);
      setTelegramStatus(tgRes.data);
    } catch (err) {
      console.error('Error fetching data:', err);
      setError('Failed to load alerts');
    } finally {
      setLoading(false);
    }
  }, [getAuthHeader]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleSubscribe = async () => {
    setActionLoading(true);
    setError('');
    try {
      const response = await axios.post(`${API}/alerts/create-checkout`, {}, {
        headers: getAuthHeader()
      });
      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create checkout session');
      setActionLoading(false);
    }
  };

  const handleAlertCreated = (data) => {
    setSuccess(`Alert created for ${data.alert.asset_symbol}`);
    fetchData();
    setTimeout(() => setSuccess(''), 3000);
  };

  const toggleAlert = async (alertId) => {
    try {
      await axios.post(`${API}/alerts/${alertId}/toggle`, {}, { headers: getAuthHeader() });
      fetchData();
    } catch (err) {
      setError('Failed to toggle alert');
    }
  };

  const deleteAlert = async (alertId) => {
    if (!window.confirm('Delete this alert?')) return;
    try {
      await axios.delete(`${API}/alerts/${alertId}`, { headers: getAuthHeader() });
      fetchData();
    } catch (err) {
      setError('Failed to delete alert');
    }
  };

  const connectTelegram = async () => {
    if (!telegramChatId.trim()) return;
    setConnectingTelegram(true);
    try {
      await axios.post(`${API}/alerts/telegram/connect?chat_id=${telegramChatId.trim()}`, {}, { headers: getAuthHeader() });
      setSuccess('Telegram connected!');
      setTelegramChatId('');
      fetchData();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to connect');
    } finally {
      setConnectingTelegram(false);
    }
  };

  const disconnectTelegram = async () => {
    try {
      await axios.delete(`${API}/alerts/telegram/disconnect`, { headers: getAuthHeader() });
      fetchData();
    } catch (err) {
      setError('Failed to disconnect');
    }
  };

  const testTelegram = async () => {
    try {
      await axios.post(`${API}/alerts/telegram/test`, {}, { headers: getAuthHeader() });
      setSuccess('Test alert sent!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to send test');
    }
  };

  const canCreateAlerts = subscription?.status === 'trialing' || subscription?.status === 'active';
  const daysRemaining = subscription?.days_remaining;

  if (loading) {
    return (
      <div className="min-h-screen bg-[#0d0d14] flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#0d0d14] flex">
      {/* Sidebar */}
      <div className="w-56 bg-[#12121a] border-r border-white/5 flex flex-col">
        {/* Logo */}
        <div className="p-4 border-b border-white/5">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-purple-600 flex items-center justify-center">
              <Bell className="w-4 h-4 text-white" />
            </div>
            <span className="text-white font-semibold text-sm">
              CRYPTO<span className="text-purple-400">BAGTRACKER</span>
            </span>
          </div>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1">
          <button
            onClick={() => setActiveNav('alerts')}
            className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors ${
              activeNav === 'alerts' 
                ? 'bg-purple-500/20 text-purple-400' 
                : 'text-white/60 hover:text-white hover:bg-white/5'
            }`}
          >
            <Bell className="w-4 h-4" />
            Price Alerts
          </button>
          <button
            onClick={() => onSwitchToPortfolio && onSwitchToPortfolio()}
            className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors text-white/60 hover:text-white hover:bg-white/5"
          >
            <FileText className="w-4 h-4" />
            Bag Tracker
            <span className="text-[10px] bg-orange-500 text-white px-1.5 py-0.5 rounded ml-auto">Beta</span>
          </button>
        </nav>

        {/* Upgrade Card - only show if NOT trialing and NOT active */}
        {subscription?.status !== 'active' && subscription?.status !== 'trialing' && (
          <div className="p-3">
            <div className="bg-gradient-to-br from-purple-900/50 to-purple-800/30 rounded-xl p-4 border border-purple-500/20">
              <h4 className="text-white font-medium text-sm mb-1">Unlock Full Access</h4>
              <p className="text-white/50 text-xs mb-3">Upgrade to Premium for unlimited alerts.</p>
              <button 
                onClick={handleSubscribe}
                disabled={actionLoading}
                className="w-full bg-purple-600 hover:bg-purple-700 text-white text-sm py-2 rounded-lg transition-colors"
              >
                Upgrade Now
              </button>
            </div>
          </div>
        )}

        {/* User Profile */}
        <div className="p-3 border-t border-white/5">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 rounded-full bg-purple-600 flex items-center justify-center text-white text-sm font-medium">
              {user?.email?.charAt(0).toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-white text-sm truncate">{user?.email}</p>
              {subscription?.status === 'trialing' && (
                <p className="text-purple-400 text-xs">Free Trial · {daysRemaining}d left</p>
              )}
              {subscription?.status === 'active' && (
                <p className="text-green-400 text-xs">Premium</p>
              )}
            </div>
            <button onClick={onLogout} className="text-white/40 hover:text-white">
              <LogOut className="w-4 h-4" />
            </button>
          </div>
          {subscription?.status === 'trialing' && (
            <div className="mt-2 h-1 bg-white/10 rounded-full overflow-hidden">
              <div 
                className="h-full bg-purple-500 rounded-full" 
                style={{ width: `${((7 - daysRemaining) / 7) * 100}%` }}
              />
            </div>
          )}
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex flex-col">
        {/* Header */}
        <header className="h-14 border-b border-white/5 flex items-center justify-between px-6">
          <h1 className="text-white">
            Welcome back, <span className="text-purple-400">{user?.email}</span>
          </h1>
          <div className="flex items-center gap-2">
            <button className="p-2 text-white/40 hover:text-white">
              <HelpCircle className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 p-6 overflow-y-auto">
          {/* Trial Banner */}
          {subscription?.status === 'trialing' && (
            <div className="bg-[#1a1a2e] border border-purple-500/20 rounded-xl p-4 mb-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Clock className="w-5 h-5 text-purple-400" />
                <div>
                  <p className="text-white font-medium">Free Trial</p>
                  <p className="text-white/50 text-sm">{daysRemaining} days remaining in your trial</p>
                </div>
              </div>
              <span className="bg-purple-500/20 text-purple-400 px-3 py-1 rounded-lg text-sm">Trial Active</span>
            </div>
          )}

          {/* Alerts */}
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-red-400 text-sm flex items-center gap-2 mb-4">
              <AlertCircle className="w-4 h-4" />
              {error}
            </div>
          )}
          
          {success && (
            <div className="bg-green-500/10 border border-green-500/20 rounded-lg px-4 py-3 text-green-400 text-sm flex items-center gap-2 mb-4">
              <CheckCircle className="w-4 h-4" />
              {success}
            </div>
          )}

          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-white font-semibold flex items-center gap-2">
                <Bell className="w-5 h-5 text-purple-400" />
                Your Alerts
              </h2>
              <p className="text-white/40 text-sm">{alerts.length} alerts configured</p>
            </div>
            {canCreateAlerts && (
              <button
                onClick={() => setShowCreateModal(true)}
                className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-sm font-medium flex items-center gap-2 transition-colors"
              >
                <Plus className="w-4 h-4" />
                New Alert
              </button>
            )}
          </div>

          {alerts.length === 0 ? (
            <div className="bg-[#1a1a2e] border border-white/10 rounded-xl py-12 text-center">
              <Bell className="w-12 h-12 mx-auto text-white/20 mb-3" />
              <p className="text-white font-medium mb-1">No alerts yet</p>
              <p className="text-white/40 text-sm mb-4">Create your first alert to get started</p>
              {canCreateAlerts && (
                <button 
                  onClick={() => setShowCreateModal(true)}
                  className="bg-purple-600 hover:bg-purple-700 text-white px-4 py-2 rounded-lg text-sm"
                >
                  Create Alert
                </button>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              {alerts.map((alert) => {
                const typeInfo = ALERT_TYPE_LABELS[alert.alert_type] || {};
                return (
                  <div key={alert.alert_id} className="bg-[#1a1a2e] border border-white/10 rounded-xl p-4">
                    <div className="flex items-center gap-4">
                      <CryptoIcon symbol={alert.asset_symbol} />
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="text-white font-semibold">{alert.asset_symbol}</span>
                          <span className="text-[10px] bg-purple-500/30 text-purple-300 px-1.5 py-0.5 rounded">CRYPTO</span>
                          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
                            alert.status === 'active' 
                              ? 'bg-green-500/30 text-green-400' 
                              : 'bg-white/10 text-white/40'
                          }`}>
                            {alert.status.toUpperCase()}
                          </span>
                        </div>
                        <p className="text-white/60 text-sm">
                          {typeInfo.label}: {alert.alert_type.includes('percent') ? `${alert.target_value}%` : formatPrice(alert.target_value)}
                          <span className="text-purple-400 ml-3">
                            Current: {formatPrice(alert.current_price)}
                          </span>
                          {alert.note && <span className="text-white/40 ml-3">Note: {alert.note}</span>}
                        </p>
                      </div>
                      <div className="flex items-center gap-1">
                        <button className="p-2 text-white/40 hover:text-white">
                          <BarChart3 className="w-4 h-4" />
                        </button>
                        <button 
                          onClick={() => toggleAlert(alert.alert_id)}
                          className="p-2 text-white/40 hover:text-white"
                        >
                          {alert.status === 'active' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                        </button>
                        <button 
                          onClick={() => deleteAlert(alert.alert_id)}
                          className="p-2 text-white/40 hover:text-red-400"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Telegram Section */}
          {canCreateAlerts && (
            <div className="bg-[#1a1a2e] border border-white/10 rounded-xl p-4 mt-6">
              <div className="flex items-center gap-2 mb-3">
                <MessageCircle className="w-5 h-5 text-purple-400" />
                <h3 className="text-white font-medium">Telegram Notifications</h3>
                {telegramStatus?.connected && (
                  <span className="text-[10px] bg-green-500/30 text-green-400 px-1.5 py-0.5 rounded ml-2">CONNECTED</span>
                )}
              </div>
              
              {telegramStatus?.connected ? (
                <div className="flex items-center justify-between">
                  <p className="text-white/50 text-sm">Alerts will be sent to your Telegram</p>
                  <div className="flex gap-2">
                    <button onClick={testTelegram} className="text-purple-400 hover:text-purple-300 text-sm">
                      Send Test
                    </button>
                    <button onClick={disconnectTelegram} className="text-red-400 hover:text-red-300 text-sm">
                      Disconnect
                    </button>
                  </div>
                </div>
              ) : (
                <>
                  <p className="text-white/50 text-sm mb-3">
                    Get instant alerts on Telegram - unlimited, no rate limits.
                  </p>
                  <p className="text-white/70 text-sm mb-1">
                    1. Start chat with <a href="https://t.me/cryptobagtrackerbot" target="_blank" rel="noopener noreferrer" className="text-purple-400 hover:underline">@cryptobagtrackerbot</a> <ExternalLink className="w-3 h-3 inline" />
                  </p>
                  <p className="text-white/50 text-sm mb-3">
                    2. Send /start to the bot, it will reply with your Chat ID
                  </p>
                  <div className="flex gap-2">
                    <Input
                      value={telegramChatId}
                      onChange={(e) => setTelegramChatId(e.target.value)}
                      placeholder="Enter your Chat ID"
                      className="bg-white/5 border-white/10 text-white max-w-xs"
                    />
                    <button
                      onClick={connectTelegram}
                      disabled={connectingTelegram || !telegramChatId.trim()}
                      className="bg-purple-600 hover:bg-purple-700 disabled:opacity-50 text-white px-4 py-2 rounded-lg text-sm transition-colors"
                    >
                      {connectingTelegram ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Connect'}
                    </button>
                  </div>
                </>
              )}
            </div>
          )}
        </main>

        {/* Footer */}
        <footer className="h-12 border-t border-white/5 flex items-center justify-between px-6 text-white/30 text-xs">
          <span>© 2026 CryptoBagTracker</span>
          <span>Track your bags. Know your worth.</span>
          <span className="flex items-center gap-1">
            <span>Secured with enterprise-grade encryption</span>
          </span>
        </footer>
      </div>

      <CreateAlertModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={handleAlertCreated}
        getAuthHeader={getAuthHeader}
      />
    </div>
  );
};

export default AlertDashboard;
