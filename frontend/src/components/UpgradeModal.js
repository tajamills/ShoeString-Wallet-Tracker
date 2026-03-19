import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Crown, Check, Zap, Shield, FileText, Globe, Gift } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

// Direct Stripe Payment Link with 45-day free trial
const STRIPE_PAYMENT_LINK = 'https://buy.stripe.com/6oU3cu0D2bB7bVC2Sr3gk06';

export const UpgradeModal = ({ isOpen, onClose }) => {
  const { user } = useAuth();

  const features = [
    { icon: Globe, text: 'Unlimited wallet analyses' },
    { icon: Zap, text: 'All 14 blockchains (ETH, BTC, SOL, ALGO, XRP, XLM + more)' },
    { icon: FileText, text: 'Full CSV export & tax reports' },
    { icon: Shield, text: 'Cost basis & capital gains (FIFO)' },
    { icon: Crown, text: 'Form 8949 & Schedule D export' },
    { icon: Check, text: 'Chain of Custody analysis' },
    { icon: Check, text: 'Exchange CSV import' },
    { icon: Check, text: 'Transaction categorization' },
    { icon: Check, text: 'Priority support' },
  ];

  const handleUpgrade = () => {
    // Add user email as prefill if available
    let paymentUrl = STRIPE_PAYMENT_LINK;
    if (user?.email) {
      paymentUrl += `?prefilled_email=${encodeURIComponent(user.email)}`;
    }
    window.location.href = paymentUrl;
  };

  // Check if user already has unlimited
  const hasUnlimited = user?.subscription_tier === 'unlimited' && user?.subscription_status === 'active';

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-lg bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto" data-testid="upgrade-modal">
        <DialogHeader>
          <DialogTitle className="text-white text-2xl flex items-center gap-2">
            <Crown className="w-6 h-6 text-yellow-400" />
            Upgrade to Unlimited
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Get full access to all features
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Beta Trial Banner */}
          <div className="bg-gradient-to-r from-green-900/50 to-emerald-900/50 border border-green-500/50 rounded-lg p-4 text-center">
            <div className="flex items-center justify-center gap-2 mb-2">
              <Gift className="w-5 h-5 text-green-400" />
              <span className="text-green-300 font-bold text-lg">45 Days FREE Trial!</span>
            </div>
            <p className="text-green-200 text-sm">
              No charge for 45 days. Cancel anytime during trial.
            </p>
          </div>

          {/* Beta26 Promo */}
          <div className="bg-gradient-to-r from-yellow-900/50 to-orange-900/50 border border-yellow-500/50 rounded-lg p-4 text-center">
            <p className="text-yellow-300 text-sm font-medium">
              ⭐ First 50 customers: Use code <span className="bg-yellow-700 text-white px-2 py-0.5 rounded font-bold mx-1">Beta26</span> at checkout for <span className="text-white font-bold">50% off FOREVER</span>
            </p>
          </div>

          {/* Pricing Card */}
          <div className="p-6 rounded-lg border-2 border-yellow-500 bg-gradient-to-br from-yellow-900/20 to-orange-900/20">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-2xl font-bold text-white">Unlimited Access</h3>
              <div className="text-right">
                <Badge className="bg-yellow-600 text-lg px-3 py-1">
                  $100.88/year
                </Badge>
                <p className="text-green-400 text-xs mt-1">After 45-day trial</p>
              </div>
            </div>
            
            <ul className="space-y-3">
              {features.map((feature, idx) => (
                <li key={idx} className="flex items-center gap-3 text-gray-300">
                  <feature.icon className="w-5 h-5 text-yellow-400 flex-shrink-0" />
                  <span>{feature.text}</span>
                </li>
              ))}
            </ul>
          </div>

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
              className="w-full bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-700 hover:to-orange-700 h-14 text-lg font-semibold"
              data-testid="create-payment-button"
            >
              <Crown className="mr-2 h-5 w-5" />
              Start 45-Day Free Trial
            </Button>
          )}

          <p className="text-xs text-gray-500 text-center">
            No charge for 45 days. After trial, $100.88/year (or 50% off with Beta26).
            Cancel anytime. By subscribing, you agree to our Terms of Service.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
