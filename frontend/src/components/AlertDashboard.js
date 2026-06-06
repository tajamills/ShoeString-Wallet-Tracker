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
  price_above: { label: 'Price Above', icon: ArrowUp, color: 'text-green-400' },
  price_below: { label: 'Price Below', icon: ArrowDown, color: 'text-red-400' },
  percent_change_up: { label: '% Change Up', icon: TrendingUp, color: 'text-green-400' },
  percent_change_down: { label: '% Change Down', icon: TrendingDown, color: 'text-red-400' }
};

// Asset type badges
const AssetBadge = ({ type }) => (
  <Badge className={type === 'crypto' ? 'bg-orange-600' : 'bg-blue-600'}>
    {type === 'crypto' ? 'CRYPTO' : 'STOCK'}
  </Badge>
);

// Status badge
const StatusBadge = ({ status }) => {
  const styles = {
    active: 'bg-green-600',
    paused: 'bg-yellow-600',
    triggered: 'bg-purple-600',
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
      <Card className="bg-slate-800 border-slate-700 w-full max-w-md max-h-[90vh] overflow-y-auto">
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
              <AlertCircle className="w-4 h-4 text-red-400" />
              <AlertDescription className="text-red-300">{error}</AlertDescription>
            </Alert>
          )}

          {step === 1 && (
            <>
              {/* Search Input */}
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search BTC, ETH, SOL..."
                  className="pl-10 bg-slate-700 border-slate-600 text-white"
                  autoFocus
                  data-testid="alert-search-input"
                />
                {searching && <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 w-4 h-4 animate-spin text-gray-400" />}
              </div>

              {/* Search Results */}
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {searchResults.map((result) => (
                  <div
                    key={`${result.type}-${result.symbol}`}
                    onClick={() => handleSelectAsset(result)}
                    className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg cursor-pointer hover:bg-slate-700 transition-colors"
                    data-testid={`search-result-${result.symbol}`}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">{result.symbol}</span>
                        <AssetBadge type={result.type} />
                      </div>
                      <p className="text-xs text-gray-400">{result.name}</p>
                    </div>
                    <ArrowUp className="w-4 h-4 text-gray-400" />
                  </div>
                ))}
                
                {searchQuery && !searching && searchResults.length === 0 && (
                  <p className="text-center text-gray-400 py-4">No results found</p>
                )}
                
                {!searchQuery && (
                  <div className="text-center text-gray-400 py-8">
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
              <div className="flex items-center justify-between p-3 bg-slate-700/50 rounded-lg">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-white font-medium text-lg">{selectedAsset.symbol}</span>
                    <AssetBadge type={selectedAsset.type} />
                  </div>
                  <p className="text-xs text-gray-400">{selectedAsset.name}</p>
                </div>
                <div className="text-right">
                  <p className="text-white font-medium">
                    {currentPrice ? formatPrice(currentPrice.price) : 'Loading...'}
                  </p>
                  {currentPrice?.change_24h && (
                    <p className={`text-xs ${currentPrice.change_24h >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {currentPrice.change_24h >= 0 ? '+' : ''}{currentPrice.change_24h.toFixed(2)}% (24h)
                    </p>
                  )}
                </div>
              </div>

              {/* Alert Type */}
              <div>
                <label className="text-sm text-gray-300 mb-2 block">Alert Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(ALERT_TYPE_LABELS).map(([key, { label, icon: Icon, color }]) => (
                    <Button
                      key={key}
                      variant={alertType === key ? 'default' : 'outline'}
                      onClick={() => setAlertType(key)}
                      className={`justify-start ${alertType === key ? 'bg-purple-600' : 'border-slate-600'}`}
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
                <label className="text-sm text-gray-300 mb-2 block">
                  {alertType.includes('percent') ? 'Percentage Change' : 'Target Price'}
                </label>
                <div className="relative">
                  {alertType.includes('percent') ? (
                    <Percent className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  ) : (
                    <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
                  )}
                  <Input
                    type="number"
                    value={targetValue}
                    onChange={(e) => setTargetValue(e.target.value)}
                    placeholder={alertType.includes('percent') ? '5' : currentPrice?.price?.toString() || '0'}
                    className="pl-10 bg-slate-700 border-slate-600 text-white"
                    data-testid="alert-target-value"
                  />
                </div>
                {currentPrice && !alertType.includes('percent') && (
                  <p className="text-xs text-gray-400 mt-1">
                    Current: {formatPrice(currentPrice.price)}
                  </p>
                )}
              </div>

              {/* Notification Method - Telegram or SMS */}
              <div>
                <label className="text-sm text-gray-300 mb-2 block">Notify via</label>
                <div className="flex gap-2">
                  <Button
                    variant={notificationMethod === 'telegram' ? 'default' : 'outline'}
                    onClick={() => setNotificationMethod('telegram')}
                    className={notificationMethod === 'telegram' ? 'bg-blue-600' : 'border-slate-600'}
                    size="sm"
                    data-testid="notify-telegram"
                  >
                    <MessageCircle className="w-4 h-4 mr-1" />
                    Telegram
                  </Button>
                  <Button
                    variant={notificationMethod === 'sms' ? 'default' : 'outline'}
                    onClick={() => setNotificationMethod('sms')}
                    className={notificationMethod === 'sms' ? 'bg-purple-600' : 'border-slate-600'}
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
                  <label className="text-sm text-gray-300 mb-2 block">Phone Number</label>
                  <Input
                    type="tel"
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="+1 (555) 123-4567"
                    className="bg-slate-700 border-slate-600 text-white"
                    data-testid="alert-phone-input"
                  />
                  <p className="text-xs text-gray-500 mt-1">Include country code (e.g., +1 for US)</p>
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
                <label className="text-sm text-gray-300 mb-2 block">Note (optional)</label>
                <Input
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  placeholder="e.g., Buy signal"
                  className="bg-slate-700 border-slate-600 text-white"
                />
              </div>

              {/* Actions */}
              <div className="flex gap-2 pt-2">
                <Button
                  variant="outline"
                  onClick={() => setStep(1)}
                  className="flex-1 border-slate-600"
                >
                  Back
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={creating || !targetValue}
                  className="flex-1 bg-purple-600 hover:bg-purple-700"
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
      <Card className="bg-gradient-to-r from-green-900/50 to-emerald-900/50 border-green-700/50 mb-6">
        <CardContent className="py-3 px-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <CheckCircle className="w-5 h-5 text-green-400" />
            <span className="text-white">
              <strong>Unlimited Plan</strong> - Create unlimited alerts
            </span>
          </div>
          <Badge className="bg-green-600">Active</Badge>
        </CardContent>
      </Card>
    );
  }

  if (status === 'trialing') {
    return (
      <Card className="bg-gradient-to-r from-purple-900/50 to-indigo-900/50 border-purple-700/50 mb-6">
        <CardContent className="py-3 px-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Clock className="w-5 h-5 text-purple-400" />
            <span className="text-white">
              <strong>Free Trial</strong> - {daysRemaining} day{daysRemaining !== 1 ? 's' : ''} remaining
            </span>
          </div>
          <Badge className="bg-purple-600">Trial Active</Badge>
        </CardContent>
      </Card>
    );
  }

  if (status === 'expired') {
    return (
      <Card className="bg-gradient-to-r from-red-900/50 to-orange-900/50 border-red-700/50 mb-6">
        <CardContent className="py-4 px-4 text-center">
          <AlertCircle className="w-8 h-8 text-red-400 mx-auto mb-2" />
          <h3 className="text-white font-semibold mb-1">Trial Expired</h3>
          <p className="text-gray-400 text-sm mb-3">Subscribe to continue creating and monitoring alerts</p>
          <Button 
            onClick={onSubscribe} 
            disabled={loading}
            className="bg-purple-600 hover:bg-purple-700"
            data-testid="subscribe-expired-btn"
          >
            {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <CreditCard className="w-4 h-4 mr-2" />}
            Subscribe - $18.88/month
          </Button>
        </CardContent>
      </Card>
    );
  }

  // No subscription - go directly to Stripe (which has 7-day trial built in)
  return (
    <Card className="bg-gradient-to-r from-purple-900/50 to-indigo-900/50 border-purple-700/50 mb-6">
      <CardContent className="py-6 px-4 text-center">
        <Sparkles className="w-10 h-10 text-yellow-400 mx-auto mb-3" />
        <h3 className="text-xl font-bold text-white mb-2">Get Price Alerts</h3>
        <p className="text-gray-300 text-sm mb-4 max-w-md mx-auto">
          Unlimited price alerts with instant Telegram notifications.
          7-day free trial included.
        </p>
        <Button 
          onClick={onSubscribe}
          disabled={loading}
          className="bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 text-black font-semibold"
          data-testid="subscribe-btn"
        >
          {loading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Zap className="w-4 h-4 mr-2" />}
          Start Free Trial
        </Button>
        <p className="text-gray-500 text-xs mt-2">7-day free trial, then $18.88/month</p>
      </CardContent>
    </Card>
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
        <Loader2 className="w-8 h-8 animate-spin text-purple-500" />
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
          <h2 className="text-xl font-bold text-white flex items-center gap-2">
            <Bell className="w-5 h-5 text-purple-400" />
            Your Alerts
          </h2>
          <p className="text-gray-400 text-sm mt-1">
            {alerts.length} alert{alerts.length !== 1 ? 's' : ''} configured
          </p>
        </div>
        {canCreateAlerts && (
          <Button
            onClick={() => setShowCreateModal(true)}
            className="bg-purple-600 hover:bg-purple-700"
            data-testid="new-alert-btn"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Alert
          </Button>
        )}
      </div>

      {/* Alerts */}
      {error && (
        <Alert className="bg-red-900/20 border-red-700">
          <AlertCircle className="w-4 h-4 text-red-400" />
          <AlertDescription className="text-red-300">{error}</AlertDescription>
        </Alert>
      )}
      
      {success && (
        <Alert className="bg-green-900/20 border-green-700">
          <CheckCircle className="w-4 h-4 text-green-400" />
          <AlertDescription className="text-green-300">{success}</AlertDescription>
        </Alert>
      )}

      {alerts.length === 0 ? (
        <Card className="bg-slate-800/50 border-slate-700">
          <CardContent className="py-12 text-center">
            <Bell className="w-16 h-16 mx-auto text-gray-600 mb-4" />
            <h3 className="text-xl font-medium text-white mb-2">No alerts yet</h3>
            <p className="text-gray-400 mb-4">
              {canCreateAlerts 
                ? 'Create your first price alert to get notified when prices hit your targets.'
                : 'Start your free trial to create price alerts.'}
            </p>
            {canCreateAlerts && (
              <Button 
                onClick={() => setShowCreateModal(true)} 
                className="bg-purple-600 hover:bg-purple-700"
                data-testid="create-first-alert-btn"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Alert
              </Button>
            )}
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-3">
          {alerts.map((alert) => {
            const typeInfo = ALERT_TYPE_LABELS[alert.alert_type] || {};
            const TypeIcon = typeInfo.icon || Bell;
            
            return (
              <Card key={alert.alert_id} className="bg-slate-800/50 border-slate-700" data-testid={`alert-card-${alert.alert_id}`}>
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className={`p-2 rounded-lg ${alert.status === 'active' ? 'bg-purple-600/20' : 'bg-gray-600/20'}`}>
                        <TypeIcon className={`w-6 h-6 ${alert.status === 'active' ? typeInfo.color : 'text-gray-400'}`} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium text-lg">{alert.asset_symbol}</span>
                          <AssetBadge type={alert.asset_type} />
                          <StatusBadge status={alert.status} />
                        </div>
                        <p className="text-sm text-gray-400 mt-1">
                          {typeInfo.label}: {alert.alert_type.includes('percent') ? `${alert.target_value}%` : formatPrice(alert.target_value)}
                          {alert.current_price && (
                            <span className="ml-2">
                              (Current: {formatPrice(alert.current_price)})
                            </span>
                          )}
                        </p>
                        {alert.note && (
                          <p className="text-xs text-gray-500 mt-1">Note: {alert.note}</p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => toggleAlert(alert.alert_id)}
                        className="text-gray-400 hover:text-white"
                        data-testid={`toggle-alert-${alert.alert_id}`}
                      >
                        {alert.status === 'active' ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => deleteAlert(alert.alert_id)}
                        className="text-gray-400 hover:text-red-400"
                        data-testid={`delete-alert-${alert.alert_id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Telegram Connect Section */}
      {canCreateAlerts && (
        <Card className="bg-slate-800/50 border-slate-700">
          <CardContent className="p-4">
            <div className="flex items-center gap-3 mb-3">
              <MessageCircle className="w-5 h-5 text-blue-400" />
              <h3 className="text-white font-medium">Telegram Notifications</h3>
              {telegramStatus?.connected && (
                <Badge className="bg-green-600">Connected</Badge>
              )}
            </div>
            
            {telegramStatus?.connected ? (
              <div className="flex items-center justify-between">
                <p className="text-gray-400 text-sm">
                  Alerts will be sent to your Telegram
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={testTelegram}
                    className="border-slate-600 text-gray-300"
                  >
                    <Send className="w-4 h-4 mr-1" />
                    Test
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={disconnectTelegram}
                    className="border-red-600 text-red-400 hover:bg-red-900/20"
                  >
                    Disconnect
                  </Button>
                </div>
              </div>
            ) : (
              <div className="space-y-3">
                <p className="text-gray-400 text-sm">
                  Get instant alerts on Telegram - unlimited, no rate limits.
                </p>
                <div className="flex flex-col sm:flex-row gap-2">
                  <a
                    href="https://t.me/cryptobagtrackerbot"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-2 text-blue-400 hover:text-blue-300 text-sm"
                  >
                    <span>1. Start chat with @cryptobagtrackerbot</span>
                    <ExternalLink className="w-3 h-3" />
                  </a>
                </div>
                <p className="text-gray-500 text-xs">
                  2. Send /start to the bot, it will reply with your Chat ID
                </p>
                <div className="flex gap-2">
                  <Input
                    value={telegramChatId}
                    onChange={(e) => setTelegramChatId(e.target.value)}
                    placeholder="Enter your Chat ID"
                    className="bg-slate-700 border-slate-600 text-white max-w-xs"
                    data-testid="telegram-chat-id-input"
                  />
                  <Button
                    onClick={connectTelegram}
                    disabled={connectingTelegram || !telegramChatId.trim()}
                    className="bg-blue-600 hover:bg-blue-700"
                    data-testid="connect-telegram-btn"
                  >
                    {connectingTelegram ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      'Connect'
                    )}
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
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
