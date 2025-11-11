import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, Bitcoin, Crown, Check } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const UpgradeModal = ({ isOpen, onClose }) => {
  const [selectedTier, setSelectedTier] = useState('premium');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { getAuthHeader } = useAuth();

  const tiers = {
    premium: {
      name: 'Premium',
      price: 19,
      features: [
        'Unlimited wallet analyses',
        'CSV export',
        'Priority support',
        'Advanced analytics'
      ]
    },
    pro: {
      name: 'Pro',
      price: 49,
      features: [
        'Everything in Premium',
        'Real-time alerts',
        'Multi-chain support',
        'API access',
        'Custom reports'
      ]
    }
  };

  const handleUpgrade = async () => {
    setError('');
    setLoading(true);

    try {
      const originUrl = window.location.origin;
      
      const response = await axios.post(
        `${API}/payments/create-upgrade`,
        { 
          tier: selectedTier,
          origin_url: originUrl
        },
        { headers: getAuthHeader() }
      );
      
      // Redirect to Stripe Checkout
      if (response.data.url) {
        window.location.href = response.data.url;
      } else {
        throw new Error('No checkout URL received');
      }
      
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create payment. Please try again.');
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-3xl bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto" data-testid="upgrade-modal">
        <DialogHeader>
          <DialogTitle className="text-white text-2xl flex items-center gap-2">
            <Crown className="w-6 h-6 text-yellow-400" />
            Upgrade Your Subscription
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Choose a plan and pay securely with Stripe
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
            {/* Tier Selection */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {Object.entries(tiers).map(([key, tier]) => (
                <div
                  key={key}
                  onClick={() => setSelectedTier(key)}
                  className={`p-6 rounded-lg border-2 cursor-pointer transition-all ${
                    selectedTier === key
                      ? 'border-purple-500 bg-purple-900/20'
                      : 'border-slate-600 bg-slate-700/30 hover:border-slate-500'
                  }`}
                  data-testid={`tier-${key}`}
                >
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-xl font-bold text-white">{tier.name}</h3>
                    <Badge className="bg-purple-600">${tier.price}/mo</Badge>
                  </div>
                  <ul className="space-y-2">
                    {tier.features.map((feature, idx) => (
                      <li key={idx} className="flex items-center gap-2 text-gray-300 text-sm">
                        <Check className="w-4 h-4 text-green-400" />
                        {feature}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>

            {error && (
              <Alert className="bg-red-900/20 border-red-900 text-red-300" data-testid="payment-error">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex items-center justify-center gap-2 text-gray-400 text-sm">
              <Crown className="w-5 h-5 text-purple-400" />
              <span>Secure payment powered by Stripe</span>
            </div>

            <Button
              onClick={handleUpgrade}
              disabled={loading}
              className="w-full bg-purple-600 hover:bg-purple-700 h-12 text-lg"
              data-testid="create-payment-button"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Creating Payment...
                </>
              ) : (
                <>
                  Upgrade to {tiers[selectedTier].name} - ${tiers[selectedTier].price}/mo
                </>
              )}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
