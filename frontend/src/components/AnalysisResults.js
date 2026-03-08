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
        <p className="text-gray-400 text-sm mb-2">Portfolio Value</p>
        <h2 className="text-5xl font-bold text-white mb-2">{formatUSD(totalValueUsd)}</h2>
        {priceUsd && (
          <p className="text-gray-400 text-sm">
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
          <Crown className="w-6 h-6 text-yellow-400" />
          Multi-Chain Portfolio Analysis
          <Badge className="bg-yellow-600 ml-2">Pro Feature</Badge>
        </CardTitle>
        <CardDescription className="text-gray-400">
          Analyzed {multiChainResults.address} across {multiChainResults.chains_analyzed} blockchains
        </CardDescription>
      </CardHeader>
      <CardContent>
        {/* Aggregated Totals */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Total Transactions</div>
            <div className="text-3xl font-bold text-white">
              {multiChainResults.aggregated.total_transactions.toLocaleString()}
            </div>
            <div className="text-xs text-gray-500 mt-1">Across all chains</div>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Total Gas Fees</div>
            <div className="text-3xl font-bold text-orange-400">
              {formatNumber(multiChainResults.aggregated.total_gas_fees)}
            </div>
            <div className="text-xs text-gray-500 mt-1">Combined across chains</div>
          </div>
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Chains Analyzed</div>
            <div className="text-3xl font-bold text-green-400">
              {multiChainResults.chains_analyzed}/{multiChainResults.total_chains}
            </div>
            <div className="text-xs text-gray-500 mt-1">Successfully analyzed</div>
          </div>
        </div>

        {/* Per-Chain Breakdown */}
        <div className="space-y-3">
          <h3 className="text-lg font-semibold text-white mb-3">Chain Breakdown</h3>
          {multiChainResults.results.map((result) => (
            <div key={result.chain} className="bg-slate-900/30 rounded-lg p-4 border border-slate-700">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center gap-2">
                  <span className="text-2xl">{getChainIcon(result.chain)}</span>
                  <span className="text-lg font-semibold text-white capitalize">{result.chain}</span>
                </div>
                <Badge className="bg-green-900/50 text-green-300">Active</Badge>
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <div className="text-gray-400">Sent</div>
                  <div className="text-white font-semibold">{formatNumber(result.totalSent)}</div>
                </div>
                <div>
                  <div className="text-gray-400">Received</div>
                  <div className="text-white font-semibold">{formatNumber(result.totalReceived)}</div>
                </div>
                <div>
                  <div className="text-gray-400">Net Balance</div>
                  <div className={`font-semibold ${result.netBalance >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {result.netBalance >= 0 ? '+' : ''}{formatNumber(result.netBalance)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Transactions</div>
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

// Transactions Table
export const TransactionsTable = ({ transactions, chain, selectedChain, onExport, isPremium }) => {
  if (!transactions || transactions.length === 0) return null;

  const currentChain = chain || selectedChain;
  const symbol = getChainSymbol(currentChain);

  const getExplorerUrl = (hash) => {
    const explorers = {
      ethereum: `https://etherscan.io/tx/${hash}`,
      bitcoin: `https://blockchain.info/tx/${hash}`,
      polygon: `https://polygonscan.com/tx/${hash}`,
      arbitrum: `https://arbiscan.io/tx/${hash}`,
      bsc: `https://bscscan.com/tx/${hash}`,
      solana: `https://solscan.io/tx/${hash}`
    };
    return explorers[currentChain] || '#';
  };

  return (
    <Card className="bg-slate-800/50 border-slate-700" data-testid="transactions-table">
      <CardHeader>
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="text-white">Recent Transactions</CardTitle>
            <CardDescription className="text-gray-400">
              Showing up to 20 most recent transactions
            </CardDescription>
          </div>
          {isPremium && onExport && (
            <Button
              onClick={onExport}
              variant="outline"
              className="border-slate-600 text-gray-300"
            >
              <Download className="w-4 h-4 mr-2" />
              Export CSV
            </Button>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-3 px-4 text-gray-400 font-medium">Type</th>
                <th className="text-left py-3 px-4 text-gray-400 font-medium">Hash</th>
                <th className="text-left py-3 px-4 text-gray-400 font-medium">Asset</th>
                <th className="text-right py-3 px-4 text-gray-400 font-medium">Amount</th>
                <th className="text-right py-3 px-4 text-gray-400 font-medium">USD Value</th>
                <th className="text-right py-3 px-4 text-gray-400 font-medium">Running Balance</th>
                <th className="text-left py-3 px-4 text-gray-400 font-medium">Address/Label</th>
              </tr>
            </thead>
            <tbody>
              {transactions.map((tx, idx) => (
                <tr key={idx} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                  <td className="py-3 px-4">
                    <Badge
                      variant="outline"
                      className={tx.type === 'sent' ? 'text-red-300 border-red-700' : 'text-green-300 border-green-700'}
                    >
                      {tx.type === 'sent' ? 'Sent' : 'Received'}
                    </Badge>
                  </td>
                  <td className="py-3 px-4">
                    {tx.hash ? (
                      <a
                        href={getExplorerUrl(tx.hash)}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-purple-400 hover:text-purple-300 font-mono text-sm"
                      >
                        {formatAddress(tx.hash)}
                      </a>
                    ) : (
                      <span className="text-gray-500 text-sm">N/A</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-white font-medium">{tx.asset}</span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className="text-white font-mono">{formatNumber(tx.value)}</span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    {tx.value_usd !== undefined ? (
                      <span className="text-gray-300 font-semibold">{formatUSD(tx.value_usd)}</span>
                    ) : (
                      <span className="text-gray-500 text-sm">-</span>
                    )}
                  </td>
                  <td className="py-3 px-4 text-right">
                    {tx.running_balance !== undefined ? (
                      <span className="text-blue-300 font-semibold font-mono">{formatNumber(tx.running_balance)}</span>
                    ) : (
                      <span className="text-gray-500 text-sm">-</span>
                    )}
                  </td>
                  <td className="py-3 px-4">
                    <div className="flex flex-col">
                      {tx.type === 'sent' && tx.to_label && (
                        <Badge variant="outline" className="text-blue-300 border-blue-700 mb-1 w-fit">
                          {tx.to_label}
                        </Badge>
                      )}
                      {tx.type === 'received' && tx.from_label && (
                        <Badge variant="outline" className="text-blue-300 border-blue-700 mb-1 w-fit">
                          {tx.from_label}
                        </Badge>
                      )}
                      <span className="text-gray-400 font-mono text-sm">
                        {tx.type === 'sent' ? formatAddress(tx.to) : formatAddress(tx.from)}
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
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
          <Badge className="bg-purple-600 ml-2">Premium</Badge>
        </CardTitle>
        <CardDescription className="text-gray-400">
          Deeper insights into your wallet activity
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Average Transaction Value */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Avg Transaction Value</div>
            <div className="text-2xl font-bold text-white">
              {formatNumber(
                (analysis.totalEthReceived + analysis.totalEthSent) /
                Math.max(1, analysis.incomingTransactionCount + analysis.outgoingTransactionCount)
              )} {symbol}
            </div>
            <div className="text-xs text-gray-500 mt-1">Per transaction</div>
          </div>

          {/* Activity Ratio */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Activity Ratio</div>
            <div className="text-2xl font-bold text-white">
              {analysis.outgoingTransactionCount > 0
                ? (analysis.incomingTransactionCount / analysis.outgoingTransactionCount).toFixed(2)
                : analysis.incomingTransactionCount.toFixed(2)}:1
            </div>
            <div className="text-xs text-gray-500 mt-1">Incoming : Outgoing</div>
          </div>

          {/* Unique Assets */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Unique Assets</div>
            <div className="text-2xl font-bold text-white">
              {1 + new Set([
                ...Object.keys(analysis.tokensReceived || {}),
                ...Object.keys(analysis.tokensSent || {})
              ]).size}
            </div>
            <div className="text-xs text-gray-500 mt-1">Native + Tokens</div>
          </div>

          {/* Gas Efficiency (EVM only) */}
          {['ethereum', 'arbitrum', 'polygon', 'bsc'].includes(chain) && analysis.totalGasFees > 0 && (
            <div className="bg-slate-900/50 rounded-lg p-4">
              <div className="text-sm text-gray-400 mb-1">Avg Gas per TX</div>
              <div className="text-2xl font-bold text-white">
                {formatNumber(analysis.totalGasFees / Math.max(1, analysis.outgoingTransactionCount))} {symbol}
              </div>
              <div className="text-xs text-gray-500 mt-1">Average gas cost</div>
            </div>
          )}

          {/* Net Flow */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Net Flow</div>
            <div className={`text-2xl font-bold ${analysis.netEth >= 0 ? 'text-green-400' : 'text-red-400'}`}>
              {analysis.netEth >= 0 ? '+' : ''}{formatNumber(analysis.netEth)} {symbol}
            </div>
            <div className="text-xs text-gray-500 mt-1">
              {analysis.netEth >= 0 ? 'Net accumulation' : 'Net spending'}
            </div>
          </div>

          {/* Total Volume */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <div className="text-sm text-gray-400 mb-1">Total Volume</div>
            <div className="text-2xl font-bold text-white">
              {formatNumber(analysis.totalEthReceived + analysis.totalEthSent)} {symbol}
            </div>
            <div className="text-xs text-gray-500 mt-1">Combined flow</div>
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
    <Card className="bg-slate-800/50 border-slate-700" data-testid="tokens-card">
      <CardHeader>
        <CardTitle className="text-white">ERC-20 Token Activity</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          {Object.keys(tokensReceived || {}).length > 0 && (
            <div>
              <h3 className="text-green-300 font-semibold mb-3">Tokens Received</h3>
              <div className="space-y-2">
                {Object.entries(tokensReceived).map(([token, amount]) => (
                  <div key={token} className="flex items-center justify-between bg-green-900/10 p-2 rounded">
                    <Badge variant="outline" className="text-green-300 border-green-700">{token}</Badge>
                    <span className="text-white font-mono text-sm">{formatNumber(amount)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
          {Object.keys(tokensSent || {}).length > 0 && (
            <div>
              <h3 className="text-red-300 font-semibold mb-3">Tokens Sent</h3>
              <div className="space-y-2">
                {Object.entries(tokensSent).map(([token, amount]) => (
                  <div key={token} className="flex items-center justify-between bg-red-900/10 p-2 rounded">
                    <Badge variant="outline" className="text-red-300 border-red-700">{token}</Badge>
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
