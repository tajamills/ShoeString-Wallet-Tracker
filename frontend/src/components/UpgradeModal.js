import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Loader2, Crown, Check, Zap, Shield, FileText, Globe, Tag, CheckCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const UpgradeModal = ({ isOpen, onClose }) => {
  const { user, getAuthHeader } = useAuth();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [affiliateCode, setAffiliateCode] = useState('');
  const [affiliateValid, setAffiliateValid] = useState(null);
  const [validatingCode, setValidatingCode] = useState(false);

  const features = [
    { icon: Globe, text: 'Unlimited wallet analyses' },
    { icon: Zap, text: 'All 6 blockchains (ETH, BTC, POLY, ARB, BSC, SOL)' },
    { icon: FileText, text: 'Full CSV export & tax reports' },
    { icon: Shield, text: 'Cost basis & capital gains (FIFO)' },
    { icon: Crown, text: 'Form 8949 & Schedule D export' },
    { icon: Check, text: 'Bitcoin xPub HD wallet support' },
    { icon: Check, text: 'Analyze All Chains feature' },
    { icon: Check, text: 'Transaction categorization' },
    { icon: Check, text: 'Priority support' },
  ];

  const validateAffiliateCode = async (code) => {
    if (!code || code.length < 3) {
      setAffiliateValid(null);
      return;
    }

    setValidatingCode(true);
    try {
      const response = await axios.get(`${API}/affiliate/validate/${code}`);
      setAffiliateValid(response.data);
    } catch (err) {
      setAffiliateValid({ valid: false, message: 'Error validating code' });
    } finally {
      setValidatingCode(false);
    }
  };

  const handleCodeChange = (e) => {
    const code = e.target.value.toUpperCase();
    setAffiliateCode(code);
    
    // Debounce validation
    if (code.length >= 3) {
      const timer = setTimeout(() => validateAffiliateCode(code), 500);
      return () => clearTimeout(timer);
    } else {
      setAffiliateValid(null);
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
          tier: 'unlimited',
          origin_url: originUrl,
          affiliate_code: affiliateValid?.valid ? affiliateCode : null
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

  // Check if user already has unlimited
  const hasUnlimited = user?.subscription_tier === 'unlimited' && user?.subscription_status === 'active';

  // Calculate final price
  const basePrice = 100.88;
  const discount = affiliateValid?.valid ? 10 : 0;
  const finalPrice = basePrice - discount;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto" data-testid="upgrade-modal">
        <DialogHeader>
          <DialogTitle className="text-white text-2xl flex items-center gap-2">
            <Crown className="w-6 h-6 text-yellow-400" />
            Upgrade to Unlimited
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Get full access to all features for one year
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Pricing Card */}
          <div className="p-6 rounded-lg border-2 border-yellow-500 bg-gradient-to-br from-yellow-900/20 to-orange-900/20">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-2xl font-bold text-white">Unlimited Access</h3>
              <div className="text-right">
                {discount > 0 && (
                  <span className="text-gray-400 line-through text-sm mr-2">${basePrice}/year</span>
                )}
                <Badge className="bg-yellow-600 text-lg px-3 py-1">
                  ${finalPrice.toFixed(2)}/year
                </Badge>
              </div>
            </div>
            <p className="text-gray-400 text-sm mb-4">
              One payment. Full year. Unlimited everything.
            </p>
            
            <ul className="space-y-3">
              {features.map((feature, idx) => (
                <li key={idx} className="flex items-center gap-3 text-gray-300">
                  <feature.icon className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                  <span>{feature.text}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Affiliate Code Input */}
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <label className="flex items-center gap-2 text-sm font-medium text-gray-300 mb-2">
              <Tag className="w-4 h-4 text-purple-400" />
              Have a referral code? Get $10 off!
            </label>
            <div className="flex gap-2">
              <Input
                value={affiliateCode}
                onChange={handleCodeChange}
                placeholder="Enter code (e.g., JOHN10)"
                className="bg-slate-800 border-slate-600 text-white uppercase"
                maxLength={20}
                data-testid="upgrade-affiliate-code-input"
              />
              {validatingCode && (
                <Loader2 className="w-5 h-5 animate-spin text-gray-400 my-auto" />
              )}
            </div>
            
            {affiliateValid && (
              <div className={`mt-2 text-sm flex items-center gap-2 ${affiliateValid.valid ? 'text-green-400' : 'text-red-400'}`} data-testid="affiliate-validation-status">
                {affiliateValid.valid ? (
                  <>
                    <CheckCircle className="w-4 h-4" />
                    {affiliateValid.message}
                  </>
                ) : (
                  affiliateValid.message
                )}
              </div>
            )}
          </div>

          {/* Free tier info */}
          <div className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
            <p className="text-sm text-gray-400">
              <span className="text-white font-semibold">Free tier:</span> 1 wallet analysis to try before you buy.
              Upgrade for unlimited analyses and all premium features.
            </p>
          </div>

          {error && (
            <Alert className="bg-red-900/20 border-red-900 text-red-300" data-testid="payment-error">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <div className="flex items-center justify-center gap-2 text-gray-400 text-sm">
            <Shield className="w-5 h-5 text-green-400" />
            <span>Secure payment powered by Stripe</span>
          </div>

          {hasUnlimited ? (
            <Alert className="bg-green-900/20 border-green-700 text-green-300">
              <Check className="h-4 w-4" />
              <AlertDescription>
                You already have an active Unlimited subscription
              </AlertDescription>
            </Alert>
          ) : (
            <Button
              onClick={handleUpgrade}
              disabled={loading}
              className="w-full bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-700 hover:to-orange-700 h-14 text-lg font-semibold"
              data-testid="create-payment-button"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                  Creating Payment...
                </>
              ) : (
                <>
                  <Crown className="mr-2 h-5 w-5" />
                  Get Unlimited Access - ${finalPrice.toFixed(2)}/year
                </>
              )}
            </Button>
          )}

          <p className="text-xs text-gray-500 text-center">
            By purchasing, you agree to our Terms of Service. Subscription auto-renews annually.
            Cancel anytime from your account settings.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
