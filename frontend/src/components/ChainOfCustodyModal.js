/**
 * Chain of Custody Modal
 * Traces the origin of cryptocurrency by following the transaction graph backwards.
 * Helps establish accurate cost basis by finding exchanges, DEXs, and dormant wallet origins.
 * 
 * Unlimited tier only - designed to be easily separable for government/enterprise licensing.
 */
import React, { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Loader2,
  Search,
  Link2,
  Building2,
  ArrowRight,
  Download,
  RefreshCw,
  ExternalLink,
  Layers,
  AlertTriangle,
  GitBranch,
  Table
} from 'lucide-react';
import axios from 'axios';
import { CustodyFlowGraph } from './CustodyFlowGraph';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const ChainOfCustodyModal = ({ isOpen, onClose, getAuthHeader, userTier }) => {
  const [address, setAddress] = useState('');
  const [chain, setChain] = useState('ethereum');
  const [maxDepth, setMaxDepth] = useState(10);
  const [dormancyDays, setDormancyDays] = useState(365);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [viewMode, setViewMode] = useState('graph'); // 'graph' or 'table'

  const supportedChains = [
    { id: 'ethereum', name: 'Ethereum', icon: '⟠' },
    { id: 'polygon', name: 'Polygon', icon: '🔺' },
    { id: 'arbitrum', name: 'Arbitrum', icon: '🔷' },
    { id: 'bsc', name: 'BNB Chain', icon: '🟡' },
    { id: 'base', name: 'Base', icon: '🔵' },
    { id: 'optimism', name: 'Optimism', icon: '🔴' },
  ];

  const analyzeChainOfCustody = async () => {
    if (!address) {
      setError('Please enter a wallet address');
      return;
    }

    if (!address.startsWith('0x') || address.length !== 42) {
      setError('Invalid EVM address format');
      return;
    }

    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await axios.post(
        `${API}/custody/analyze`,
        {
          address: address.toLowerCase(),
          chain: chain,
          max_depth: maxDepth,
          dormancy_days: dormancyDays
        },
        { headers: getAuthHeader() }
      );
      setResult(response.data);
    } catch (err) {
      if (err.response?.status === 403) {
        setError('Chain of Custody analysis requires Unlimited subscription.');
      } else {
        setError(err.response?.data?.detail || 'Analysis failed. Please try again.');
      }
    } finally {
      setLoading(false);
    }
  };

  const exportResults = () => {
    if (!result) return;

    // Create CSV content
    const headers = ['From Address', 'To Address', 'Value', 'Asset', 'Origin Type', 'Exchange/DEX', 'TX Hash', 'Timestamp', 'Depth'];
    const rows = result.custody_chain.map(link => [
      link.from,
      link.to,
      link.value,
      link.asset,
      link.origin_type,
      link.exchange_name || link.dex_name || '',
      link.tx_hash,
      link.timestamp || '',
      link.depth
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.map(cell => `"${cell}"`).join(','))
    ].join('\n');

    // Download
    const blob = new Blob([csvContent], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `chain_of_custody_${address.substring(0, 10)}_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);
  };

  const getExplorerUrl = (txHash, chainId) => {
    const explorers = {
      ethereum: 'https://etherscan.io/tx/',
      polygon: 'https://polygonscan.com/tx/',
      arbitrum: 'https://arbiscan.io/tx/',
      bsc: 'https://bscscan.com/tx/',
      base: 'https://basescan.org/tx/',
      optimism: 'https://optimistic.etherscan.io/tx/'
    };
    return `${explorers[chainId] || explorers.ethereum}${txHash}`;
  };

  const formatAddress = (addr) => {
    if (!addr) return '';
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-5xl max-h-[90vh] overflow-y-auto bg-slate-900 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-2xl text-white flex items-center gap-2">
            <Link2 className="w-6 h-6 text-blue-400" />
            Chain of Custody Analysis
            <Badge className="bg-gradient-to-r from-yellow-600 to-orange-600 ml-2">
              Unlimited
            </Badge>
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Trace the origin of cryptocurrency by following the transaction graph backwards.
            Find where assets came from - exchanges, DEXs, or dormant wallets.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6 mt-4">
          {/* Input Section */}
          <Card className="bg-slate-800/50 border-slate-700">
            <CardHeader className="pb-3">
              <CardTitle className="text-white text-lg">Analysis Parameters</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Chain Selector */}
              <div>
                <label className="text-sm text-gray-400 block mb-2">Blockchain</label>
                <select
                  value={chain}
                  onChange={(e) => setChain(e.target.value)}
                  className="w-full bg-slate-900 border border-slate-600 text-white rounded-md px-3 py-2"
                  disabled={loading}
                >
                  {supportedChains.map(c => (
                    <option key={c.id} value={c.id}>
                      {c.icon} {c.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Address Input */}
              <div>
                <label className="text-sm text-gray-400 block mb-2">Wallet Address</label>
                <div className="flex gap-2">
                  <Input
                    type="text"
                    placeholder="0x..."
                    value={address}
                    onChange={(e) => setAddress(e.target.value)}
                    className="flex-1 bg-slate-900 border-slate-600 text-white"
                    disabled={loading}
                  />
                  <Button
                    onClick={analyzeChainOfCustody}
                    disabled={loading || !address}
                    className="bg-blue-600 hover:bg-blue-700"
                  >
                    {loading ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Tracing...
                      </>
                    ) : (
                      <>
                        <Search className="w-4 h-4 mr-2" />
                        Analyze
                      </>
                    )}
                  </Button>
                </div>
              </div>

              {/* Advanced Options Toggle */}
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1"
              >
                {showAdvanced ? '▼' : '▶'} Advanced Options
              </button>

              {showAdvanced && (
                <div className="grid grid-cols-2 gap-4 pt-2">
                  <div>
                    <label className="text-sm text-gray-400 block mb-2">
                      Max Trace Depth
                      <span className="text-xs text-gray-500 ml-1">(0 = unlimited)</span>
                    </label>
                    <Input
                      type="number"
                      min="0"
                      max="50"
                      value={maxDepth}
                      onChange={(e) => setMaxDepth(parseInt(e.target.value) || 0)}
                      className="bg-slate-900 border-slate-600 text-white"
                      disabled={loading}
                    />
                  </div>
                  <div>
                    <label className="text-sm text-gray-400 block mb-2">
                      Dormancy Threshold (days)
                    </label>
                    <Input
                      type="number"
                      min="30"
                      max="3650"
                      value={dormancyDays}
                      onChange={(e) => setDormancyDays(parseInt(e.target.value) || 365)}
                      className="bg-slate-900 border-slate-600 text-white"
                      disabled={loading}
                    />
                  </div>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Error Display */}
          {error && (
            <Alert className="bg-red-900/20 border-red-700 text-red-300">
              <AlertTriangle className="w-4 h-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {/* Results Section */}
          {result && (
            <>
              {/* Summary Cards */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold text-white">
                      {result.summary.total_links_traced}
                    </div>
                    <div className="text-sm text-gray-400">Links Traced</div>
                  </CardContent>
                </Card>
                <Card className="bg-green-900/30 border-green-700">
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold text-green-400">
                      {result.summary.exchange_origins}
                    </div>
                    <div className="text-sm text-gray-400">Exchange Origins</div>
                  </CardContent>
                </Card>
                <Card className="bg-blue-900/30 border-blue-700">
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold text-blue-400">
                      {result.summary.dex_origins}
                    </div>
                    <div className="text-sm text-gray-400">DEX Origins</div>
                  </CardContent>
                </Card>
                <Card className="bg-orange-900/30 border-orange-700">
                  <CardContent className="pt-4">
                    <div className="text-2xl font-bold text-orange-400">
                      {result.summary.dormant_origins}
                    </div>
                    <div className="text-sm text-gray-400">Dormant Origins</div>
                  </CardContent>
                </Card>
              </div>

              {/* View Toggle and Export */}
              <div className="flex justify-between items-center">
                <div className="flex gap-2">
                  <Button
                    variant={viewMode === 'graph' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setViewMode('graph')}
                    className={viewMode === 'graph' ? 'bg-purple-600 hover:bg-purple-700' : 'border-slate-600 text-gray-300'}
                  >
                    <GitBranch className="w-4 h-4 mr-2" />
                    Flow Graph
                  </Button>
                  <Button
                    variant={viewMode === 'table' ? 'default' : 'outline'}
                    size="sm"
                    onClick={() => setViewMode('table')}
                    className={viewMode === 'table' ? 'bg-purple-600 hover:bg-purple-700' : 'border-slate-600 text-gray-300'}
                  >
                    <Table className="w-4 h-4 mr-2" />
                    Table View
                  </Button>
                </div>
                <Button
                  onClick={exportResults}
                  variant="outline"
                  className="border-slate-600 text-gray-300"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export Results (CSV)
                </Button>
              </div>

              {/* Flow Graph View */}
              {viewMode === 'graph' && (
                <CustodyFlowGraph result={result} chain={chain} />
              )}

              {/* Table View - Exchange Endpoints */}
              {viewMode === 'table' && result.exchange_endpoints.length > 0 && (
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2">
                      <Building2 className="w-5 h-5 text-green-400" />
                      Exchange Origins
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-slate-700">
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Exchange</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Value</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Date</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Depth</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">TX</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.exchange_endpoints.map((ep, idx) => (
                            <tr key={idx} className="border-b border-slate-700/50">
                              <td className="py-2 px-3">
                                <Badge className="bg-green-900/50 text-green-300">
                                  {ep.exchange}
                                </Badge>
                              </td>
                              <td className="py-2 px-3 text-white font-mono">
                                {ep.value?.toFixed(6)}
                              </td>
                              <td className="py-2 px-3 text-gray-300">
                                {ep.timestamp ? new Date(ep.timestamp).toLocaleDateString() : '-'}
                              </td>
                              <td className="py-2 px-3 text-gray-400">
                                {ep.depth} hops
                              </td>
                              <td className="py-2 px-3">
                                <a
                                  href={getExplorerUrl(ep.tx_hash, chain)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                                >
                                  {formatAddress(ep.tx_hash)}
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* DEX Endpoints - Table View */}
              {viewMode === 'table' && result.dex_endpoints.length > 0 && (
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2">
                      <RefreshCw className="w-5 h-5 text-blue-400" />
                      DEX Swap Origins
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-slate-700">
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">DEX</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Value</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Date</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Depth</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">TX</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.dex_endpoints.map((ep, idx) => (
                            <tr key={idx} className="border-b border-slate-700/50">
                              <td className="py-2 px-3">
                                <Badge className="bg-blue-900/50 text-blue-300">
                                  {ep.dex}
                                </Badge>
                              </td>
                              <td className="py-2 px-3 text-white font-mono">
                                {ep.value?.toFixed(6)}
                              </td>
                              <td className="py-2 px-3 text-gray-300">
                                {ep.timestamp ? new Date(ep.timestamp).toLocaleDateString() : '-'}
                              </td>
                              <td className="py-2 px-3 text-gray-400">
                                {ep.depth} hops
                              </td>
                              <td className="py-2 px-3">
                                <a
                                  href={getExplorerUrl(ep.tx_hash, chain)}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                                >
                                  {formatAddress(ep.tx_hash)}
                                  <ExternalLink className="w-3 h-3" />
                                </a>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Full Chain Table - Table View */}
              {viewMode === 'table' && result.custody_chain.length > 0 && (
                <Card className="bg-slate-800/50 border-slate-700">
                  <CardHeader>
                    <CardTitle className="text-white flex items-center gap-2">
                      <Layers className="w-5 h-5 text-purple-400" />
                      Full Custody Chain
                      <span className="text-sm font-normal text-gray-400 ml-2">
                        (showing first {Math.min(result.custody_chain.length, 100)} links)
                      </span>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <div className="overflow-x-auto max-h-96">
                      <table className="w-full">
                        <thead className="sticky top-0 bg-slate-800">
                          <tr className="border-b border-slate-700">
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">From</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium"></th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">To</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Value</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Type</th>
                            <th className="text-left py-2 px-3 text-gray-400 font-medium">Depth</th>
                          </tr>
                        </thead>
                        <tbody>
                          {result.custody_chain.map((link, idx) => (
                            <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                              <td className="py-2 px-3 font-mono text-sm text-gray-300">
                                {formatAddress(link.from)}
                              </td>
                              <td className="py-2 px-3">
                                <ArrowRight className="w-4 h-4 text-gray-500" />
                              </td>
                              <td className="py-2 px-3 font-mono text-sm text-gray-300">
                                {formatAddress(link.to)}
                              </td>
                              <td className="py-2 px-3 text-white font-mono text-sm">
                                {link.value?.toFixed(4)} {link.asset}
                              </td>
                              <td className="py-2 px-3">
                                <Badge className={
                                  link.origin_type === 'exchange' ? 'bg-green-900/50 text-green-300' :
                                  link.origin_type === 'dex_swap' ? 'bg-blue-900/50 text-blue-300' :
                                  link.origin_type === 'dormant' ? 'bg-orange-900/50 text-orange-300' :
                                  'bg-slate-700 text-gray-300'
                                }>
                                  {link.origin_type}
                                </Badge>
                              </td>
                              <td className="py-2 px-3 text-gray-400 text-sm">
                                {link.depth}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </CardContent>
                </Card>
              )}

              {/* Analysis Info */}
              <div className="text-xs text-gray-500 text-center">
                Analysis completed at {new Date(result.analysis_timestamp).toLocaleString()} | 
                {result.summary.unique_addresses_visited} unique addresses visited
              </div>
            </>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

export default ChainOfCustodyModal;
