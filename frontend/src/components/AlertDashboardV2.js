import React, { useState, useEffect, useCallback } from 'react';
import { 
  Bell, 
  ChartLineUp,
  SignOut, 
  Question,
  Plus,
  Trash,
  Pause,
  Play,
  ChartLineUp as TrendUp,
  ChartLineDown as TrendDown,
  CaretUp,
  CaretDown,
  CircleNotch,
  Warning,
  CheckCircle,
  Clock,
  TelegramLogo,
  ArrowSquareOut,
  X,
  MagnifyingGlass,
  CurrencyDollar,
  Percent,
  Folder,
  PaperPlaneTilt,
  ListBullets,
  Certificate,
  DeviceMobile
} from '@phosphor-icons/react';
import { Input } from '@/components/ui/input';
import axios from 'axios';
import { usePushNotifications } from '../hooks/usePushNotifications';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Professional monospace token badge
const TokenBadge = ({ symbol }) => {
  return (
    <div className="w-10 h-10 bg-[#161618] border border-[#1F1F22] flex items-center justify-center font-mono text-xs text-white tracking-wider">
      {symbol.slice(0, 2).toUpperCase()}
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
  price_above: { label: 'ABOVE', icon: CaretUp, color: 'text-[#00C805]' },
  price_below: { label: 'BELOW', icon: CaretDown, color: 'text-[#FF3B30]' },
  percent_change_up: { label: '% UP', icon: TrendUp, color: 'text-[#00C805]' },
  percent_change_down: { label: '% DOWN', icon: TrendDown, color: 'text-[#FF3B30]' }
};

// Create Alert Modal - Professional Design
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
    <div className="fixed inset-0 bg-black/90 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#0A0A0C] border border-[#1F1F22] w-full max-w-md max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-[#1F1F22]">
          <h2 className="text-white font-semibold tracking-tight">
            {step === 1 ? 'SEARCH ASSET' : 'CONFIGURE ALERT'}
          </h2>
          <button onClick={handleClose} className="text-[#8A8A93] hover:text-white transition-colors">
            <X size={20} weight="bold" />
          </button>
        </div>
        
        <div className="p-4 space-y-4">
          {error && (
            <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 px-3 py-2 text-[#FF3B30] text-sm flex items-center gap-2">
              <Warning size={16} weight="fill" />
              {error}
            </div>
          )}

          {step === 1 && (
            <>
              <div className="relative">
                <MagnifyingGlass className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8A8A93]" size={16} />
                <Input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search BTC, ETH, SOL..."
                  className="pl-10 bg-[#0C0C0E] border-[#1F1F22] text-white placeholder:text-[#4A4A52] rounded-none font-mono"
                  autoFocus
                />
                {searching && <CircleNotch className="absolute right-3 top-1/2 -translate-y-1/2 text-white animate-spin" size={16} />}
              </div>

              <div className="space-y-1 max-h-64 overflow-y-auto">
                {searchResults.map((result) => (
                  <div
                    key={`${result.type}-${result.symbol}`}
                    onClick={() => handleSelectAsset(result)}
                    className="flex items-center justify-between p-3 bg-[#0C0C0E] border border-[#1F1F22] cursor-pointer hover:bg-[#161618] transition-colors"
                    data-testid={`search-result-${result.symbol}`}
                  >
                    <div className="flex items-center gap-3">
                      <TokenBadge symbol={result.symbol} />
                      <div>
                        <span className="text-white font-mono text-sm">{result.symbol}</span>
                        <p className="text-xs text-[#8A8A93]">{result.name}</p>
                      </div>
                    </div>
                    <CaretUp className="text-[#4A4A52]" size={16} />
                  </div>
                ))}
                
                {searchQuery && !searching && searchResults.length === 0 && (
                  <p className="text-center text-[#8A8A93] py-4 font-mono text-sm">NO RESULTS</p>
                )}
                
                {!searchQuery && (
                  <div className="text-center text-[#8A8A93] py-8">
                    <MagnifyingGlass size={32} className="mx-auto mb-2 opacity-30" />
                    <p className="text-sm font-mono">SEARCH FOR A SYMBOL</p>
                  </div>
                )}
              </div>
            </>
          )}

          {step === 2 && selectedAsset && (
            <>
              <div className="flex items-center gap-3 p-3 bg-[#0C0C0E] border border-[#1F1F22]">
                <TokenBadge symbol={selectedAsset.symbol} />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-white font-mono">{selectedAsset.symbol}</span>
                    <span className="text-[10px] border border-[#1F1F22] text-[#8A8A93] px-1.5 py-0.5 font-mono">CRYPTO</span>
                  </div>
                  <p className="text-xs text-[#8A8A93]">{selectedAsset.name}</p>
                </div>
                <div className="text-right">
                  <p className="text-white font-mono tabular-nums">
                    {currentPrice ? formatPrice(currentPrice.price) : '...'}
                  </p>
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold tracking-[0.2em] uppercase text-[#8A8A93] mb-2 block">ALERT TYPE</label>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(ALERT_TYPE_LABELS).map(([key, { label, icon: Icon, color }]) => (
                    <button
                      key={key}
                      onClick={() => setAlertType(key)}
                      className={`flex items-center gap-2 p-3 border transition-colors text-sm font-mono ${
                        alertType === key 
                          ? 'bg-white text-black border-white' 
                          : 'bg-[#0C0C0E] border-[#1F1F22] text-[#8A8A93] hover:bg-[#161618]'
                      }`}
                      data-testid={`alert-type-${key}`}
                    >
                      <Icon size={16} weight="bold" />
                      {label}
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold tracking-[0.2em] uppercase text-[#8A8A93] mb-2 block">
                  {alertType.includes('percent') ? 'PERCENTAGE' : 'TARGET PRICE'}
                </label>
                <div className="relative">
                  {alertType.includes('percent') ? (
                    <Percent className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8A8A93]" size={16} />
                  ) : (
                    <CurrencyDollar className="absolute left-3 top-1/2 -translate-y-1/2 text-[#8A8A93]" size={16} />
                  )}
                  <Input
                    type="number"
                    value={targetValue}
                    onChange={(e) => setTargetValue(e.target.value)}
                    placeholder={alertType.includes('percent') ? '5' : '0.00'}
                    className="pl-10 bg-[#0C0C0E] border-[#1F1F22] text-white font-mono tabular-nums rounded-none"
                    data-testid="alert-target-value"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs font-semibold tracking-[0.2em] uppercase text-[#8A8A93] mb-2 block">NOTIFY VIA</label>
                <div className="flex gap-2">
                  <button
                    onClick={() => setNotificationMethod('telegram')}
                    className={`flex-1 flex items-center justify-center gap-2 p-2.5 border transition-colors text-sm font-mono ${
                      notificationMethod === 'telegram'
                        ? 'bg-white text-black border-white'
                        : 'bg-[#0C0C0E] border-[#1F1F22] text-[#8A8A93] hover:bg-[#161618]'
                    }`}
                    data-testid="notify-telegram"
                  >
                    <TelegramLogo size={16} weight="fill" />
                    TELEGRAM
                  </button>
                  <button
                    onClick={() => setNotificationMethod('sms')}
                    className={`flex-1 flex items-center justify-center gap-2 p-2.5 border transition-colors text-sm font-mono ${
                      notificationMethod === 'sms'
                        ? 'bg-white text-black border-white'
                        : 'bg-[#0C0C0E] border-[#1F1F22] text-[#8A8A93] hover:bg-[#161618]'
                    }`}
                    data-testid="notify-sms"
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
                  className="bg-[#0C0C0E] border-[#1F1F22] text-white font-mono rounded-none"
                  data-testid="alert-phone-input"
                />
              )}

              <Input
                value={note}
                onChange={(e) => setNote(e.target.value)}
                placeholder="Note (optional)"
                className="bg-[#0C0C0E] border-[#1F1F22] text-white rounded-none"
              />

              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => setStep(1)}
                  className="flex-1 py-2.5 border border-[#1F1F22] text-[#8A8A93] hover:bg-[#161618] transition-colors font-mono text-sm"
                >
                  BACK
                </button>
                <button
                  onClick={handleCreate}
                  disabled={creating || !targetValue}
                  className="flex-1 py-2.5 bg-white text-black font-semibold hover:bg-gray-200 transition-colors disabled:opacity-50 flex items-center justify-center gap-2 font-mono text-sm"
                  data-testid="create-alert-submit"
                >
                  {creating ? <CircleNotch size={16} className="animate-spin" /> : <Bell size={16} weight="fill" />}
                  CREATE
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// Request Coin Modal Component
const RequestCoinModal = ({ isOpen, onClose, getAuthHeader, onSuccess }) => {
  const [symbol, setSymbol] = useState('');
  const [name, setName] = useState('');
  const [reason, setReason] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [supportedCoins, setSupportedCoins] = useState([]);
  const [activeTab, setActiveTab] = useState('supported'); // 'request', 'supported'

  useEffect(() => {
    if (isOpen) {
      fetchSupportedCoins();
    }
  }, [isOpen]);

  const fetchSupportedCoins = async () => {
    try {
      const response = await axios.get(`${API}/alerts/public/supported-coins`);
      setSupportedCoins(response.data.coins || []);
    } catch (err) {
      console.error('Error fetching supported coins:', err);
    }
  };

  const handleSubmit = async () => {
    if (!symbol.trim()) {
      setError('Symbol is required');
      return;
    }
    setSubmitting(true);
    setError('');
    try {
      const response = await axios.post(`${API}/alerts/coin-request`, {
        symbol: symbol.trim(),
        name: name.trim(),
        reason: reason.trim()
      }, { headers: getAuthHeader() });
      onSuccess(response.data.message);
      handleClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit request');
    } finally {
      setSubmitting(false);
    }
  };

  const handleClose = () => {
    setSymbol('');
    setName('');
    setReason('');
    setError('');
    setActiveTab('supported');
    onClose();
  };

  if (!isOpen) return null;

  const iso20022Coins = supportedCoins.filter(c => c.is_iso20022);
  const otherCoins = supportedCoins.filter(c => !c.is_iso20022);

  return (
    <div className="fixed inset-0 bg-black/90 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-[#0A0A0C] border border-[#1F1F22] w-full max-w-lg max-h-[90vh] overflow-hidden flex flex-col">
        <div className="flex items-center justify-between p-4 border-b border-[#1F1F22]">
          <h2 className="text-white font-semibold tracking-tight">COIN LIBRARY</h2>
          <button onClick={handleClose} className="text-[#8A8A93] hover:text-white transition-colors">
            <X size={20} weight="bold" />
          </button>
        </div>
        
        {/* Tabs */}
        <div className="flex border-b border-[#1F1F22]">
          <button
            onClick={() => setActiveTab('supported')}
            className={`flex-1 px-4 py-3 text-sm font-mono transition-colors ${
              activeTab === 'supported' ? 'bg-[#161618] text-white border-b-2 border-[#00C805]' : 'text-[#8A8A93] hover:text-white'
            }`}
          >
            <ListBullets size={16} className="inline mr-2" />
            SUPPORTED ({supportedCoins.length})
          </button>
          <button
            onClick={() => setActiveTab('request')}
            className={`flex-1 px-4 py-3 text-sm font-mono transition-colors ${
              activeTab === 'request' ? 'bg-[#161618] text-white border-b-2 border-[#00C805]' : 'text-[#8A8A93] hover:text-white'
            }`}
          >
            <PaperPlaneTilt size={16} className="inline mr-2" />
            REQUEST
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4">
          {activeTab === 'supported' && (
            <>
              {/* ISO 20022 Section */}
              <div className="mb-6">
                <div className="flex items-center gap-2 mb-3">
                  <Certificate size={18} className="text-[#00C805]" weight="fill" />
                  <h3 className="text-white font-semibold text-sm">ISO 20022 COMPLIANT</h3>
                  <span className="text-[10px] border border-[#00C805]/30 text-[#00C805] px-1.5 py-0.5 font-mono">
                    {iso20022Coins.length} COINS
                  </span>
                </div>
                <p className="text-[#8A8A93] text-xs mb-3">
                  These cryptocurrencies are compliant with ISO 20022 financial messaging standard.
                </p>
                <div className="grid grid-cols-3 gap-2">
                  {iso20022Coins.map(coin => (
                    <div key={coin.symbol} className="bg-[#0C0C0E] border border-[#00C805]/30 p-2 text-center">
                      <span className="text-white font-mono text-sm">{coin.symbol}</span>
                      <p className="text-[#8A8A93] text-[10px] truncate">{coin.name}</p>
                    </div>
                  ))}
                </div>
              </div>

              {/* Other Supported Coins */}
              <div>
                <h3 className="text-white font-semibold text-sm mb-3">ALL SUPPORTED COINS</h3>
                <div className="grid grid-cols-4 gap-1 max-h-64 overflow-y-auto">
                  {otherCoins.map(coin => (
                    <div key={coin.symbol} className="bg-[#0C0C0E] border border-[#1F1F22] px-2 py-1.5 text-center">
                      <span className="text-white font-mono text-xs">{coin.symbol}</span>
                    </div>
                  ))}
                </div>
              </div>
            </>
          )}

          {activeTab === 'request' && (
            <>
              {/* Request Form */}
              <div>
                <h3 className="text-white font-semibold text-sm mb-3">REQUEST A NEW COIN</h3>
                <p className="text-[#8A8A93] text-xs mb-4">
                  Can't find a coin? Submit a request and we'll review it and add it to the platform.
                </p>

                {error && (
                  <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 px-3 py-2 text-[#FF3B30] text-sm flex items-center gap-2 mb-4">
                    <Warning size={16} weight="fill" />
                    {error}
                  </div>
                )}

                <div className="space-y-4">
                  <div>
                    <label className="text-xs font-semibold tracking-[0.1em] uppercase text-[#8A8A93] mb-2 block">
                      SYMBOL *
                    </label>
                    <Input
                      value={symbol}
                      onChange={(e) => setSymbol(e.target.value.toUpperCase())}
                      placeholder="e.g. KASPA"
                      className="bg-[#0C0C0E] border-[#1F1F22] text-white font-mono rounded-none"
                      maxLength={10}
                    />
                  </div>
                  
                  <div>
                    <label className="text-xs font-semibold tracking-[0.1em] uppercase text-[#8A8A93] mb-2 block">
                      FULL NAME
                    </label>
                    <Input
                      value={name}
                      onChange={(e) => setName(e.target.value)}
                      placeholder="e.g. Kaspa"
                      className="bg-[#0C0C0E] border-[#1F1F22] text-white rounded-none"
                    />
                  </div>
                  
                  <div>
                    <label className="text-xs font-semibold tracking-[0.1em] uppercase text-[#8A8A93] mb-2 block">
                      WHY ADD THIS COIN?
                    </label>
                    <textarea
                      value={reason}
                      onChange={(e) => setReason(e.target.value)}
                      placeholder="Optional: Tell us why you need this coin..."
                      className="w-full bg-[#0C0C0E] border border-[#1F1F22] text-white p-3 text-sm resize-none h-20"
                      maxLength={200}
                    />
                  </div>

                  <button
                    onClick={handleSubmit}
                    disabled={submitting || !symbol.trim()}
                    className="w-full bg-white text-black py-2.5 font-semibold hover:bg-gray-200 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
                  >
                    {submitting ? (
                      <CircleNotch size={16} className="animate-spin" />
                    ) : (
                      <PaperPlaneTilt size={16} weight="fill" />
                    )}
                    SUBMIT REQUEST
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// Push Notification Section Component
const PushNotificationSection = ({ getAuthHeader }) => {
  const {
    isSupported,
    isSubscribed,
    permission,
    loading,
    error,
    subscribe,
    unsubscribe,
    sendTest
  } = usePushNotifications(getAuthHeader);

  const [testLoading, setTestLoading] = useState(false);
  const [testSuccess, setTestSuccess] = useState(false);
  const [testError, setTestError] = useState('');

  const handleToggle = async () => {
    if (isSubscribed) {
      await unsubscribe();
    } else {
      await subscribe();
    }
  };

  const handleTest = async () => {
    setTestLoading(true);
    setTestError('');
    setTestSuccess(false);
    try {
      await sendTest();
      setTestSuccess(true);
      setTimeout(() => setTestSuccess(false), 3000);
    } catch (err) {
      setTestError(err.response?.data?.detail || 'Failed to send test notification');
      setTimeout(() => setTestError(''), 5000);
    } finally {
      setTestLoading(false);
    }
  };

  if (!isSupported) {
    return null; // Don't show if not supported
  }

  return (
    <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4 mt-4">
      <div className="flex items-center gap-2 mb-3">
        <DeviceMobile size={20} className="text-white" weight="fill" />
        <h3 className="text-white font-semibold text-sm">PUSH NOTIFICATIONS</h3>
        {isSubscribed && (
          <span className="text-[10px] border border-[#00C805]/30 text-[#00C805] px-1.5 py-0.5 ml-2 font-mono">ENABLED</span>
        )}
      </div>

      {error && (
        <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 px-3 py-2 text-[#FF3B30] text-xs mb-3 flex items-center gap-2">
          <Warning size={14} weight="fill" />
          {error}
        </div>
      )}

      {testSuccess && (
        <div className="bg-[#00C805]/10 border border-[#00C805]/30 px-3 py-2 text-[#00C805] text-xs mb-3 flex items-center gap-2">
          <CheckCircle size={14} weight="fill" />
          Test notification sent! Check your device.
        </div>
      )}

      {testError && (
        <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 px-3 py-2 text-[#FF3B30] text-xs mb-3 flex items-center gap-2">
          <Warning size={14} weight="fill" />
          {testError}
        </div>
      )}

      {isSubscribed ? (
        <div className="flex items-center justify-between">
          <p className="text-[#8A8A93] text-sm">Alerts will appear on this device</p>
          <div className="flex gap-2">
            <button 
              onClick={handleTest}
              disabled={testLoading}
              className="text-white hover:text-[#8A8A93] text-sm font-mono transition-colors disabled:opacity-50"
            >
              {testLoading ? <CircleNotch size={14} className="animate-spin" /> : 'TEST'}
            </button>
            <button 
              onClick={handleToggle}
              disabled={loading}
              className="text-[#FF3B30] hover:text-[#FF3B30]/80 text-sm font-mono transition-colors disabled:opacity-50"
            >
              {loading ? <CircleNotch size={14} className="animate-spin" /> : 'DISABLE'}
            </button>
          </div>
        </div>
      ) : (
        <>
          <p className="text-[#8A8A93] text-sm mb-4">
            Get instant price alerts directly on your device — works on mobile and desktop browsers.
          </p>

          {permission === 'denied' ? (
            <div className="bg-[#161618] border border-[#1F1F22] p-3 text-center">
              <p className="text-[#8A8A93] text-sm">
                Notifications are blocked. Enable them in your browser settings.
              </p>
            </div>
          ) : (
            <button
              onClick={handleToggle}
              disabled={loading}
              className="w-full bg-white text-black py-2.5 font-semibold hover:bg-gray-200 transition-colors disabled:opacity-50 flex items-center justify-center gap-2"
            >
              {loading ? (
                <CircleNotch size={16} className="animate-spin" />
              ) : (
                <Bell size={16} weight="fill" />
              )}
              ENABLE PUSH NOTIFICATIONS
            </button>
          )}
        </>
      )}
    </div>
  );
};

// Main Dashboard Component - Professional Design
export const AlertDashboard = ({ getAuthHeader, user, onLogout, portfolioContent, initialView = 'alerts' }) => {
  const [alerts, setAlerts] = useState([]);
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [actionLoading, setActionLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [showCoinLibrary, setShowCoinLibrary] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [activeNav, setActiveNav] = useState(initialView);
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
  const daysRemaining = subscription?.days_remaining ?? 0;
  const trialProgress = daysRemaining > 0 ? Math.min(100, Math.max(0, ((7 - daysRemaining) / 7) * 100)) : 100;

  if (loading) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center">
        <CircleNotch size={32} className="animate-spin text-white" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#050505]">
      {/* Mobile Header - Only visible on small screens */}
      <div className="lg:hidden fixed top-0 left-0 right-0 z-50 bg-[#0C0C0E] border-b border-[#1F1F22] px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 bg-white flex items-center justify-center">
            <ChartLineUp size={14} weight="bold" className="text-black" />
          </div>
          <span className="text-white font-semibold text-xs">
            CRYPTOBAG<span className="text-[#8A8A93]">TRACKER</span>
          </span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setActiveNav('alerts')}
            className={`px-3 py-1.5 text-xs font-mono ${activeNav === 'alerts' ? 'bg-white text-black' : 'text-[#8A8A93]'}`}
          >
            ALERTS
          </button>
          <button
            onClick={() => setActiveNav('portfolio')}
            className={`px-3 py-1.5 text-xs font-mono ${activeNav === 'portfolio' ? 'bg-white text-black' : 'text-[#8A8A93]'}`}
          >
            BAG
          </button>
          <button onClick={onLogout} className="p-1.5 text-[#8A8A93]">
            <SignOut size={18} />
          </button>
        </div>
      </div>

      <div className="flex">
        {/* Sidebar - Hidden on mobile, visible on lg+ */}
        <div className="hidden lg:flex w-64 bg-[#0C0C0E] border-r border-[#1F1F22] flex-col fixed h-screen">
          {/* Logo */}
          <div className="p-4 border-b border-[#1F1F22]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-white flex items-center justify-center">
                <ChartLineUp size={18} weight="bold" className="text-black" />
              </div>
              <span className="text-white font-semibold tracking-tight text-sm">
                CRYPTOBAG<span className="text-[#8A8A93]">TRACKER</span>
              </span>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 p-2">
            <div className="text-xs font-semibold tracking-[0.2em] uppercase text-[#4A4A52] px-3 py-2">
              MENU
            </div>
            <button
              onClick={() => setActiveNav('alerts')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm transition-colors ${
                activeNav === 'alerts' 
                  ? 'bg-white text-black font-medium' 
                  : 'text-[#8A8A93] hover:text-white hover:bg-[#161618]'
              }`}
              data-testid="nav-alerts"
            >
              <Bell size={18} weight={activeNav === 'alerts' ? 'fill' : 'regular'} />
              Price Alerts
            </button>
            <button
              onClick={() => setActiveNav('portfolio')}
              className={`w-full flex items-center gap-3 px-3 py-2.5 text-sm transition-colors ${
                activeNav === 'portfolio' 
                  ? 'bg-white text-black font-medium' 
                  : 'text-[#8A8A93] hover:text-white hover:bg-[#161618]'
              }`}
              data-testid="nav-portfolio"
            >
              <Folder size={18} weight={activeNav === 'portfolio' ? 'fill' : 'regular'} />
              Bag Tracker
              <span className="text-[10px] border border-[#00C805]/30 text-[#00C805] px-1.5 py-0.5 ml-auto font-mono">BETA</span>
            </button>
          </nav>

          {/* Upgrade Card */}
          {subscription?.status !== 'active' && subscription?.status !== 'trialing' && (
            <div className="p-3">
              <div className="bg-[#161618] border border-[#1F1F22] p-4">
                <h4 className="text-white font-semibold text-sm mb-1">UNLOCK ACCESS</h4>
                <p className="text-[#8A8A93] text-xs mb-3">Upgrade for unlimited alerts</p>
                <button 
                  onClick={handleSubscribe}
                  disabled={actionLoading}
                  className="w-full bg-white text-black text-sm py-2 font-semibold hover:bg-gray-200 transition-colors"
                >
                  UPGRADE NOW
                </button>
              </div>
            </div>
          )}

          {/* User Profile */}
          <div className="p-3 border-t border-[#1F1F22]">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 bg-[#161618] border border-[#1F1F22] flex items-center justify-center text-white text-xs font-mono">
                {user?.email?.charAt(0).toUpperCase()}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-white text-sm truncate">{user?.email}</p>
                {subscription?.status === 'trialing' && daysRemaining > 0 && (
                  <p className="text-[#00C805] text-xs font-mono">TRIAL · {daysRemaining}D LEFT</p>
                )}
                {subscription?.status === 'trialing' && daysRemaining === 0 && (
                  <p className="text-[#FFB800] text-xs font-mono">BILLING STARTS TODAY</p>
                )}
                {subscription?.status === 'active' && (
                  <p className="text-[#00C805] text-xs font-mono">PREMIUM</p>
                )}
              </div>
              <button onClick={onLogout} className="text-[#8A8A93] hover:text-white transition-colors" data-testid="logout-btn">
                <SignOut size={18} />
              </button>
            </div>
            {subscription?.status === 'trialing' && daysRemaining > 0 && (
              <div className="mt-2 h-1 bg-[#1F1F22] overflow-hidden">
                <div 
                  className="h-full bg-[#00C805] transition-all duration-500" 
                  style={{ width: `${trialProgress}%` }}
                />
              </div>
            )}
          </div>
        </div>

        {/* Main Content */}
        <div className="flex-1 lg:ml-64 flex flex-col min-h-screen pt-14 lg:pt-0">
        {/* Header - Hidden on mobile (info shown in mobile header) */}
        <header className="hidden lg:flex h-14 border-b border-[#1F1F22] items-center justify-between px-6 bg-[#0C0C0E]">
          <h1 className="text-white text-sm">
            Welcome back, <span className="text-[#8A8A93] font-mono">{user?.email}</span>
          </h1>
          <div className="flex items-center gap-2">
            <button className="p-2 text-[#8A8A93] hover:text-white transition-colors">
              <Question size={20} />
            </button>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 p-4 sm:p-6 overflow-y-auto">
          {activeNav === 'alerts' ? (
            <>
              {/* Trial Banner */}
              {subscription?.status === 'trialing' && daysRemaining > 0 && (
                <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4 mb-6 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Clock size={20} className="text-[#8A8A93]" />
                    <div>
                      <p className="text-white font-medium text-sm">FREE TRIAL</p>
                      <p className="text-[#8A8A93] text-xs font-mono">{daysRemaining} {daysRemaining === 1 ? 'DAY' : 'DAYS'} REMAINING</p>
                    </div>
                  </div>
                  <span className="border border-[#00C805]/30 text-[#00C805] px-3 py-1 text-xs font-mono">ACTIVE</span>
                </div>
              )}
              
              {subscription?.status === 'trialing' && daysRemaining === 0 && (
                <div className="bg-[#0C0C0E] border border-[#FFB800]/30 p-4 mb-6 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <Clock size={20} className="text-[#FFB800]" />
                    <div>
                      <p className="text-white font-medium text-sm">TRIAL ENDING TODAY</p>
                      <p className="text-[#8A8A93] text-xs font-mono">Your subscription begins automatically</p>
                    </div>
                  </div>
                  <span className="border border-[#FFB800]/30 text-[#FFB800] px-3 py-1 text-xs font-mono">AUTO-RENEW</span>
                </div>
              )}

              {/* Status Messages */}
              {error && (
                <div className="bg-[#FF3B30]/10 border border-[#FF3B30]/30 px-4 py-3 text-[#FF3B30] text-sm flex items-center gap-2 mb-4">
                  <Warning size={16} weight="fill" />
                  {error}
                </div>
              )}
              
              {success && (
                <div className="bg-[#00C805]/10 border border-[#00C805]/30 px-4 py-3 text-[#00C805] text-sm flex items-center gap-2 mb-4">
                  <CheckCircle size={16} weight="fill" />
                  {success}
                </div>
              )}

              {/* Alerts Header */}
              <div className="mb-4">
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <h2 className="text-white font-semibold text-lg tracking-tight">YOUR ALERTS</h2>
                    <p className="text-[#8A8A93] text-xs font-mono">{alerts.length} CONFIGURED</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowCoinLibrary(true)}
                    className="flex-1 sm:flex-none border border-[#1F1F22] text-[#8A8A93] px-3 py-2.5 text-xs sm:text-sm font-mono flex items-center justify-center gap-2 hover:bg-[#161618] hover:text-white transition-colors"
                    data-testid="coin-library-btn"
                  >
                    <ListBullets size={16} />
                    COINS
                  </button>
                  {canCreateAlerts && (
                    <button
                      onClick={() => setShowCreateModal(true)}
                      className="flex-1 sm:flex-none bg-white text-black px-3 sm:px-4 py-2.5 text-xs sm:text-sm font-semibold flex items-center justify-center gap-2 hover:bg-gray-200 transition-colors"
                      data-testid="new-alert-btn"
                    >
                      <Plus size={16} weight="bold" />
                      NEW ALERT
                    </button>
                  )}
                </div>
              </div>

              {/* Alerts List */}
              {alerts.length === 0 ? (
                <div className="bg-[#0C0C0E] border border-[#1F1F22] py-12 text-center">
                  <Bell size={40} className="mx-auto text-[#4A4A52] mb-3" />
                  <p className="text-white font-medium mb-1">NO ALERTS YET</p>
                  <p className="text-[#8A8A93] text-sm mb-4">Create your first alert to get started</p>
                  {canCreateAlerts && (
                    <button 
                      onClick={() => setShowCreateModal(true)}
                      className="bg-white text-black px-4 py-2 text-sm font-semibold hover:bg-gray-200 transition-colors"
                    >
                      CREATE ALERT
                    </button>
                  )}
                </div>
              ) : (
                <>
                  {/* Desktop Table - Hidden on mobile */}
                  <div className="hidden md:block border border-[#1F1F22] overflow-x-auto">
                    {/* Table Header */}
                    <div className="grid grid-cols-12 gap-4 px-4 py-2 bg-[#0C0C0E] border-b border-[#1F1F22] text-xs font-semibold tracking-[0.1em] uppercase text-[#8A8A93] min-w-[700px]">
                      <div className="col-span-3">ASSET</div>
                      <div className="col-span-2">CONDITION</div>
                      <div className="col-span-2 text-right">TARGET</div>
                      <div className="col-span-2 text-right">CURRENT</div>
                      <div className="col-span-1 text-center">STATUS</div>
                      <div className="col-span-2 text-right">ACTIONS</div>
                    </div>
                    
                    {/* Table Rows */}
                    {alerts.map((alert) => {
                      const typeInfo = ALERT_TYPE_LABELS[alert.alert_type] || {};
                      return (
                        <div key={alert.alert_id} className="grid grid-cols-12 gap-4 px-4 py-3 border-b border-[#1F1F22] hover:bg-[#0C0C0E] transition-colors items-center min-w-[700px]">
                          <div className="col-span-3 flex items-center gap-3">
                            <TokenBadge symbol={alert.asset_symbol} />
                            <div>
                              <span className="text-white font-mono text-sm">{alert.asset_symbol}</span>
                              <span className="text-[10px] border border-[#1F1F22] text-[#8A8A93] px-1.5 py-0.5 ml-2 font-mono">CRYPTO</span>
                            </div>
                          </div>
                          <div className="col-span-2">
                            <span className={`font-mono text-sm ${typeInfo.color || 'text-white'}`}>
                              {typeInfo.label}
                            </span>
                          </div>
                          <div className="col-span-2 text-right font-mono text-white tabular-nums">
                            {alert.alert_type.includes('percent') ? `${alert.target_value}%` : formatPrice(alert.target_value)}
                          </div>
                          <div className="col-span-2 text-right font-mono text-[#8A8A93] tabular-nums">
                            {formatPrice(alert.current_price)}
                          </div>
                          <div className="col-span-1 text-center">
                            <span className={`text-[10px] px-2 py-0.5 font-mono border ${
                              alert.status === 'active' 
                                ? 'border-[#00C805]/30 text-[#00C805] bg-[#00C805]/10' 
                                : 'border-[#1F1F22] text-[#8A8A93]'
                            }`}>
                              {alert.status.toUpperCase()}
                            </span>
                          </div>
                          <div className="col-span-2 flex items-center justify-end gap-1">
                            <button 
                              onClick={() => toggleAlert(alert.alert_id)}
                              className="p-2 text-[#8A8A93] hover:text-white transition-colors"
                              data-testid={`toggle-alert-${alert.alert_id}`}
                            >
                              {alert.status === 'active' ? <Pause size={16} /> : <Play size={16} weight="fill" />}
                            </button>
                            <button 
                              onClick={() => deleteAlert(alert.alert_id)}
                              className="p-2 text-[#8A8A93] hover:text-[#FF3B30] transition-colors"
                              data-testid={`delete-alert-${alert.alert_id}`}
                            >
                              <Trash size={16} />
                            </button>
                          </div>
                        </div>
                      );
                    })}
                  </div>

                  {/* Mobile Cards - Visible only on mobile */}
                  <div className="md:hidden space-y-3">
                    {alerts.map((alert) => {
                      const typeInfo = ALERT_TYPE_LABELS[alert.alert_type] || {};
                      return (
                        <div key={alert.alert_id} className="bg-[#0C0C0E] border border-[#1F1F22] p-4">
                          {/* Card Header */}
                          <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-3">
                              <TokenBadge symbol={alert.asset_symbol} />
                              <div>
                                <span className="text-white font-mono text-sm">{alert.asset_symbol}</span>
                                <span className={`text-[10px] px-2 py-0.5 font-mono border ml-2 ${
                                  alert.status === 'active' 
                                    ? 'border-[#00C805]/30 text-[#00C805] bg-[#00C805]/10' 
                                    : 'border-[#1F1F22] text-[#8A8A93]'
                                }`}>
                                  {alert.status.toUpperCase()}
                                </span>
                              </div>
                            </div>
                            <div className="flex items-center gap-1">
                              <button 
                                onClick={() => toggleAlert(alert.alert_id)}
                                className="p-2 text-[#8A8A93] hover:text-white transition-colors"
                                data-testid={`toggle-alert-mobile-${alert.alert_id}`}
                              >
                                {alert.status === 'active' ? <Pause size={18} /> : <Play size={18} weight="fill" />}
                              </button>
                              <button 
                                onClick={() => deleteAlert(alert.alert_id)}
                                className="p-2 text-[#8A8A93] hover:text-[#FF3B30] transition-colors"
                                data-testid={`delete-alert-mobile-${alert.alert_id}`}
                              >
                                <Trash size={18} />
                              </button>
                            </div>
                          </div>
                          
                          {/* Card Body */}
                          <div className="grid grid-cols-2 gap-3 text-sm">
                            <div>
                              <p className="text-[#8A8A93] text-xs mb-1">CONDITION</p>
                              <span className={`font-mono ${typeInfo.color || 'text-white'}`}>
                                {typeInfo.label}
                              </span>
                            </div>
                            <div className="text-right">
                              <p className="text-[#8A8A93] text-xs mb-1">TARGET</p>
                              <span className="font-mono text-white tabular-nums">
                                {alert.alert_type.includes('percent') ? `${alert.target_value}%` : formatPrice(alert.target_value)}
                              </span>
                            </div>
                            <div className="col-span-2 pt-2 border-t border-[#1F1F22]">
                              <div className="flex justify-between items-center">
                                <span className="text-[#8A8A93] text-xs">CURRENT PRICE</span>
                                <span className="font-mono text-[#8A8A93] tabular-nums">
                                  {formatPrice(alert.current_price)}
                                </span>
                              </div>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              {/* Telegram Section */}
              {canCreateAlerts && (
                <div className="bg-[#0C0C0E] border border-[#1F1F22] p-4 mt-6">
                  <div className="flex items-center gap-2 mb-3">
                    <TelegramLogo size={20} className="text-white" weight="fill" />
                    <h3 className="text-white font-semibold text-sm">TELEGRAM NOTIFICATIONS</h3>
                    {telegramStatus?.connected && (
                      <span className="text-[10px] border border-[#00C805]/30 text-[#00C805] px-1.5 py-0.5 ml-2 font-mono">CONNECTED</span>
                    )}
                  </div>
                  
                  {telegramStatus?.connected ? (
                    <div className="flex items-center justify-between">
                      <p className="text-[#8A8A93] text-sm">Alerts will be sent to your Telegram</p>
                      <div className="flex gap-2">
                        <button onClick={testTelegram} className="text-white hover:text-[#8A8A93] text-sm font-mono transition-colors">
                          TEST
                        </button>
                        <button onClick={disconnectTelegram} className="text-[#FF3B30] hover:text-[#FF3B30]/80 text-sm font-mono transition-colors">
                          DISCONNECT
                        </button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <p className="text-[#8A8A93] text-sm mb-4">
                        Get instant alerts on Telegram — unlimited, no rate limits.
                      </p>
                      
                      {/* Step by step instructions */}
                      <div className="bg-[#161618] border border-[#1F1F22] p-4 mb-4">
                        <p className="text-xs font-semibold tracking-[0.1em] uppercase text-[#8A8A93] mb-3">HOW TO CONNECT</p>
                        
                        <div className="space-y-3 font-mono text-sm">
                          <div className="flex gap-3">
                            <span className="text-[#00C805] font-bold">1.</span>
                            <div>
                              <p className="text-white">Open Telegram and search for <a href="https://t.me/cryptobagtrackerbot" target="_blank" rel="noopener noreferrer" className="text-[#00C805] underline hover:text-[#00C805]/80">@cryptobagtrackerbot</a></p>
                              <p className="text-[#8A8A93] text-xs mt-1">Or click the link to open directly</p>
                            </div>
                          </div>
                          
                          <div className="flex gap-3">
                            <span className="text-[#00C805] font-bold">2.</span>
                            <div>
                              <p className="text-white">Click "Start" or send <span className="bg-[#0C0C0E] px-1.5 py-0.5 text-[#00C805]">/start</span></p>
                              <p className="text-[#8A8A93] text-xs mt-1">The bot will reply with your Chat ID</p>
                            </div>
                          </div>
                          
                          <div className="flex gap-3">
                            <span className="text-[#00C805] font-bold">3.</span>
                            <div>
                              <p className="text-white">Copy the number the bot sends you</p>
                              <p className="text-[#8A8A93] text-xs mt-1">It looks like: <span className="text-white">123456789</span> (a 9-10 digit number)</p>
                            </div>
                          </div>
                        </div>
                      </div>
                      
                      <div className="flex gap-2">
                        <Input
                          value={telegramChatId}
                          onChange={(e) => setTelegramChatId(e.target.value)}
                          placeholder="Paste your Chat ID here (e.g. 123456789)"
                          className="bg-[#161618] border-[#1F1F22] text-white flex-1 font-mono rounded-none"
                        />
                        <button
                          onClick={connectTelegram}
                          disabled={connectingTelegram || !telegramChatId.trim()}
                          className="bg-white text-black disabled:opacity-50 px-4 py-2 text-sm font-semibold hover:bg-gray-200 transition-colors"
                        >
                          {connectingTelegram ? <CircleNotch size={16} className="animate-spin" /> : 'CONNECT'}
                        </button>
                      </div>
                    </>
                  )}
                </div>
              )}

              {/* Push Notifications Section */}
              {canCreateAlerts && <PushNotificationSection getAuthHeader={getAuthHeader} />}
            </>
          ) : (
            /* Portfolio/Bag Tracker Content */
            <div data-testid="portfolio-content">
              {portfolioContent}
            </div>
          )}
        </main>

        {/* Footer */}
        <footer className="h-auto sm:h-10 border-t border-[#1F1F22] flex flex-col sm:flex-row items-center justify-between px-4 sm:px-6 py-2 sm:py-0 text-[#4A4A52] text-xs font-mono bg-[#0C0C0E] gap-1 sm:gap-0">
          <span>© 2026 CRYPTOBAGTRACKER</span>
          <span className="hidden sm:inline">TRACK YOUR BAGS. KNOW YOUR WORTH.</span>
        </footer>
      </div>

      </div>

      <CreateAlertModal
        isOpen={showCreateModal}
        onClose={() => setShowCreateModal(false)}
        onCreated={handleAlertCreated}
        getAuthHeader={getAuthHeader}
      />

      <RequestCoinModal
        isOpen={showCoinLibrary}
        onClose={() => setShowCoinLibrary(false)}
        getAuthHeader={getAuthHeader}
        onSuccess={(msg) => {
          setSuccess(msg);
          setTimeout(() => setSuccess(''), 5000);
        }}
      />
    </div>
  );
};

export default AlertDashboard;
