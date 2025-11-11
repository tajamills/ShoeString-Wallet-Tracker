import React, { useState } from 'react';
import axios from 'axios';
import { Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Alert, AlertDescription } from '@/components/ui/alert';

const API = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

export const ChainRequestModal = ({ isOpen, onClose, getAuthHeader, userTier }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);
  const [formData, setFormData] = useState({
    chain_name: '',
    reason: ''
  });

  const handleSubmit = async () => {
    setError('');
    setLoading(true);

    try {
      await axios.post(
        `${API}/api/chain-request`,
        formData,
        { headers: getAuthHeader() }
      );
      
      setSuccess(true);
      setTimeout(() => {
        onClose();
        setSuccess(false);
        setFormData({ chain_name: '', reason: '' });
      }, 2000);
      
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit request');
    } finally {
      setLoading(false);
    }
  };

  if (userTier === 'free') {
    return (
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="sm:max-w-md bg-slate-800 border-slate-700">
          <DialogHeader>
            <DialogTitle className="text-white flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-yellow-400" />
              Premium Feature
            </DialogTitle>
            <DialogDescription className="text-gray-400">
              Chain requests are only available for Premium and Pro subscribers
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4">
            <Alert className="bg-purple-900/20 border-purple-700 text-purple-300">
              <AlertDescription>
                Upgrade to Premium or Pro to request support for additional blockchains!
              </AlertDescription>
            </Alert>

            <Button
              onClick={onClose}
              className="w-full bg-purple-600 hover:bg-purple-700"
            >
              Close
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-slate-800 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-yellow-400" />
            Request New Blockchain
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Let us know which blockchain you'd like us to support
          </DialogDescription>
        </DialogHeader>

        {success ? (
          <Alert className="bg-green-900/20 border-green-700 text-green-300">
            <AlertDescription>
              ✅ Request submitted successfully! We'll review it and get back to you.
            </AlertDescription>
          </Alert>
        ) : (
          <div className="space-y-4">
            <div>
              <Label htmlFor="chain_name" className="text-gray-300">Blockchain Name *</Label>
              <Input
                id="chain_name"
                placeholder="e.g., Polygon, Avalanche, Fantom..."
                value={formData.chain_name}
                onChange={(e) => setFormData({...formData, chain_name: e.target.value})}
                className="bg-slate-900 border-slate-600 text-white"
              />
            </div>

            <div>
              <Label htmlFor="reason" className="text-gray-300">Why do you need this? (Optional)</Label>
              <textarea
                id="reason"
                placeholder="Tell us how this would help you..."
                value={formData.reason}
                onChange={(e) => setFormData({...formData, reason: e.target.value})}
                className="w-full bg-slate-900 border border-slate-600 text-white rounded-md px-3 py-2 min-h-[80px]"
                rows="3"
              />
            </div>

            {error && (
              <Alert className="bg-red-900/20 border-red-700 text-red-300">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex gap-2">
              <Button
                onClick={handleSubmit}
                disabled={loading || !formData.chain_name}
                className="flex-1 bg-purple-600 hover:bg-purple-700"
              >
                {loading ? 'Submitting...' : 'Submit Request'}
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
