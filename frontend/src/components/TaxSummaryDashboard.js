import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, CheckCircle, RefreshCw, Download, Lock, Calendar, X } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';
import ValidationStatusPanel from './ValidationStatusPanel';
import UnknownTransactionClassifier from './UnknownTransactionClassifier';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Get available tax years (current year back to 2020)
const getAvailableYears = () => {
  const currentYear = new Date().getFullYear();
  const years = [];
  for (let year = currentYear; year >= 2020; year--) {
    years.push(year);
  }
  return years;
};

export const TaxSummaryDashboard = ({ onOpenExchangeModal: onAddData, onOpenChainOfCustody, onOpenReviewQueue }) => {
  const { getAuthHeader, user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [taxData, setTaxData] = useState(null);
  const [connections, setConnections] = useState([]);
  const [exchangeSummary, setExchangeSummary] = useState([]);
  const [portfolioByExchange, setPortfolioByExchange] = useState({});
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [showClassifier, setShowClassifier] = useState(false);
  const availableYears = getAvailableYears();

  useEffect(() => {
    fetchTaxSummary();
  }, [selectedYear]); // Refetch when year changes

  const fetchTaxSummary = async () => {
    setLoading(true);
    try {
      // Fetch connections
      const connResponse = await axios.get(`${API}/exchanges/api-connections`, {
        headers: getAuthHeader()
      });
      setConnections(connResponse.data.connections || []);

      // Fetch transactions to count per exchange
      const txResponse = await axios.get(`${API}/exchanges/transactions?limit=10000`, {
        headers: getAuthHeader()
      });
      const allTransactions = txResponse.data.transactions || [];
      
      // Filter transactions by selected year
      const yearStart = new Date(selectedYear, 0, 1);
      const yearEnd = new Date(selectedYear, 11, 31, 23, 59, 59);
      
      const transactions = allTransactions.filter(tx => {
        const txDate = new Date(tx.timestamp);
        return txDate >= yearStart && txDate <= yearEnd;
      });

      // Use end of tax year for unrealized gains valuation
      const asOfDate = `${selectedYear}-12-31`;

      // Fetch tax data with year filter and as_of_date for proper valuation
      const taxResponse = await axios.post(
        `${API}/tax/unified`,
        { 
          data_source: 'exchange_only',
          tax_year: selectedYear,
          as_of_date: asOfDate  // Value holdings at end of tax year
        },
        { headers: getAuthHeader() }
      );
      
      const data = taxResponse.data;
      setTaxData(data);

      // Build exchange summary - count transactions per exchange
      const byExchange = {};
      
      transactions.forEach(tx => {
        const exchange = (tx.exchange || 'unknown').toLowerCase();
        if (!byExchange[exchange]) {
          byExchange[exchange] = { count: 0, gainLoss: 0, portfolioValue: 0, assets: {} };
        }
        byExchange[exchange].count++;
      });

      // Fetch portfolio data from backend (calculates net holdings correctly)
      try {
        const portfolioResponse = await axios.get(`${API}/portfolio/by-exchange`, {
          headers: getAuthHeader()
        });
        const portfolioData = portfolioResponse.data;
        
        // Merge portfolio values into exchange summary
        (portfolioData.exchanges || []).forEach(exData => {
          const exchange = exData.exchange.toLowerCase();
          if (byExchange[exchange]) {
            byExchange[exchange].portfolioValue = exData.portfolio_value || 0;
            byExchange[exchange].assets = {};
            (exData.assets || []).forEach(a => {
              byExchange[exchange].assets[a.asset] = { amount: a.amount, value: a.value };
            });
          } else {
            byExchange[exchange] = {
              count: 0,
              gainLoss: 0,
              portfolioValue: exData.portfolio_value || 0,
              assets: {}
            };
            (exData.assets || []).forEach(a => {
              byExchange[exchange].assets[a.asset] = { amount: a.amount, value: a.value };
            });
          }
        });
      } catch (portfolioError) {
        console.log('Could not fetch portfolio data:', portfolioError);
      }

      // Also include remaining lots if available (fallback)
      const remainingLots = data?.tax_data?.unrealized?.lots || [];
      remainingLots.forEach(lot => {
        const exchange = (lot.exchange || 'unknown').toLowerCase();
        const currentValue = lot.current_value || 0;
        
        // Only add if we don't already have portfolio data from transactions
        if (byExchange[exchange] && byExchange[exchange].portfolioValue === 0) {
          byExchange[exchange].portfolioValue += currentValue;
        }
      });

      // Add gain/loss from realized gains
      const realizedGains = data?.tax_data?.realized_gains || [];
      realizedGains.forEach(gain => {
        // Try to find the exchange from the gain data
        // Priority: gain.exchange > gain.sell_source > gain.buy_source > gain.source > raw_data.exchange
        let exchange = 'unknown';
        
        if (gain.exchange && gain.exchange !== 'wallet' && gain.exchange !== 'unknown') {
          exchange = gain.exchange.toLowerCase();
        } else if (gain.sell_source) {
          // sell_source is in format "exchange:coinbase" or "wallet"
          exchange = gain.sell_source.replace('exchange:', '').toLowerCase();
        } else if (gain.buy_source) {
          exchange = gain.buy_source.replace('exchange:', '').toLowerCase();
        } else if (gain.source) {
          exchange = gain.source.replace('exchange:', '').toLowerCase();
        }
        
        // Fallback: try raw_data
        if (exchange === 'unknown' && gain.raw_data?.exchange) {
          exchange = gain.raw_data.exchange.toLowerCase();
        }
        
        // Check sell_exchange and buy_exchange fields (also set by FIFO)
        if (exchange === 'unknown' && gain.sell_exchange) {
          exchange = gain.sell_exchange.toLowerCase();
        }
        if (exchange === 'unknown' && gain.buy_exchange) {
          exchange = gain.buy_exchange.toLowerCase();
        }
        
        if (!byExchange[exchange]) {
          byExchange[exchange] = { count: 0, gainLoss: 0 };
        }
        byExchange[exchange].gainLoss += gain.gain_loss || 0;
      });

      // If all gains are in "unknown", try to distribute based on transaction counts
      const unknownGains = byExchange['unknown']?.gainLoss || 0;
      const hasRealExchanges = Object.keys(byExchange).some(k => k !== 'unknown' && byExchange[k].count > 0);
      
      if (unknownGains > 0 && hasRealExchanges && Object.keys(byExchange).filter(k => k !== 'unknown').every(k => byExchange[k].gainLoss === 0)) {
        // Redistribute unknown gains proportionally to transaction counts
        const totalTx = Object.entries(byExchange)
          .filter(([k]) => k !== 'unknown')
          .reduce((sum, [, v]) => sum + v.count, 0);
        
        if (totalTx > 0) {
          Object.keys(byExchange).forEach(exchange => {
            if (exchange !== 'unknown' && byExchange[exchange].count > 0) {
              const proportion = byExchange[exchange].count / totalTx;
              byExchange[exchange].gainLoss = unknownGains * proportion;
            }
          });
          // Remove or zero out unknown
          delete byExchange['unknown'];
        }
      }

      setExchangeSummary(Object.entries(byExchange)
        .filter(([name]) => name !== 'unknown' || byExchange[name].count > 0 || byExchange[name].gainLoss !== 0)
        .map(([name, data]) => ({
          name,
          transactions: data.count,
          gainLoss: data.gainLoss,
          portfolioValue: data.portfolioValue || 0,
          assets: data.assets || {}
        }))
        .sort((a, b) => b.portfolioValue - a.portfolioValue || b.transactions - a.transactions)
      );

    } catch (err) {
      console.error('Failed to fetch tax summary:', err);
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount) => {
    if (amount === null || amount === undefined) return '$0.00';
    const formatted = Math.abs(amount).toLocaleString('en-US', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
    return amount < 0 ? `-$${formatted}` : `$${formatted}`;
  };

  const totalTransactions = exchangeSummary.reduce((sum, ex) => sum + ex.transactions, 0);
  const totalGainLoss = exchangeSummary.reduce((sum, ex) => sum + ex.gainLoss, 0);
  
  const shortTermGain = taxData?.tax_data?.summary?.short_term_gains || 0;
  const longTermGain = taxData?.tax_data?.summary?.long_term_gains || 0;
  const cryptoIncome = taxData?.tax_data?.summary?.total_income || 0;

  const isPaidUser = user?.subscription_tier !== 'free';

  if (loading) {
    return (
      <Card className="bg-gray-800 border-gray-700 shadow-sm">
        <CardContent className="py-12 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-purple-400" />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Unknown Transaction Classifier Modal */}
      {showClassifier && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" data-testid="classifier-modal">
          <div className="bg-gray-900 rounded-lg w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold text-white">Unknown Transaction Classifier</h2>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowClassifier(false)}
                className="text-gray-400 hover:text-white"
                data-testid="close-classifier-btn"
              >
                <X className="w-5 h-5" />
              </Button>
            </div>
            <div className="flex-1 overflow-y-auto p-4">
              <UnknownTransactionClassifier 
                onClassificationComplete={(count) => {
                  console.log(`Classified ${count} transactions`);
                  fetchTaxSummary();
                }}
              />
            </div>
          </div>
        </div>
      )}

      {/* Tax Validation Status Panel */}
      <ValidationStatusPanel 
        apiUrl={BACKEND_URL}
        authHeader={getAuthHeader()}
        onRefresh={fetchTaxSummary}
        onOpenClassifier={() => setShowClassifier(true)}
        onOpenChainOfCustody={onOpenChainOfCustody}
        onOpenReviewQueue={onOpenReviewQueue}
      />

      {/* Header with Year Selector */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3 mb-1">
            <h2 className="text-2xl font-semibold text-white">Tax Summary</h2>
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value))}
              className="bg-gray-800 border border-gray-600 text-white rounded-md px-3 py-1 text-sm font-medium focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
            >
              {availableYears.map(year => (
                <option key={year} value={year}>{year}</option>
              ))}
            </select>
          </div>
          <div className="flex items-center gap-4 mt-2 text-sm text-gray-300">
            <span className="flex items-center gap-1">
              <CheckCircle className="w-4 h-4 text-green-400" />
              {connections.length} account{connections.length !== 1 ? 's' : ''} synced
            </span>
            <span className="flex items-center gap-1">
              <CheckCircle className="w-4 h-4 text-green-400" />
              {totalTransactions} transactions in {selectedYear}
            </span>
          </div>
        </div>
        <Button 
          variant="outline" 
          onClick={fetchTaxSummary}
          className="border-gray-500 text-white bg-gray-700 hover:bg-gray-600"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-gray-800 border-gray-700 shadow-sm">
          <CardContent className="p-6">
            <p className="text-sm text-gray-400 mb-2">Short term capital gain</p>
            <div className="flex items-center gap-2">
              <span className={`text-2xl font-semibold ${shortTermGain >= 0 ? 'text-white' : 'text-red-400'}`}>
                {formatCurrency(shortTermGain)}
              </span>
              {!isPaidUser && <Lock className="w-4 h-4 text-gray-500" />}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gray-800 border-gray-700 shadow-sm">
          <CardContent className="p-6">
            <p className="text-sm text-gray-400 mb-2">Long term capital gain</p>
            <div className="flex items-center gap-2">
              <span className={`text-2xl font-semibold ${longTermGain >= 0 ? 'text-white' : 'text-red-400'}`}>
                {formatCurrency(longTermGain)}
              </span>
              {!isPaidUser && <Lock className="w-4 h-4 text-gray-500" />}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-gray-800 border-gray-700 shadow-sm">
          <CardContent className="p-6">
            <p className="text-sm text-gray-400 mb-2">Crypto income</p>
            <span className="text-2xl font-semibold text-white">
              {formatCurrency(cryptoIncome)}
            </span>
            <p className="text-xs text-gray-500 mt-1">Staking rewards, airdrops</p>
          </CardContent>
        </Card>
      </div>

      {/* Cost Basis Breakdown - NEW */}
      {taxData?.tax_data?.cost_basis_breakdown && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <Card className="bg-gray-800 border-gray-700 shadow-sm">
            <CardContent className="p-6">
              <p className="text-sm text-gray-400 mb-2">Cost Basis from Purchases</p>
              <span className="text-xl font-semibold text-white">
                {formatCurrency(taxData.tax_data.cost_basis_breakdown.purchases || 0)}
              </span>
              <p className="text-xs text-gray-500 mt-1">Actual USD spent on buys</p>
            </CardContent>
          </Card>

          <Card className="bg-gray-800 border-gray-700 shadow-sm">
            <CardContent className="p-6">
              <p className="text-sm text-gray-400 mb-2">Cost Basis from Income</p>
              <span className="text-xl font-semibold text-white">
                {formatCurrency(taxData.tax_data.cost_basis_breakdown.income || 0)}
              </span>
              <p className="text-xs text-gray-500 mt-1">FMV of rewards when received</p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Account Breakdown Table */}
      <Card className="bg-gray-800 border-gray-700 shadow-sm">
        <CardContent className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left py-4 px-6 text-sm font-medium text-gray-400">Account</th>
                <th className="text-center py-4 px-6 text-sm font-medium text-gray-400">Transactions</th>
                <th className="text-right py-4 px-6 text-sm font-medium text-gray-400">Portfolio Value</th>
                <th className="text-right py-4 px-6 text-sm font-medium text-gray-400">Gain/Loss</th>
              </tr>
            </thead>
            <tbody>
              {exchangeSummary.length === 0 ? (
                <tr>
                  <td colSpan={4} className="py-8 text-center text-gray-400">
                    No accounts connected yet.{' '}
                    <button 
                      onClick={onAddData}
                      className="text-purple-400 hover:underline"
                    >
                      Add your data
                    </button>
                  </td>
                </tr>
              ) : (
                <>
                  {exchangeSummary.map((exchange, idx) => (
                    <tr key={idx} className="border-b border-gray-700 hover:bg-gray-700/50">
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-purple-900/50 flex items-center justify-center">
                            <span className="text-purple-400 font-semibold text-sm">
                              {exchange.name.charAt(0).toUpperCase()}
                            </span>
                          </div>
                          <div>
                            <span className="font-medium text-white capitalize">{exchange.name}</span>
                            {Object.keys(exchange.assets || {}).length > 0 && (
                              <p className="text-xs text-gray-500">
                                {Object.keys(exchange.assets).length} asset{Object.keys(exchange.assets).length !== 1 ? 's' : ''}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="py-4 px-6 text-center text-gray-300">{exchange.transactions}</td>
                      <td className="py-4 px-6 text-right font-medium text-white">
                        {formatCurrency(exchange.portfolioValue)}
                      </td>
                      <td className={`py-4 px-6 text-right font-medium ${exchange.gainLoss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {formatCurrency(exchange.gainLoss)}
                      </td>
                    </tr>
                  ))}
                  <tr className="bg-gray-900/50">
                    <td className="py-4 px-6 font-semibold text-white">Total</td>
                    <td className="py-4 px-6 text-center font-semibold text-white">{totalTransactions}</td>
                    <td className="py-4 px-6 text-right font-semibold text-white">
                      {formatCurrency(exchangeSummary.reduce((sum, ex) => sum + (ex.portfolioValue || 0), 0))}
                    </td>
                    <td className={`py-4 px-6 text-right font-semibold ${totalGainLoss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatCurrency(totalGainLoss)}
                    </td>
                  </tr>
                </>
              )}
            </tbody>
          </table>
        </CardContent>
      </Card>

      {/* Export Button */}
      {exchangeSummary.length > 0 && (
        <div className="flex justify-end">
          <Button 
            className="bg-purple-600 hover:bg-purple-700 text-white"
            onClick={async () => {
              try {
                const response = await axios.post(
                  `${API}/tax/export-form-8949`,
                  { 
                    tax_year: selectedYear,
                    format: 'csv',
                    data_source: 'exchange_only'
                  },
                  { 
                    headers: getAuthHeader(),
                    responseType: 'blob'
                  }
                );
                
                // Create download link
                const url = window.URL.createObjectURL(new Blob([response.data]));
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', `tax-report-${selectedYear}.csv`);
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(url);
              } catch (err) {
                console.error('Export failed:', err);
                alert(`No tax data found for ${selectedYear}. Try selecting a different year.`);
              }
            }}
          >
            <Download className="w-4 h-4 mr-2" />
            Download {selectedYear} Tax Report
          </Button>
        </div>
      )}
    </div>
  );
};
