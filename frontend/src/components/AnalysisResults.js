import React from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Crown,
  Wallet,
  TrendingUp,
  TrendingDown,
  Activity,
  DollarSign,
  Download,
  Tag
} from 'lucide-react';
import { getChainSymbol, getChainIcon } from './WalletInputCard';

export const formatNumber = (num) => {
  const value = Number(num);
  if (value === 0) return '0';
  if (value < 0.0001) return value.toExponential(4);
  if (value < 1) return value.toFixed(6);
  return value.toFixed(4);
};

export const formatUSD = (num) => {
  if (num === undefined || num === null) return '$0.00';
  return new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  }).format(num);
};

export const formatAddress = (addr) => {
  if (!addr) return '';
  return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
};

// Portfolio Value Card
export const PortfolioValueCard = ({ totalValueUsd, netBalance, symbol, priceUsd }) => (
  <Card className="bg-gradient-to-r from-green-900/30 to-emerald-800/30 border-green-700">
    <CardContent className="pt-6">
      <div className="text-center">
        <p className="text-[#8A8A93] text-sm mb-2">Portfolio Value</p>
        <h2 className="text-5xl font-bold text-white mb-2">{formatUSD(totalValueUsd)}</h2>
        {priceUsd && (
          <p className="text-[#8A8A93] text-sm">
            {formatNumber(netBalance)} {symbol}
            <span className="mx-2">•</span>1 {symbol} = {formatUSD(priceUsd)}
          </p>
        )}
      </div>
    </CardContent>
  </Card>
);

// Stats Card Component
export const StatCard = ({ title, value, usdValue, subtitle, icon: Icon, colorClass }) => (
  <Card className={`bg-gradient-to-br ${colorClass}`}>
    <CardHeader className="pb-3">
      <CardTitle className="text-sm font-medium flex items-center gap-2">
        <Icon className="w-4 h-4" />
        {title}
      </CardTitle>
    </CardHeader>
    <CardContent>
      <div className="text-3xl font-bold text-white">{value}</div>
      {usdValue && <p className="text-xl font-semibold mt-1">{usdValue}</p>}
      <p className="text-xs mt-1">{subtitle}</p>
    </CardContent>
  </Card>
);

// Multi-Chain Results Card
export const MultiChainResultsCard = ({ multiChainResults }) => {
  if (!multiChainResults) return null;

  return (
    <Card className="bg-gradient-to-br from-orange-900/30 to-yellow-800/20 border-orange-700">
      <CardHeader>
        <CardTitle className="text-white flex items-center gap-2">
          <Crown className="w-6 h-6 text-[#FFB800]" />
          Multi-Chain Portfolio Analysis
          <Badge className="bg-yellow-600 ml-2">Pro Feature</Badge>
        </CardTitle>
        <CardDescription className="text-[#8A8A93]">
          Analyzed {multiChainResults.address} across {multiChainResults.chains_analyzed} blockchains
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* Aggregated Totals */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-[#050505]/50 rounded-lg p-4">
            <div className="text-sm text-[#8A8A93] mb-1">Total Transactions</div>
            <div className="text-3xl font-bold text-white">
              {multiChainResults.aggregated.total_transactions.toLocaleString()}
            </div>
            <div className="text-xs text-[#4A4A52] mt-1">Across all chains</div>
          </div>
          <div className="bg-[#050505]/50 rounded-lg p-4">
            <div className="text-sm text-[#8A8A93] mb-1">Total Gas Fees</div>
            <div className="text-3xl font-bold text-orange-400">
              {formatNumber(multiChainResults.aggregated.total_gas_fees)}
            </div>
            <div className="text-xs text-[#4A4A52] mt-1">Combined across chains</div>
          </div>
          <div className="bg-[#050505]/50 rounded-lg p-4">
            <div className="text-sm text-[#8A8A93] mb-1">Chains Analyzed</div>
            <div className="text-3xl font-bold text-[#00C805]">
              {multiChainResults.chains_analyzed}/{multiChainResults.total_chains}
            </div>
            <div className="text-xs text-[#4A4A52] mt-1">Successfully analyzed</div>
          </div>
        </div>

        {/* Per-Chain Breakdown */}
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-white mb-3">Chain Breakdown</h3>
          {multiChainResults.results.map((result) => (
            <div key={result.chain} className="bg-[#050505]/30 rounded-lg p-4 border border-[#1F1F22]">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{getChainIcon(result.chain)}</span>
                  <span className="text-lg font-semibold text-white capitalize">{result.chain}</span>
                </div>
                <Badge className="bg-green-900/50 text-[#00C805]">Active</Badge>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <div className="text-[#8A8A93]">Sent</div>
                  <div className="text-white font-semibold">{formatNumber(result.totalSent)}</div>
                </div>
                <div>
                  <div className="text-[#8A8A93]">Received</div>
                  <div className="text-white font-semibold">{formatNumber(result.totalReceived)}</div>
                </div>
                <div>
                  <div className="text-[#8A8A93]">Net Balance</div>
                  <div className={`font-semibold ${result.netBalance >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'}`}>
                    {result.netBalance >= 0 ? '+' : ''}{formatNumber(result.netBalance)}
                  </div>
                </div>
                <div>
                  <div className="text-[#8A8A93]">Transactions</div>
                  <div className="text-white font-semibold">{result.transactionCount}</div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Failed Chains */}
        {multiChainResults.failed_chains?.length > 0 && (
          <Alert className="mt-4 bg-yellow-900/20 border-yellow-700 text-yellow-300">
            <AlertDescription>
              <strong>Note:</strong> Could not analyze {multiChainResults.failed_chains.map(f => f.chain).join(', ')}
            </AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
};

// Transactions Table (clean, collapsible)
export const TransactionsTable = ({ transactions, chain, selectedChain, onExport, isPremium }) => {
  const [isExpanded, setIsExpanded] = React.useState(false);
  const maxPreviewRows = 5;
  
  if (!transactions || transactions.length === 0) return null;

  const currentChain = chain || selectedChain;
  const symbol = getChainSymbol(currentChain);
  const displayTransactions = isExpanded ? transactions : transactions.slice(0, maxPreviewRows);
  const hasMore = transactions.length > maxPreviewRows;

  return (
    <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]" data-testid="transactions-table">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-white text-lg">Recent Transactions</CardTitle>
            <CardDescription className="text-[#8A8A93]">
              {transactions.length} transaction{transactions.length !== 1 ? 's' : ''}
            </CardDescription>
          </div>
          {isPremium && onExport && (
            <Button
              onClick={onExport}
              variant="outline"
              size="sm"
              className="border-[#1F1F22] text-white"
            >
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="space-y-2">
          {displayTransactions.map((tx, idx) => (
            <div key={idx} className="flex items-center justify-between py-2 border-b border-[#1F1F22]/50 last:border-0">
              <div className="flex items-center gap-3">
                <Badge
                  variant="outline"
                  className={tx.type === 'sent' ? 'text-[#FF3B30] border-red-700' : 'text-[#00C805] border-green-700'}
                >
                  {tx.type === 'sent' ? 'Out' : 'In'}
                </Badge>
                <span className="text-white text-sm">{tx.asset || symbol}</span>
              </div>
              <div className="text-right">
                <span className="text-white font-mono text-sm">{formatNumber(tx.value)}</span>
                {tx.value_usd && (
                  <span className="text-[#8A8A93] text-xs ml-2">{formatUSD(tx.value_usd)}</span>
                )}
              </div>
            </div>
          ))}
        </div>
        {hasMore && (
          <button
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full mt-3 py-2 text-sm text-[#00C805] hover:text-[#00C805]"
          >
            {isExpanded ? 'Show less' : `View all ${transactions.length} transactions`}
          </button>
        )}
      </CardContent>
    </Card>
  );
};

// Advanced Analytics Card (Premium)
export const AdvancedAnalyticsCard = ({ analysis, selectedChain }) => {
  const chain = analysis.chain || selectedChain;
  const symbol = getChainSymbol(chain);

  return (
    <Card className="bg-gradient-to-br from-indigo-900/30 to-indigo-800/20 border-indigo-700">
      <CardHeader>
        <CardTitle className="text-white flex items-center gap-2">
          <Activity className="w-5 h-5 text-indigo-400" />
          Advanced Analytics
          <Badge className="bg-white text-black ml-2">Premium</Badge>
        </CardTitle>
        <CardDescription className="text-[#8A8A93]">
          Deeper insights into your wallet activity
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Average Transaction Value */}
          <div className="bg-[#050505]/50 rounded-lg p-4">
            <div className="text-sm text-[#8A8A93] mb-1">Avg Transaction Value</div>
            <div className="text-2xl font-bold text-white">
              {formatNumber(
                (analysis.totalEthReceived + analysis.totalEthSent) /
                Math.max(1, analysis.incomingTransactionCount + analysis.outgoingTransactionCount)
              )} {symbol}
            </div>
            <div className="text-xs text-[#4A4A52] mt-1">Per transaction</div>
          </div>

          {/* Activity Ratio */}
          <div className="bg-[#050505]/50 rounded-lg p-4">
            <div className="text-sm text-[#8A8A93] mb-1">Activity Ratio</div>
            <div className="text-2xl font-bold text-white">
              {analysis.outgoingTransactionCount > 0
                ? (analysis.incomingTransactionCount / analysis.outgoingTransactionCount).toFixed(2)
                : analysis.incomingTransactionCount.toFixed(2)}:1
            </div>
            <div className="text-xs text-[#4A4A52] mt-1">Incoming : Outgoing</div>
          </div>

          {/* Unique Assets */}
          <div className="bg-[#050505]/50 rounded-lg p-4">
            <div className="text-sm text-[#8A8A93] mb-1">Unique Assets</div>
            <div className="text-2xl font-bold text-white">
              {1 + new Set([
                ...Object.keys(analysis.tokensReceived || {}),
                ...Object.keys(analysis.tokensSent || {})
              ]).size}
            </div>
            <div className="text-xs text-[#4A4A52] mt-1">Native + Tokens</div>
          </div>

          {/* Gas Efficiency (EVM only) */}
          {['ethereum', 'arbitrum', 'polygon', 'bsc'].includes(chain) && analysis.totalGasFees > 0 && (
            <div className="bg-[#050505]/50 rounded-lg p-4">
              <div className="text-sm text-[#8A8A93] mb-1">Avg Gas per TX</div>
              <div className="text-2xl font-bold text-white">
                {formatNumber(analysis.totalGasFees / Math.max(1, analysis.outgoingTransactionCount))} {symbol}
              </div>
              <div className="text-xs text-[#4A4A52] mt-1">Average gas cost</div>
            </div>
          )}

          {/* Net Flow */}
          <div className="bg-[#050505]/50 rounded-lg p-4">
            <div className="text-sm text-[#8A8A93] mb-1">Net Flow</div>
            <div className={`text-2xl font-bold ${analysis.netEth >= 0 ? 'text-[#00C805]' : 'text-[#FF3B30]'}`}>
              {analysis.netEth >= 0 ? '+' : ''}{formatNumber(analysis.netEth)} {symbol}
            </div>
            <div className="text-xs text-[#4A4A52] mt-1">
              {analysis.netEth >= 0 ? 'Net accumulation' : 'Net spending'}
            </div>
          </div>

          {/* Total Volume */}
          <div className="bg-[#050505]/50 rounded-lg p-4">
            <div className="text-sm text-[#8A8A93] mb-1">Total Volume</div>
            <div className="text-2xl font-bold text-white">
              {formatNumber(analysis.totalEthReceived + analysis.totalEthSent)} {symbol}
            </div>
            <div className="text-xs text-[#4A4A52] mt-1">Combined flow</div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// ERC-20 Tokens Card
export const TokensCard = ({ tokensReceived, tokensSent }) => {
  if (
    Object.keys(tokensReceived || {}).length === 0 &&
    Object.keys(tokensSent || {}).length === 0
  ) {
    return null;
  }

  return (
    <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]" data-testid="tokens-card">
      <CardHeader>
        <CardTitle className="text-white">ERC-20 Token Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {Object.keys(tokensReceived || {}).length > 0 && (
            <div>
              <h3 className="text-[#00C805] font-semibold mb-3">Tokens Received</h3>
              <div className="space-y-2">
                {Object.entries(tokensReceived).map(([token, amount]) => (
                  <div key={token} className="flex items-center justify-between bg-green-900/10 p-2 rounded">
                    <Badge variant="outline" className="text-[#00C805] border-green-700">{token}</Badge>
                    <span className="text-white font-mono text-sm">{formatNumber(amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {Object.keys(tokensSent || {}).length > 0 && (
            <div>
              <h3 className="text-[#FF3B30] font-semibold mb-3">Tokens Sent</h3>
              <div className="space-y-2">
                {Object.entries(tokensSent).map(([token, amount]) => (
                  <div key={token} className="flex items-center justify-between bg-red-900/10 p-2 rounded">
                    <Badge variant="outline" className="text-[#FF3B30] border-red-700">{token}</Badge>
                    <span className="text-white font-mono text-sm">{formatNumber(amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};
