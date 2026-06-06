import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Bell,
  Plus,
  Trash2,
  Pause,
  Play,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Percent,
  Search,
  Loader2,
  AlertCircle,
  CheckCircle,
  X,
  ArrowUp,
  ArrowDown,
  Zap,
  Clock,
  CreditCard,
  Sparkles,
  MessageCircle,
  Send,
  ExternalLink
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Format price
const formatPrice = (price) => {
  if (!price) return '$0.00';
  if (price >= 1000) return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (price >= 1) return `$${price.toFixed(2)}`;
  if (price >= 0.01) return `$${price.toFixed(4)}`;
  return `$${price.toFixed(8)}`;
};

// Alert type labels
const ALERT_TYPE_LABELS = {
  price_above: { label: 'Price Above', icon: ArrowUp, color: 'text-[#00C805]' },
  price_below: { label: 'Price Below', icon: ArrowDown, color: 'text-[#FF3B30]' },
  percent_change_up: { label: '% Change Up', icon: TrendingUp, color: 'text-[#00C805]' },
  percent_change_down: { label: '% Change Down', icon: TrendingDown, color: 'text-[#FF3B30]' }
};

// Asset type badges
const AssetBadge = ({ type }) => (
  <Badge className={type === 'crypto' ? 'bg-orange-600' : 'bg-white text-black'}>
    {type === 'crypto' ? 'CRYPTO' : 'STOCK'}
  </Badge>
);

// Status badge
const StatusBadge = ({ status }) => {
  const styles = {
    active: 'bg-[#00C805]',
    paused: 'bg-yellow-600',
    triggered: 'bg-white text-black',
    expired: 'bg-gray-600'
  };
  return <Badge className={styles[status] || 'bg-gray-600'}>{status.toUpperCase()}</Badge>;
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

  // Search assets
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

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      if (searchQuery) searchAssets(searchQuery);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, searchAssets]);

  // Fetch price when asset is selected
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
    
    // Require phone for SMS
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
        if (detail.error === 'trial_expired') {
          setError('Your free trial has expired. Subscribe to continue creating alerts.');
        } else if (detail.error === 'no_subscription') {
          setError('Start your free trial to create alerts.');
        } else {
          setError(detail.message || 'Failed to create alert');
        }
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
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <Card className="bg-[#0C0C0E] border-[#1F1F22] w-full max-w-md max-h-[90vh] overflow-y-auto">
        <CardHeader className="flex flex-row items-center justify-between pb-2">
          <CardTitle className="text-white text-lg">
            {step === 1 ? 'Search Asset' : 'Configure Alert'}
          </CardTitle>
          <Button variant="ghost" size="sm" onClick={handleClose}>
            <X className="w-4 h-4" />
          </Button>
        </CardHeader>
        <CardContent className="space-y-4">
          {error && (
            <Alert className="bg-red-900/20 border-red-700">
              <AlertCircle className="w-4 h-4 text-[#FF3B30]" />
              <AlertDescription className="text-[#FF3B30]">{error}</AlertDescription>
            </Alert>
          )}

          {step === 1 && (
            <>
              {/* Search Input */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8A8A93]" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search BTC, ETH, SOL..."
                  className="pl-10 bg-[#161618] border-[#1F1F22] text-white"
                  autoFocus
                  data-testid="alert-search-input"
                />
                {searching && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-[#8A8A93]" />}
              </div>

              {/* Search Results */}
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {searchResults.map((result) => (
                  <div
                    key={`${result.type}-${result.symbol}`}
                    onClick={() => handleSelectAsset(result)}
                    className="flex items-center justify-between p-3 bg-[#161618]/50 rounded-lg cursor-pointer hover:bg-[#161618] transition-colors"
                    data-testid={`search-result-${result.symbol}`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">{result.symbol}</span>
                        <AssetBadge type={result.type} />
                      </div>
                      <p className="text-xs text-[#8A8A93]">{result.name}</p>
                    </div>
                    <ArrowUp className="w-4 h-4 text-[#8A8A93]" />
                  </div>
                ))}
                
                {searchQuery && !searching && searchResults.length === 0 && (
                  <p className="text-center text-[#8A8A93] py-4">No results found</p>
                )}
                
                {!searchQuery && (
                  <div className="text-center text-[#8A8A93] py-8">
                    <Search className="w-12 h-12 mx-auto mb-2 opacity-50" />
                    <p>Search for a crypto symbol</p>
                    <p className="text-xs mt-1">e.g., BTC, ETH, SOL, DOGE</p>
                  </div>
                )}
              </div>
            </>
          )}

          {step === 2 && selectedAsset && (
            <>
              {/* Selected Asset */}
              <div className="flex items-center justify-between p-3 bg-[#161618]/50 rounded-lg">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium text-lg">{selectedAsset.symbol}</span>
                    <AssetBadge type={selectedAsset.type} />
                  </div>
                  <p className="text-xs text-[#8A8A93]">{selectedAsset.name}</p>
                </div>
                <div className="text-right">
                  <p className="text-white font-medium">
                    {currentPrice ? formatPrice(currentPrice.price) : 'Loading...'}
                  </p>
                  {currentPrice?.change_24h && (
                    <p className={`text-xs ${currentPrice.change_24h >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'}`}>
                      {currentPrice.change_24h >= 0 ? '+' : ''}{currentPrice.change_24h.toFixed(2)}% (24h)
                    </p>
                  )}
                </div>
              </div>

              {/* Alert Type */}
              <div>
                <label className="text-sm text-white mb-2 block">Alert Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(ALERT_TYPE_LABELS).map(([key, { label, icon: Icon, color }]) => (
                    <Button
                      key={key}
                      variant={alertType === key ? 'default' : 'outline'}
                      onClick={() => setAlertType(key)}
                      className={`justify-start ${alertType === key ? 'bg-white text-black' : 'border-[#1F1F22]'}`}
                      data-testid={`alert-type-${key}`}
                    >
                      <Icon className={`w-4 h-4 mr-2 ${color}`} />
                      {label}
                    </Button>
                  ))}
                </div>
              </div>

              {/* Target Value */}
              <div>
                <label className="text-sm text-white mb-2 block">
                  {alertType.includes('percent') ? 'Percentage Change' : 'Target Price'}
                </label>
                <div className="relative">
                  {alertType.includes('percent') ? (
                    <Percent className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8A8A93]" />
                  ) : (
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[#8A8A93]" />
                  )}
                  <Input
                    type="number"
                    value={targetValue}
                    onChange={(e) => setTargetValue(e.target.value)}
                    placeholder={alertType.includes('percent') ? '5' : currentPrice?.price?.toString() || '0'}
                    className="pl-10 bg-[#161618] border-[#1F1F22] text-white"
                    data-testid="alert-target-value"
                  />
                </div>
                {currentPrice && !alertType.includes('percent') && (
                  <p className="text-xs text-[#8A8A93] mt-1">
                    Current: {formatPrice(currentPrice.price)}
                  </p>
                )}
              </div>

              {/* Notification Method - Telegram or SMS */}
              <div>
                <label className="text-sm text-white mb-2 block">Notify via</label>
                <div className="flex gap-2">
                  <Button
                    variant={notificationMethod === 'telegram' ? 'default' : 'outline'}
                    onClick={() => setNotificationMethod('telegram')}
                    className={notificationMethod === 'telegram' ? 'bg-white text-black' : 'border-[#1F1F22]'}
                    size="sm"
                    data-testid="notify-telegram"
                  >
                    <MessageCircle className="w-4 h-4 mr-1" />
                    Telegram
                  </Button>
                  <Button
                    variant={notificationMethod === 'sms' ? 'default' : 'outline'}
                    onClick={() => setNotificationMethod('sms')}
                    className={notificationMethod === 'sms' ? 'bg-white text-black' : 'border-[#1F1F22]'}
                    size="sm"
                    data-testid="notify-sms"
                  >
                    SMS
                  </Button>
                </div>
              </div>

              {/* Phone Number - show when SMS selected */}
              {notificationMethod === 'sms' && (
                <div>
                  <label className="text-sm text-white mb-2 block">Phone Number</label>
                  <Input
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="+1 (555) 123-4567"
                    className="bg-[#161618] border-[#1F1F22] text-white"
                    data-testid="alert-phone-input"
                  />
                  <p className="text-xs text-[#4A4A52] mt-1">Include country code (e.g., +1 for US)</p>
                </div>
              )}

              {/* Telegram reminder when telegram selected */}
              {notificationMethod === 'telegram' && (
                <div className="bg-blue-900/30 border border-blue-700/50 rounded-lg p-3">
                  <p className="text-blue-300 text-sm flex items-center gap-2">
                    <MessageCircle className="w-4 h-4" />
                    Connect your Telegram below to receive alerts
                  </p>
                </div>
              )}

              {/* Note */}
              <div>
                <label className="text-sm text-white mb-2 block">Note (optional)</label>
                <Input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g., Buy signal"
                  className="bg-[#161618] border-[#1F1F22] text-white"
                />
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => setStep(1)}
                  className="flex-1 border-[#1F1F22]"
                >
                  Back
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={creating || !targetValue}
                  className="flex-1 bg-white text-black hover:bg-gray-200"
                  data-testid="create-alert-submit"
                >
                  {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Bell className="w-4 h-4 mr-2" />}
                  Create Alert
                </Button>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

// Subscription Banner Component
const SubscriptionBanner = ({ subscription, onSubscribe, loading }) => {
  const status = subscription?.status || 'none';
  const daysRemaining = subscription?.days_remaining;

  if (status === 'active') {
    return (
      <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-4 py-3 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <CheckCircle className="w-4 h-4 text-[#00C805]" />
          <span className="text-white/80 text-sm">
            <span className="font-medium">Unlimited Plan</span> — Create unlimited alerts
          </span>
        </div>
        <span className="text-[#00C805] text-xs font-medium">Active</span>
      </div>
    );
  }

  if (status === 'trialing') {
    return (
      <div className="bg-white/5 border border-white/10 rounded-lg px-4 py-3 mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Clock className="w-4 h-4 text-white/60" />
          <span className="text-white/80 text-sm">
            <span className="font-medium">Free Trial</span> — {daysRemaining} day{daysRemaining !== 1 ? 's' : ''} remaining
          </span>
        </div>
        <span className="text-white/40 text-xs">Trial Active</span>
      </div>
    );
  }

  if (status === 'expired') {
    return (
      <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-6 mb-6 text-center">
        <AlertCircle className="w-8 h-8 text-[#FF3B30] mx-auto mb-3" />
        <h3 className="text-white font-medium mb-1">Trial Expired</h3>
        <p className="text-white/50 text-sm mb-4">Subscribe to continue using alerts</p>
        <button 
          onClick={onSubscribe} 
          disabled={loading}
          className="bg-white text-black font-medium px-5 py-2 rounded-lg hover:bg-white/90 transition-colors text-sm"
          data-testid="subscribe-expired-btn"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Subscribe — $18.88/mo'}
        </button>
      </div>
    );
  }

  // No subscription
  return (
    <div className="bg-white/5 border border-white/10 rounded-xl p-8 mb-6 text-center">
      <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center mx-auto mb-4">
        <Zap className="w-6 h-6 text-[#FFB800]" />
      </div>
      <h3 className="text-lg font-semibold text-white mb-2">Start Free Trial</h3>
      <p className="text-white/50 text-sm mb-6 max-w-sm mx-auto">
        Unlimited price alerts with instant Telegram notifications.
      </p>
      <button 
        onClick={onSubscribe}
        disabled={loading}
        className="bg-white text-black font-medium px-6 py-2.5 rounded-lg hover:bg-white/90 transition-colors"
        data-testid="subscribe-btn"
      >
        {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Start Free Trial'}
      </button>
      <p className="text-white/30 text-xs mt-3">7 days free, then $18.88/month</p>
    </div>
  );
};

// Main Alert Dashboard
export const AlertDashboard = ({ getAuthHeader }) => {
  const [alerts, setAlerts] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Telegram state
  const [telegramStatus, setTelegramStatus] = useState(null);
  const [telegramChatId, setTelegramChatId] = useState('');
  const [connectingTelegram, setConnectingTelegram] = useState(false);

  // Fetch alerts and subscription status
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

  // Start free trial
  const handleStartTrial = async () => {
    setActionLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API}/alerts/start-trial`, {}, {
        headers: getAuthHeader()
      });
      
      setSuccess(response.data.message);
      fetchData();
      setTimeout(() => setSuccess(''), 5000);
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail || 'Failed to start trial');
    } finally {
      setActionLoading(false);
    }
  };

  // Create checkout session for subscription
  const handleSubscribe = async () => {
    setActionLoading(true);
    setError('');
    
    try {
      const response = await axios.post(`${API}/alerts/create-checkout`, {}, {
        headers: getAuthHeader()
      });
      
      // Redirect to Stripe checkout
      if (response.data.checkout_url) {
        window.location.href = response.data.checkout_url;
      }
    } catch (err) {
      const detail = err.response?.data?.detail;
      setError(detail || 'Failed to create checkout session');
      setActionLoading(false);
    }
  };

  // Handle alert created
  const handleAlertCreated = (data) => {
    setSuccess(`Alert created for ${data.alert.asset_symbol}`);
    fetchData();
    setTimeout(() => setSuccess(''), 3000);
  };

  // Toggle alert
  const toggleAlert = async (alertId) => {
    try {
      await axios.post(`${API}/alerts/${alertId}/toggle`, {}, {
        headers: getAuthHeader()
      });
      fetchData();
    } catch (err) {
      setError('Failed to toggle alert');
    }
  };

  // Delete alert
  const deleteAlert = async (alertId) => {
    if (!window.confirm('Are you sure you want to delete this alert?')) return;
    
    try {
      await axios.delete(`${API}/alerts/${alertId}`, {
        headers: getAuthHeader()
      });
      fetchData();
      setSuccess('Alert deleted');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to delete alert');
    }
  };

  // Connect Telegram
  const connectTelegram = async () => {
    if (!telegramChatId.trim()) {
      setError('Please enter your Telegram Chat ID');
      return;
    }
    
    setConnectingTelegram(true);
    setError('');
    
    try {
      const response = await axios.post(
        `${API}/alerts/telegram/connect?chat_id=${telegramChatId.trim()}`,
        {},
        { headers: getAuthHeader() }
      );
      
      setSuccess(response.data.message);
      setTelegramChatId('');
      fetchData();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to connect Telegram');
    } finally {
      setConnectingTelegram(false);
    }
  };

  // Disconnect Telegram
  const disconnectTelegram = async () => {
    try {
      await axios.delete(`${API}/alerts/telegram/disconnect`, {
        headers: getAuthHeader()
      });
      setSuccess('Telegram disconnected');
      fetchData();
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError('Failed to disconnect Telegram');
    }
  };

  // Test Telegram
  const testTelegram = async () => {
    try {
      await axios.post(`${API}/alerts/telegram/test`, {}, {
        headers: getAuthHeader()
      });
      setSuccess('Test alert sent to Telegram!');
      setTimeout(() => setSuccess(''), 3000);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to send test');
    }
  };

  const canCreateAlerts = subscription?.can_create_alerts || subscription?.status === 'trialing' || subscription?.status === 'active';

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 animate-spin text-white/40" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Subscription Banner */}
      <SubscriptionBanner 
        subscription={subscription}
        onSubscribe={handleSubscribe}
        loading={actionLoading}
      />

      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h2 className="text-lg font-semibold text-white">Your Alerts</h2>
          <p className="text-white/40 text-sm">
            {alerts.length} alert{alerts.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        {canCreateAlerts && (
          <button
            onClick={() => setShowCreateModal(true)}
            className="bg-white text-black font-medium px-4 py-2 rounded-lg hover:bg-white/90 transition-colors text-sm flex items-center gap-2"
            data-testid="new-alert-btn"
          >
            <Plus className="w-4 h-4" />
            New Alert
          </button>
        )}
      </div>

      {/* Alerts */}
      {error && (
        <div className="bg-red-500/10 border border-red-500/20 rounded-lg px-4 py-3 text-[#FF3B30] text-sm flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          {error}
        </div>
      )}
      
      {success && (
        <div className="bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-4 py-3 text-[#00C805] text-sm flex items-center gap-2">
          <CheckCircle className="w-4 h-4" />
          {success}
        </div>
      )}

      {alerts.length === 0 ? (
        <div className="bg-white/5 border border-white/10 rounded-xl py-12 text-center">
          <div className="w-12 h-12 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
            <Bell className="w-6 h-6 text-white/30" />
          </div>
          <h3 className="text-white font-medium mb-2">No alerts yet</h3>
          <p className="text-white/40 text-sm mb-4 max-w-sm mx-auto">
            {canCreateAlerts 
              ? 'Create your first alert to get notified when prices hit your targets.'
              : 'Start your free trial to create price alerts.'}
          </p>
          {canCreateAlerts && (
            <button 
              onClick={() => setShowCreateModal(true)} 
                className="bg-white text-black hover:bg-gray-200"
                data-testid="create-first-alert-btn"
              >
                <Plus className="w-4 h-4 mr-1" />
                Create Alert
              </button>
            )}
          </div>
      ) : (
        <div className="space-y-3">
          {alerts.map((alert) => {
            const typeInfo = ALERT_TYPE_LABELS[alert.alert_type] || {};
            const TypeIcon = typeInfo.icon || Bell;
            const isUp = alert.alert_type.includes('above') || alert.alert_type.includes('up');
            
            return (
              <div key={alert.alert_id} className="bg-white/5 border border-white/10 rounded-lg p-4" data-testid={`alert-card-${alert.alert_id}`}>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                      alert.status === 'active' 
                        ? isUp ? 'bg-emerald-500/20' : 'bg-red-500/20'
                        : 'bg-white/5'
                    }`}>
                      <TypeIcon className={`w-5 h-5 ${
                        alert.status === 'active'
                          ? isUp ? 'text-[#00C805]' : 'text-[#FF3B30]'
                          : 'text-white/30'
                      }`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">{alert.asset_symbol}</span>
                        <span className={`text-xs px-1.5 py-0.5 rounded ${
                          alert.status === 'active' ? 'bg-emerald-500/20 text-[#00C805]' : 'bg-white/10 text-white/40'
                        }`}>
                          {alert.status}
                        </span>
                      </div>
                      <p className="text-sm text-white/50 mt-0.5">
                        {typeInfo.label}: {alert.alert_type.includes('percent') ? `${alert.target_value}%` : formatPrice(alert.target_value)}
                        {alert.current_price > 0 && (
                          <span className="text-white/30 ml-2">
                            Now: {formatPrice(alert.current_price)}
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <button
                      onClick={() => toggleAlert(alert.alert_id)}
                      className="p-2 text-white/40 hover:text-white transition-colors"
                      data-testid={`toggle-alert-${alert.alert_id}`}
                    >
                      {alert.status === 'active' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                    </button>
                    <button
                      onClick={() => deleteAlert(alert.alert_id)}
                      className="p-2 text-white/40 hover:text-[#FF3B30] transition-colors"
                      data-testid={`delete-alert-${alert.alert_id}`}
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

      {/* Telegram Connect Section */}
      {canCreateAlerts && (
        <div className="bg-white/5 border border-white/10 rounded-lg p-4">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <MessageCircle className="w-4 h-4 text-blue-400" />
              <span className="text-white/80 text-sm font-medium">Telegram</span>
            </div>
            {telegramStatus?.connected && (
              <span className="text-[#00C805] text-xs">Connected</span>
            )}
          </div>
          
          {telegramStatus?.connected ? (
            <div className="flex items-center justify-between">
              <p className="text-white/40 text-sm">Alerts sent to your Telegram</p>
              <div className="flex gap-2">
                <button
                  onClick={testTelegram}
                  className="text-white/60 hover:text-white text-sm px-3 py-1.5 rounded border border-white/10 hover:border-white/20 transition-colors"
                >
                  Test
                </button>
                <button
                  onClick={disconnectTelegram}
                  className="text-[#FF3B30]/80 hover:text-[#FF3B30] text-sm px-3 py-1.5 rounded border border-red-500/20 hover:border-red-500/30 transition-colors"
                >
                  Disconnect
                </button>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              <p className="text-white/40 text-sm">
                Connect Telegram for instant alerts
              </p>
              <div className="space-y-2">
                <a
                  href="https://t.me/cryptobagtrackerbot"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-blue-400 hover:text-blue-300 text-sm"
                >
                  1. Message @cryptobagtrackerbot
                  <ExternalLink className="w-3 h-3" />
                </a>
                <p className="text-white/30 text-xs">
                  2. Send /start to get your Chat ID
                </p>
              </div>
              <div className="flex gap-2 mt-3">
                <Input
                  value={telegramChatId}
                  onChange={(e) => setTelegramChatId(e.target.value)}
                  placeholder="Paste Chat ID"
                  className="bg-white/5 border-white/10 text-white max-w-[200px] text-sm"
                  data-testid="telegram-chat-id-input"
                />
                <button
                  onClick={connectTelegram}
                  disabled={connectingTelegram || !telegramChatId.trim()}
                  className="bg-blue-500 hover:bg-white text-black disabled:bg-blue-500/50 text-white text-sm px-4 py-2 rounded-lg transition-colors"
                  data-testid="connect-telegram-btn"
                >
                  {connectingTelegram ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    'Connect'
                  )}
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Create Alert Modal */}
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
