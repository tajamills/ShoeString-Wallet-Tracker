import React, { useState } from 'react';
import axios from 'axios';
import { AlertTriangle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export const DowngradeModal = ({ isOpen, onClose, user, getAuthHeader, onSuccess }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false);

  const getDowngradeInfo = () => {
    if (user?.subscription_tier === 'pro') {
      return {
        from: 'Pro',
        to: 'Premium',
        newPrice: '$19/month',
        loses: ['Custom reports', 'Request new chains']
      };
    } else if (user?.subscription_tier === 'premium') {
      return {
        from: 'Premium',
        to: 'Free',
        newPrice: 'Free',
        loses: ['Unlimited analyses', 'Multi-chain support', 'CSV export', 'Exchange detection', 'Saved wallets (non-Ethereum)']
      };
    }
    return null;
  };

  const handleDowngrade = async () => {
    setError('');
    setLoading(true);

    try {
      const downgradeInfo = getDowngradeInfo();
      const newTier = downgradeInfo.to.toLowerCase();

      // Update user subscription tier
      await axios.post(
        `${API}/api/auth/downgrade`,
        { new_tier: newTier },
        { headers: getAuthHeader() }
      );

      setConfirmed(true);
      setTimeout(() => {
        onClose();
        // Pass the new tier to the success callback
        onSuccess && onSuccess(newTier);
        setConfirmed(false);
      }, 2000);

    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to downgrade. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const downgradeInfo = getDowngradeInfo();

  if (!downgradeInfo) {
    return null;
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-slate-800 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-400" />
            Downgrade Subscription
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Are you sure you want to downgrade?
          </DialogDescription>
        </DialogHeader>

        {confirmed ? (
          <Alert className="bg-green-900/20 border-green-700 text-green-300">
            <AlertDescription>
              ✅ Subscription downgraded successfully!
            </AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-4">
            <div className="bg-slate-900/50 rounded-lg p-4 space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Current Plan:</span>
                <span className="text-white font-semibold">{downgradeInfo.from}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">New Plan:</span>
                <span className="text-white font-semibold">{downgradeInfo.to}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">New Price:</span>
                <span className="text-white font-semibold">{downgradeInfo.newPrice}</span>
              </div>
            </div>

            <Alert className="bg-yellow-900/20 border-yellow-700 text-yellow-300">
              <AlertDescription>
                <div className="font-semibold mb-2">You will lose access to:</div>
                <ul className="list-disc list-inside space-y-1 text-sm">
                  {downgradeInfo.loses.map((feature, idx) => (
                    <li key={idx}>{feature}</li>
                  ))}
                </ul>
              </AlertDescription>
            </Alert>

            {error && (
              <Alert className="bg-red-900/20 border-red-700 text-red-300">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex gap-2">
              <Button
                onClick={handleDowngrade}
                disabled={loading}
                variant="destructive"
                className="flex-1 bg-red-600 hover:bg-red-700"
              >
                {loading ? 'Downgrading...' : 'Yes, Downgrade'}
              </Button>
              <Button
                onClick={onClose}
                variant="outline"
                className="flex-1 border-slate-600"
              >
                Cancel
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
