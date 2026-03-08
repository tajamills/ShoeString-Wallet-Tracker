import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { 
  Loader2, 
  Users, 
  DollarSign, 
  Copy, 
  Check,
  Share2,
  TrendingUp,
  Clock
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const AffiliateModal = ({ isOpen, onClose, getAuthHeader }) => {
  const [loading, setLoading] = useState(true);
  const [affiliateData, setAffiliateData] = useState(null);
  const [registering, setRegistering] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [copied, setCopied] = useState(false);
  
  // Registration form
  const [affiliateCode, setAffiliateCode] = useState('');
  const [name, setName] = useState('');
  const [paypalEmail, setPaypalEmail] = useState('');

  useEffect(() => {
    if (isOpen) {
      fetchAffiliateData();
    }
  }, [isOpen]);

  const fetchAffiliateData = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/affiliate/me`, {
        headers: getAuthHeader()
      });
      setAffiliateData(response.data);
    } catch (err) {
      setError('Failed to load affiliate data');
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async () => {
    if (!affiliateCode || !name) {
      setError('Please fill in all required fields');
      return;
    }

    setRegistering(true);
    setError('');
    setSuccess('');

    try {
      const response = await axios.post(
        `${API}/affiliate/register`,
        {
          affiliate_code: affiliateCode,
          name: name,
          paypal_email: paypalEmail || null
        },
        { headers: getAuthHeader() }
      );

      setSuccess(response.data.message);
      fetchAffiliateData(); // Refresh data
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to register');
    } finally {
      setRegistering(false);
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const formatDate = (dateStr) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    });
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto" data-testid="affiliate-modal">
        <DialogHeader>
          <DialogTitle className="text-white text-2xl flex items-center gap-2" data-testid="affiliate-modal-title">
            <Users className="w-6 h-6 text-purple-400" />
            Affiliate Program
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Earn $10 for every customer you refer. They get $10 off too!
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12" data-testid="affiliate-loading">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          </div>
        ) : affiliateData?.is_affiliate ? (
          // Affiliate Dashboard
          <div className="space-y-6" data-testid="affiliate-dashboard">
            {/* Stats Cards */}
            <div className="grid grid-cols-3 gap-4">
              <Card className="bg-slate-900/50 border-slate-700">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
                    <DollarSign className="w-4 h-4" />
                    Total Earned
                  </div>
                  <div className="text-2xl font-bold text-green-400">
                    ${affiliateData.total_earnings.toFixed(2)}
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-slate-900/50 border-slate-700">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
                    <Clock className="w-4 h-4" />
                    Pending Payout
                  </div>
                  <div className="text-2xl font-bold text-yellow-400">
                    ${affiliateData.pending_earnings.toFixed(2)}
                  </div>
                </CardContent>
              </Card>
              
              <Card className="bg-slate-900/50 border-slate-700">
                <CardContent className="pt-4">
                  <div className="flex items-center gap-2 text-gray-400 text-sm mb-1">
                    <TrendingUp className="w-4 h-4" />
                    Referrals
                  </div>
                  <div className="text-2xl font-bold text-white">
                    {affiliateData.referral_count}
                  </div>
                </CardContent>
              </Card>
            </div>

            {/* Share Code */}
            <Card className="bg-gradient-to-r from-purple-900/30 to-pink-900/30 border-purple-700">
              <CardHeader>
                <CardTitle className="text-white flex items-center gap-2">
                  <Share2 className="w-5 h-5 text-purple-400" />
                  Your Affiliate Code
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-3">
                  <Badge className="bg-purple-600 text-xl px-4 py-2" data-testid="affiliate-code-badge">
                    {affiliateData.affiliate_code}
                  </Badge>
                  <Button
                    onClick={() => copyToClipboard(affiliateData.affiliate_code)}
                    variant="outline"
                    className="border-purple-600 text-purple-300"
                  >
                    {copied ? (
                      <>
                        <Check className="w-4 h-4 mr-2" />
                        Copied!
                      </>
                    ) : (
                      <>
                        <Copy className="w-4 h-4 mr-2" />
                        Copy Code
                      </>
                    )}
                  </Button>
                </div>
                <p className="text-sm text-gray-400 mt-3">
                  Share this code with friends. They get $10 off, you earn $10!
                </p>
              </CardContent>
            </Card>

            {/* Recent Referrals */}
            {affiliateData.recent_referrals?.length > 0 && (
              <Card className="bg-slate-900/50 border-slate-700">
                <CardHeader>
                  <CardTitle className="text-white">Recent Referrals</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="space-y-3">
                    {affiliateData.recent_referrals.map((ref, idx) => (
                      <div key={idx} className="flex items-center justify-between py-2 border-b border-slate-700 last:border-0">
                        <div>
                          <span className="text-gray-300">{ref.customer_email}</span>
                          <span className="text-gray-500 text-sm ml-2">
                            {formatDate(ref.created_at)}
                          </span>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="text-green-400 font-semibold">+${ref.amount_earned}</span>
                          {ref.paid_out ? (
                            <Badge className="bg-green-900/50 text-green-300 text-xs">Paid</Badge>
                          ) : (
                            <Badge className="bg-yellow-900/50 text-yellow-300 text-xs">Pending</Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}

            <Alert className="bg-blue-900/20 border-blue-700 text-blue-300">
              <AlertDescription>
                Payouts are processed quarterly via PayPal. Make sure your PayPal email is set:
                <strong className="ml-1">{affiliateData.paypal_email || 'Not set'}</strong>
              </AlertDescription>
            </Alert>
          </div>
        ) : (
          // Registration Form
          <div className="space-y-6" data-testid="affiliate-registration-form">
            <div className="bg-gradient-to-r from-purple-900/20 to-pink-900/20 rounded-lg p-6 border border-purple-700/50">
              <h3 className="text-xl font-bold text-white mb-2">Join Our Affiliate Program</h3>
              <p className="text-gray-400 mb-4">
                Earn $10 for every person who signs up using your unique code. 
                They also get $10 off their subscription!
              </p>
              
              <ul className="space-y-2 text-sm text-gray-300">
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  Earn $10 per successful referral
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  Your friends save $10 on their subscription
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  Quarterly PayPal payouts
                </li>
                <li className="flex items-center gap-2">
                  <Check className="w-4 h-4 text-green-400" />
                  Track your earnings in real-time
                </li>
              </ul>
            </div>

            <div className="space-y-4">
              <div>
                <label className="text-sm font-medium text-gray-300 mb-1 block">
                  Choose Your Affiliate Code *
                </label>
                <Input
                  value={affiliateCode}
                  onChange={(e) => setAffiliateCode(e.target.value.toUpperCase())}
                  placeholder="e.g., JOHN10, CRYPTOPRO"
                  className="bg-slate-900 border-slate-600 text-white uppercase"
                  maxLength={20}
                  data-testid="affiliate-code-input"
                />
                <p className="text-xs text-gray-500 mt-1">3-20 characters, letters and numbers only</p>
              </div>

              <div>
                <label className="text-sm font-medium text-gray-300 mb-1 block">
                  Your Name *
                </label>
                <Input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="John Smith"
                  className="bg-slate-900 border-slate-600 text-white"
                  data-testid="affiliate-name-input"
                />
              </div>

              <div>
                <label className="text-sm font-medium text-gray-300 mb-1 block">
                  PayPal Email (for payouts)
                </label>
                <Input
                  value={paypalEmail}
                  onChange={(e) => setPaypalEmail(e.target.value)}
                  placeholder="your@paypal.com"
                  type="email"
                  className="bg-slate-900 border-slate-600 text-white"
                  data-testid="affiliate-paypal-input"
                />
                <p className="text-xs text-gray-500 mt-1">You can add this later</p>
              </div>
            </div>

            {error && (
              <Alert className="bg-red-900/20 border-red-700 text-red-300">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="bg-green-900/20 border-green-700 text-green-300">
                <AlertDescription>{success}</AlertDescription>
              </Alert>
            )}

            <Button
              onClick={handleRegister}
              disabled={registering || !affiliateCode || !name}
              className="w-full bg-gradient-to-r from-purple-600 to-pink-600 hover:from-purple-700 hover:to-pink-700 h-12"
              data-testid="affiliate-register-button"
            >
              {registering ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Registering...
                </>
              ) : (
                <>
                  <Users className="mr-2 h-4 w-4" />
                  Become an Affiliate
                </>
              )}
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
