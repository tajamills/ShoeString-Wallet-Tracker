/**
 * Wallet Linkage & Review Queue Component
 * 
 * Handles:
 * - Viewing and managing wallet linkages (clusters)
 * - Review queue for chain breaks ("Is this your wallet?")
 * - Tax event generation from resolved chain breaks
 * - Form 8949 export
 */
import React, { useState, useEffect } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Loader2,
  Link2,
  Unlink,
  CheckCircle,
  XCircle,
  HelpCircle,
  AlertTriangle,
  Download,
  RefreshCw,
  Wallet,
  ArrowRight,
  FileText,
  Clock,
  DollarSign,
  Link
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const WalletLinkageManager = ({ getAuthHeader, onUpdate }) => {
  const [activeTab, setActiveTab] = useState('review');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  
  // Review queue state
  const [reviews, setReviews] = useState([]);
  const [resolvingId, setResolvingId] = useState(null);
  
  // Auto-link state
  const [autoLinking, setAutoLinking] = useState(false);
  const [autoLinkResult, setAutoLinkResult] = useState('');
  
  // Linkages state
  const [linkages, setLinkages] = useState([]);
  const [clusters, setClusters] = useState([]);
  
  // Link wallet form
  const [fromAddress, setFromAddress] = useState('');
  const [toAddress, setToAddress] = useState('');
  const [linkingWallets, setLinkingWallets] = useState(false);
  
  // Tax events state
  const [taxEvents, setTaxEvents] = useState([]);
  const [taxYear, setTaxYear] = useState(new Date().getFullYear());

  useEffect(() => {
    fetchReviewQueue();
    fetchLinkages();
    fetchClusters();
  }, []);

  const fetchReviewQueue = async () => {
    try {
      const response = await axios.get(`${API}/custody/review-queue`, {
        headers: getAuthHeader()
      });
      const reviews = response.data.reviews || [];
      
      // Deduplicate by tx_id
      const seen = new Set();
      const uniqueReviews = reviews.filter(review => {
        const id = review.tx_id || review.id || review.review_id;
        if (seen.has(id)) return false;
        seen.add(id);
        return true;
      });
      
      setReviews(uniqueReviews);
    } catch (err) {
      console.error('Error fetching review queue:', err);
    }
  };

  const detectAndLinkTransfers = async () => {
    setAutoLinking(true);
    setAutoLinkResult('');
    try {
      // First detect matches
      const detectResponse = await axios.get(`${API}/custody/detect-internal-transfers`, {
        headers: getAuthHeader()
      });
      
      const matches = detectResponse.data.matches || [];
      if (matches.length === 0) {
        setAutoLinkResult('No matching internal transfers found to auto-link.');
        return;
      }
      
      // Auto-link with high confidence (95%+)
      const linkResponse = await axios.post(
        `${API}/custody/bulk-link-internal-transfers?min_confidence=95`,
        {},
        { headers: getAuthHeader() }
      );
      
      const linkedCount = linkResponse.data.linked_count || 0;
      if (linkedCount > 0) {
        setAutoLinkResult(`Auto-linked ${linkedCount} internal transfers (sends matched with receives from different exchanges)`);
        // Refresh the review queue
        fetchReviewQueue();
        if (onUpdate) onUpdate();
      } else {
        setAutoLinkResult(`Found ${matches.length} potential matches, but none met the 95% confidence threshold. Review manually.`);
      }
    } catch (err) {
      console.error('Error auto-linking transfers:', err);
      setError(err.response?.data?.detail || 'Failed to auto-link transfers');
    } finally {
      setAutoLinking(false);
    }
  };

  const fetchLinkages = async () => {
    try {
      const response = await axios.get(`${API}/custody/linkages`, {
        headers: getAuthHeader()
      });
      setLinkages(response.data.linkages || []);
    } catch (err) {
      console.error('Error fetching linkages:', err);
    }
  };

  const fetchClusters = async () => {
    try {
      const response = await axios.get(`${API}/custody/clusters`, {
        headers: getAuthHeader()
      });
      setClusters(response.data.clusters || []);
    } catch (err) {
      console.error('Error fetching clusters:', err);
    }
  };

  const fetchTaxEvents = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/custody/tax-events?tax_year=${taxYear}`, {
        headers: getAuthHeader()
      });
      setTaxEvents(response.data.tax_events || []);
    } catch (err) {
      setError('Failed to fetch tax events');
    } finally {
      setLoading(false);
    }
  };

  const resolveReview = async (reviewId, decision) => {
    setResolvingId(reviewId);
    setError('');
    setSuccess('');
    
    try {
      const response = await axios.post(
        `${API}/custody/resolve-review`,
        { review_id: reviewId, decision },
        { headers: getAuthHeader() }
      );
      
      if (decision === 'yes') {
        setSuccess('Wallet linked! Chain of custody restored.');
      } else if (decision === 'no') {
        setSuccess('Marked as external transfer. Tax event created.');
      } else {
        setSuccess('Review ignored for now.');
      }
      
      // Refresh data
      fetchReviewQueue();
      fetchLinkages();
      fetchClusters();
      if (onUpdate) onUpdate();
      
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to resolve review');
    } finally {
      setResolvingId(null);
    }
  };

  const linkWallets = async () => {
    if (!fromAddress.trim() || !toAddress.trim()) {
      setError('Both wallet addresses are required');
      return;
    }
    
    setLinkingWallets(true);
    setError('');
    setSuccess('');
    
    try {
      await axios.post(
        `${API}/custody/link-wallet`,
        { from_address: fromAddress.trim(), to_address: toAddress.trim() },
        { headers: getAuthHeader() }
      );
      
      setSuccess('Wallets linked successfully!');
      setFromAddress('');
      setToAddress('');
      
      // Refresh data
      fetchLinkages();
      fetchClusters();
      if (onUpdate) onUpdate();
      
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to link wallets');
    } finally {
      setLinkingWallets(false);
    }
  };

  const unlinkWallet = async (edgeId) => {
    try {
      await axios.delete(`${API}/custody/unlink-wallet/${edgeId}`, {
        headers: getAuthHeader()
      });
      
      setSuccess('Linkage removed');
      fetchLinkages();
      fetchClusters();
      
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to remove linkage');
    }
  };

  const exportForm8949 = async () => {
    try {
      const response = await axios.get(
        `${API}/custody/export-form-8949?tax_year=${taxYear}`,
        {
          headers: getAuthHeader(),
          responseType: 'blob'
        }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `form_8949_${taxYear}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
    } catch (err) {
      setError('Failed to export Form 8949');
    }
  };

  const exportReviewQueue = async () => {
    try {
      const response = await axios.get(
        `${API}/custody/export-review-queue`,
        {
          headers: getAuthHeader(),
          responseType: 'blob'
        }
      );
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `review_queue_${new Date().toISOString().split('T')[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      
    } catch (err) {
      setError('Failed to export review queue');
    }
  };

  const truncateAddress = (addr, full = false) => {
    if (!addr) return '';
    if (full || addr.length <= 20) return addr;
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };
  
  // State for showing full addresses
  const [showFullAddresses, setShowFullAddresses] = useState(true);

  return (
    <div className="space-y-4">
      {/* Messages */}
      {error && (
        <Alert className="bg-red-900/20 border-red-700">
          <AlertTriangle className="w-4 h-4 text-[#FF3B30]" />
          <AlertDescription className="text-[#FF3B30]">{error}</AlertDescription>
        </Alert>
      )}
      
      {success && (
        <Alert className="bg-green-900/20 border-green-700">
          <CheckCircle className="w-4 h-4 text-[#00C805]" />
          <AlertDescription className="text-[#00C805]">{success}</AlertDescription>
        </Alert>
      )}

      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="grid w-full grid-cols-4 bg-[#161618]">
          <TabsTrigger value="review" className="text-xs sm:text-sm data-[state=active]:bg-white text-black">
            <HelpCircle className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
            <span className="hidden sm:inline">Review</span>
            {reviews.length > 0 && (
              <Badge className="ml-1 bg-red-500 text-white text-xs">{reviews.length}</Badge>
            )}
          </TabsTrigger>
          <TabsTrigger value="linkages" className="text-xs sm:text-sm data-[state=active]:bg-white text-black">
            <Link2 className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
            <span className="hidden sm:inline">Linkages</span>
          </TabsTrigger>
          <TabsTrigger value="clusters" className="text-xs sm:text-sm data-[state=active]:bg-white text-black">
            <Wallet className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
            <span className="hidden sm:inline">Wallets</span>
          </TabsTrigger>
          <TabsTrigger value="tax" className="text-xs sm:text-sm data-[state=active]:bg-white text-black">
            <FileText className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
            <span className="hidden sm:inline">Tax</span>
          </TabsTrigger>
        </TabsList>

        {/* Review Queue Tab */}
        <TabsContent value="review" className="space-y-3 mt-3">
          <div className="flex justify-between items-center flex-wrap gap-2">
            <div>
              <h3 className="text-sm font-medium text-white">Transaction Reviews</h3>
              {reviews.length > 0 && (
                <p className="text-xs text-[#FFB800]">{reviews.length} transactions need verification</p>
              )}
            </div>
            <div className="flex gap-2 flex-wrap">
              <Button
                size="sm"
                onClick={detectAndLinkTransfers}
                disabled={autoLinking}
                className="text-xs bg-[#00C805] hover:bg-[#00C805]/80"
                title="Auto-detect and link internal transfers between your exchanges"
              >
                {autoLinking ? (
                  <Loader2 className="w-3 h-3 animate-spin mr-1" />
                ) : (
                  <Link className="w-3 h-3 mr-1" />
                )}
                Auto-Link Transfers
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={exportReviewQueue}
                className="text-xs border-[#1F1F22]"
              >
                <Download className="w-3 h-3 mr-1" />
                Export
              </Button>
              <Button
                size="sm"
                variant="outline"
                onClick={fetchReviewQueue}
                className="text-xs border-[#1F1F22]"
              >
                <RefreshCw className="w-3 h-3" />
              </Button>
            </div>
          </div>

          {/* Auto-Link Results */}
          {autoLinkResult && (
            <Card className="bg-green-900/20 border-green-700/50">
              <CardContent className="py-2 px-3">
                <p className="text-xs text-[#00C805]">
                  <CheckCircle className="w-3 h-3 inline mr-1" />
                  {autoLinkResult}
                </p>
              </CardContent>
            </Card>
          )}

          {/* Info Banner */}
          {reviews.length > 0 && (
            <Card className="bg-blue-900/20 border-blue-700/50">
              <CardContent className="py-2 px-3">
                <p className="text-xs text-blue-300">
                  <strong>Review outgoing transactions:</strong> Mark transfers to your own wallets as "Mine" (not taxable). 
                  Mark external payments as "External" (taxable disposal).
                </p>
              </CardContent>
            </Card>
          )}

          {reviews.length === 0 ? (
            <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]">
              <CardContent className="py-8 text-center">
                <CheckCircle className="w-12 h-12 mx-auto text-green-500 mb-3" />
                <p className="text-[#8A8A93]">No pending reviews!</p>
                <p className="text-xs text-[#4A4A52] mt-1">All transfers have been resolved.</p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {reviews.map((review) => (
                <Card key={review.tx_id || review.id || review.review_id} className="bg-[#0C0C0E]/50 border-[#1F1F22]">
                  <CardContent className="p-3">
                    <div className="flex flex-col gap-2">
                      {/* Transaction info row */}
                      <div className="flex items-center gap-2 text-sm flex-wrap">
                        <span className="text-[#8A8A93] font-medium">{review.amount?.toFixed(6)}</span>
                        <Badge className="bg-white text-black">{review.asset}</Badge>
                        {review.exchange && (
                          <Badge variant="outline" className="text-xs border-[#00C805] text-[#00C805]">
                            {review.exchange}
                          </Badge>
                        )}
                      </div>
                      
                      {/* Destination address - full display */}
                      <div className="flex items-center gap-2">
                        <ArrowRight className="w-3 h-3 text-[#4A4A52] flex-shrink-0" />
                        <span className="text-white font-mono text-xs break-all">
                          {showFullAddresses ? review.destination_address : truncateAddress(review.destination_address)}
                        </span>
                      </div>
                      
                      {/* Question */}
                      <p className="text-xs text-[#FFB800]">
                        {review.question || review.prompt_text || "Is this another wallet you own?"}
                      </p>
                      
                      {/* Help text */}
                      {review.help_text && (
                        <p className="text-xs text-[#4A4A52]">{review.help_text}</p>
                      )}
                      
                      {/* Action buttons */}
                      <div className="flex gap-1 mt-1">
                        <Button
                          size="sm"
                          onClick={() => resolveReview(review.tx_id || review.id || review.review_id, 'yes')}
                          disabled={resolvingId === (review.tx_id || review.id || review.review_id)}
                          className="bg-[#00C805] hover:bg-[#00C805]/80 text-xs px-2"
                          title="Yes, this is my wallet (internal transfer)"
                        >
                          {resolvingId === (review.tx_id || review.id || review.review_id) ? (
                            <Loader2 className="w-3 h-3 animate-spin" />
                          ) : (
                            <>
                              <CheckCircle className="w-3 h-3 mr-1" />
                              Mine
                            </>
                          )}
                        </Button>
                        <Button
                          size="sm"
                          onClick={() => resolveReview(review.tx_id || review.id || review.review_id, 'no')}
                          disabled={resolvingId === (review.tx_id || review.id || review.review_id)}
                          className="bg-[#FF3B30] hover:bg-[#FF3B30]/80 text-xs px-2"
                          title="No, this is external (taxable)"
                        >
                          <XCircle className="w-3 h-3 mr-1" />
                          External
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => resolveReview(review.tx_id || review.id || review.review_id, 'ignore')}
                          disabled={resolvingId === (review.tx_id || review.id || review.review_id)}
                          className="text-xs px-2 border-[#1F1F22]"
                          title="Skip for now"
                        >
                          Skip
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Linkages Tab */}
        <TabsContent value="linkages" className="space-y-3 mt-3">
          {/* Manual Link Form */}
          <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]">
            <CardHeader className="pb-2">
              <CardTitle className="text-sm text-white">Link Wallets Manually</CardTitle>
              <CardDescription className="text-xs">
                Connect two wallet addresses you own to maintain cost basis continuity.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-2">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                <Input
                  value={fromAddress}
                  onChange={(e) => setFromAddress(e.target.value)}
                  placeholder="From address (0x...)"
                  className="bg-[#161618] border-[#1F1F22] text-white text-xs"
                />
                <Input
                  value={toAddress}
                  onChange={(e) => setToAddress(e.target.value)}
                  placeholder="To address (0x...)"
                  className="bg-[#161618] border-[#1F1F22] text-white text-xs"
                />
              </div>
              <Button
                onClick={linkWallets}
                disabled={linkingWallets || !fromAddress || !toAddress}
                className="w-full bg-white text-black hover:bg-gray-200 text-sm"
              >
                {linkingWallets ? (
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                ) : (
                  <Link2 className="w-4 h-4 mr-2" />
                )}
                Link Wallets
              </Button>
            </CardContent>
          </Card>

          {/* Existing Linkages */}
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-medium text-white">Active Linkages ({linkages.length})</h3>
            <Button
              size="sm"
              variant="outline"
              onClick={fetchLinkages}
              className="text-xs border-[#1F1F22]"
            >
              <RefreshCw className="w-3 h-3" />
            </Button>
          </div>

          {linkages.length === 0 ? (
            <p className="text-[#4A4A52] text-sm text-center py-4">No wallet linkages yet.</p>
          ) : (
            <div className="space-y-1 max-h-[300px] overflow-y-auto">
              {linkages.map((edge) => (
                <div
                  key={edge.id}
                  className="flex items-center justify-between bg-[#0C0C0E]/50 rounded p-2"
                >
                  <div className="flex items-center gap-2 text-xs">
                    <span className="font-mono text-[#8A8A93]">
                      {truncateAddress(edge.from_address)}
                    </span>
                    <ArrowRight className="w-3 h-3 text-[#00C805]" />
                    <span className="font-mono text-[#8A8A93]">
                      {truncateAddress(edge.to_address)}
                    </span>
                    <Badge className={`text-[10px] ${
                      edge.confidence >= 0.95 ? 'bg-[#00C805]' :
                      edge.confidence >= 0.8 ? 'bg-yellow-600' : 'bg-orange-600'
                    }`}>
                      {(edge.confidence * 100).toFixed(0)}%
                    </Badge>
                  </div>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => unlinkWallet(edge.id)}
                    className="text-[#FF3B30] hover:text-[#FF3B30] p-1"
                    title="Remove linkage"
                  >
                    <Unlink className="w-3 h-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Clusters Tab */}
        <TabsContent value="clusters" className="space-y-3 mt-3">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-medium text-white">Wallet Groups ({clusters.length})</h3>
            <Button
              size="sm"
              variant="outline"
              onClick={fetchClusters}
              className="text-xs border-[#1F1F22]"
            >
              <RefreshCw className="w-3 h-3" />
            </Button>
          </div>

          {clusters.length === 0 ? (
            <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]">
              <CardContent className="py-8 text-center">
                <Wallet className="w-12 h-12 mx-auto text-[#4A4A52] mb-3" />
                <p className="text-[#8A8A93]">No wallet groups yet.</p>
                <p className="text-xs text-[#4A4A52] mt-1">
                  Link wallets to automatically group them.
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-2">
              {clusters.map((cluster) => (
                <Card key={cluster.id} className="bg-[#0C0C0E]/50 border-[#1F1F22]">
                  <CardContent className="p-3">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-medium text-white">
                        {cluster.name || `Group ${cluster.id.slice(0, 8)}`}
                      </span>
                      <Badge className="bg-white text-black">
                        {cluster.addresses?.length || cluster.address_count || 0} wallets
                      </Badge>
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {(cluster.addresses || []).slice(0, 5).map((addr, i) => (
                        <span
                          key={i}
                          className="font-mono text-[10px] bg-[#161618] px-1.5 py-0.5 rounded text-[#8A8A93]"
                        >
                          {truncateAddress(addr)}
                        </span>
                      ))}
                      {(cluster.addresses?.length || 0) > 5 && (
                        <span className="text-[10px] text-[#4A4A52]">
                          +{cluster.addresses.length - 5} more
                        </span>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </TabsContent>

        {/* Tax Events Tab */}
        <TabsContent value="tax" className="space-y-3 mt-3">
          <div className="flex flex-col sm:flex-row justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="text-sm text-[#8A8A93]">Tax Year:</span>
              <select
                value={taxYear}
                onChange={(e) => setTaxYear(parseInt(e.target.value))}
                className="bg-[#161618] border-[#1F1F22] rounded px-2 py-1 text-sm text-white"
              >
                {[2024, 2023, 2022, 2021, 2020].map((year) => (
                  <option key={year} value={year}>{year}</option>
                ))}
              </select>
              <Button
                size="sm"
                onClick={fetchTaxEvents}
                disabled={loading}
                className="bg-white text-black hover:bg-gray-200 text-xs"
              >
                {loading ? <Loader2 className="w-3 h-3 animate-spin" /> : 'Load'}
              </Button>
            </div>
            <Button
              size="sm"
              onClick={exportForm8949}
              className="bg-[#00C805] hover:bg-[#00C805]/80 text-xs"
            >
              <Download className="w-3 h-3 mr-1" />
              Export Form 8949
            </Button>
          </div>

          {taxEvents.length === 0 ? (
            <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]">
              <CardContent className="py-8 text-center">
                <FileText className="w-12 h-12 mx-auto text-[#4A4A52] mb-3" />
                <p className="text-[#8A8A93]">No tax events from chain breaks.</p>
                <p className="text-xs text-[#4A4A52] mt-1">
                  Tax events are created when you mark transfers as "external".
                </p>
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-1 max-h-[300px] overflow-y-auto">
              {taxEvents.map((event) => (
                <div
                  key={event.id}
                  className="flex items-center justify-between bg-[#0C0C0E]/50 rounded p-2"
                >
                  <div className="flex items-center gap-2">
                    <Badge className="bg-white text-black text-xs">{event.asset}</Badge>
                    <span className="text-xs text-[#8A8A93]">
                      {event.quantity?.toFixed(6)}
                    </span>
                    <span className="text-xs text-[#4A4A52]">
                      {event.date_disposed?.split('T')[0]}
                    </span>
                  </div>
                  <div className={`text-xs font-medium ${
                    event.gain_loss >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'
                  }`}>
                    {event.gain_loss >= 0 ? '+' : ''}${event.gain_loss?.toFixed(2)}
                  </div>
                </div>
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
};
