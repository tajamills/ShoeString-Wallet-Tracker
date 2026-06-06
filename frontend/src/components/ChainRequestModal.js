/**
 * ChainRequestModal - Request a new blockchain to be added
 * Available for Unlimited users only
 */
import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { 
  Loader2, 
  Send, 
  CheckCircle,
  Clock,
  Plus
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const ChainRequestModal = ({ isOpen, onClose, getAuthHeader, userTier }) => {
  const [loading, setLoading] = useState(false);
  const [formData, setFormData] = useState({
    chain_name: '',
    chain_symbol: '',
    reason: '',
    sample_address: ''
  });
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!formData.chain_name.trim()) {
      setError('Please enter the chain name');
      return;
    }
    
    setLoading(true);
    setError('');
    
    try {
      await axios.post(`${API}/chains/request`, formData, {
        headers: getAuthHeader()
      });
      
      setSuccess(true);
      setFormData({ chain_name: '', chain_symbol: '', reason: '', sample_address: '' });
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to submit request');
    } finally {
      setLoading(false);
    }
  };

  const popularRequests = [
    { name: 'Cardano', symbol: 'ADA' },
    { name: 'XRP Ledger', symbol: 'XRP' },
    { name: 'Tron', symbol: 'TRX' },
    { name: 'Cosmos Hub', symbol: 'ATOM' },
    { name: 'Near Protocol', symbol: 'NEAR' },
    { name: 'Aptos', symbol: 'APT' },
    { name: 'Sui', symbol: 'SUI' },
    { name: 'TON', symbol: 'TON' },
    { name: 'Cronos', symbol: 'CRO' },
    { name: 'Hedera', symbol: 'HBAR' }
  ];

  const selectPopular = (chain) => {
    setFormData({
      ...formData,
      chain_name: chain.name,
      chain_symbol: chain.symbol
    });
  };

  if (userTier === 'free') {
    return (
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="bg-[#050505] border-[#1F1F22]">
          <DialogHeader>
            <DialogTitle className="text-white">Request a Chain</DialogTitle>
          </DialogHeader>
          <Alert className="bg-amber-900/30 border-amber-600">
            <AlertDescription className="text-amber-200">
              Chain requests are available for <strong>Unlimited subscribers</strong> only.
              Upgrade to request new chains - we add them within 48 hours!
            </AlertDescription>
          </Alert>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-[#050505] border-[#1F1F22] max-w-lg">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <Plus className="w-5 h-5 text-[#00C805]" />
            Request a Chain
          </DialogTitle>
          <DialogDescription className="text-[#8A8A93]">
            Don't see your blockchain? Request it and we'll add it within 48 hours!
          </DialogDescription>
        </DialogHeader>

        {success ? (
          <div className="text-center py-6">
            <CheckCircle className="w-16 h-16 text-[#00C805] mx-auto mb-4" />
            <h3 className="text-xl text-white font-semibold mb-2">Request Submitted!</h3>
            <p className="text-[#8A8A93] mb-4">
              We'll review your request and typically add new chains within 48 hours.
              You'll receive an email notification when it's ready.
            </p>
            <div className="flex items-center justify-center gap-2 text-sm text-[#4A4A52]">
              <Clock className="w-4 h-4" />
              Estimated: 48 hours
            </div>
            <Button 
              onClick={() => { setSuccess(false); onClose(); }}
              className="mt-4 bg-white text-black hover:bg-gray-200"
            >
              Done
            </Button>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-4">
            {/* Quick Select Popular Chains */}
            <div>
              <label className="text-sm text-[#8A8A93] mb-2 block">Quick Select:</label>
              <div className="flex flex-wrap gap-2">
                {popularRequests.slice(0, 5).map((chain) => (
                  <Badge
                    key={chain.symbol}
                    className="bg-[#161618] hover:bg-[#1F1F22] cursor-pointer transition-colors"
                    onClick={() => selectPopular(chain)}
                  >
                    {chain.name} ({chain.symbol})
                  </Badge>
                ))}
              </div>
            </div>

            {/* Chain Name */}
            <div>
              <label className="text-sm text-[#8A8A93] mb-1 block">Chain Name *</label>
              <Input
                value={formData.chain_name}
                onChange={(e) => setFormData({...formData, chain_name: e.target.value})}
                placeholder="e.g., Cardano, XRP Ledger, Tron"
                className="bg-[#0C0C0E] border-[#1F1F22] text-white"
                required
              />
            </div>

            {/* Symbol */}
            <div>
              <label className="text-sm text-[#8A8A93] mb-1 block">Symbol (Optional)</label>
              <Input
                value={formData.chain_symbol}
                onChange={(e) => setFormData({...formData, chain_symbol: e.target.value.toUpperCase()})}
                placeholder="e.g., ADA, XRP, TRX"
                className="bg-[#0C0C0E] border-[#1F1F22] text-white"
                maxLength={10}
              />
            </div>

            {/* Sample Address */}
            <div>
              <label className="text-sm text-[#8A8A93] mb-1 block">Sample Address (Optional)</label>
              <Input
                value={formData.sample_address}
                onChange={(e) => setFormData({...formData, sample_address: e.target.value})}
                placeholder="A wallet address on this chain"
                className="bg-[#0C0C0E] border-[#1F1F22] text-white"
              />
              <p className="text-xs text-[#4A4A52] mt-1">Helps us test the integration faster</p>
            </div>

            {/* Reason */}
            <div>
              <label className="text-sm text-[#8A8A93] mb-1 block">Why do you need this chain? (Optional)</label>
              <Textarea
                value={formData.reason}
                onChange={(e) => setFormData({...formData, reason: e.target.value})}
                placeholder="e.g., I have significant holdings, need tax reports..."
                className="bg-[#0C0C0E] border-[#1F1F22] text-white resize-none"
                rows={2}
              />
            </div>

            {error && (
              <Alert className="bg-red-900/30 border-red-700">
                <AlertDescription className="text-[#FF3B30]">{error}</AlertDescription>
              </Alert>
            )}

            <div className="flex justify-end gap-2 pt-2">
              <Button
                type="button"
                variant="outline"
                onClick={onClose}
                className="border-[#1F1F22] text-white"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={loading}
                className="bg-white text-black hover:bg-gray-200"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Send className="w-4 h-4 mr-2" />
                )}
                Submit Request
              </Button>
            </div>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
};
