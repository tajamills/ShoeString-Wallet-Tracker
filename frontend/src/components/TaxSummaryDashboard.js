import React, { useState, useEffect } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Loader2, CheckCircle, RefreshCw, Download, Lock } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const TaxSummaryDashboard = ({ onOpenExchangeModal }) => {
  const { getAuthHeader, user } = useAuth();
  const [loading, setLoading] = useState(true);
  const [taxData, setTaxData] = useState(null);
  const [connections, setConnections] = useState([]);
  const [exchangeSummary, setExchangeSummary] = useState([]);

  useEffect(() => {
    fetchTaxSummary();
  }, []);

  const fetchTaxSummary = async () => {
    setLoading(true);
    try {
      // Fetch connections
      const connResponse = await axios.get(`${API}/exchanges/api-connections`, {
        headers: getAuthHeader()
      });
      setConnections(connResponse.data.connections || []);

      // Fetch tax data
      const taxResponse = await axios.post(
        `${API}/tax/unified`,
        { data_source: 'exchange_only' },
        { headers: getAuthHeader() }
      );
      
      const data = taxResponse.data;
      setTaxData(data);

      // Calculate exchange summary from transactions
      const txResponse = await axios.get(`${API}/exchanges/transactions?limit=10000`, {
        headers: getAuthHeader()
      });
      
      const transactions = txResponse.data.transactions || [];
      const byExchange = {};
      
      transactions.forEach(tx => {
        const exchange = tx.exchange || 'unknown';
        if (!byExchange[exchange]) {
          byExchange[exchange] = { count: 0, gainLoss: 0 };
        }
        byExchange[exchange].count++;
      });

      // Add gain/loss from tax data if available
      const realizedGains = data?.tax_data?.realized_gains || [];
      realizedGains.forEach(gain => {
        const exchange = gain.exchange || 'unknown';
        if (!byExchange[exchange]) {
          byExchange[exchange] = { count: 0, gainLoss: 0 };
        }
        byExchange[exchange].gainLoss += gain.gain_loss || 0;
      });

      setExchangeSummary(Object.entries(byExchange).map(([name, data]) => ({
        name,
        transactions: data.count,
        gainLoss: data.gainLoss
      })));

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
      <Card className="bg-white border-gray-200 shadow-sm">
        <CardContent className="py-12 flex items-center justify-center">
          <Loader2 className="h-8 w-8 animate-spin text-purple-600" />
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-gray-900">You're on track to file with confidence</h2>
          <div className="flex items-center gap-4 mt-2 text-sm text-gray-600">
            <span className="flex items-center gap-1">
              <CheckCircle className="w-4 h-4 text-green-500" />
              {connections.length} account{connections.length !== 1 ? 's' : ''} synced
            </span>
            <span className="flex items-center gap-1">
              <CheckCircle className="w-4 h-4 text-green-500" />
              {totalTransactions} transactions tracked
            </span>
          </div>
        </div>
        <Button 
          variant="outline" 
          onClick={fetchTaxSummary}
          className="border-gray-300 text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card className="bg-white border-gray-200 shadow-sm">
          <CardContent className="p-6">
            <p className="text-sm text-gray-500 mb-2">Short term capital gain</p>
            <div className="flex items-center gap-2">
              <span className={`text-2xl font-semibold ${shortTermGain >= 0 ? 'text-gray-900' : 'text-red-600'}`}>
                {formatCurrency(shortTermGain)}
              </span>
              {!isPaidUser && <Lock className="w-4 h-4 text-gray-400" />}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200 shadow-sm">
          <CardContent className="p-6">
            <p className="text-sm text-gray-500 mb-2">Long term capital gain</p>
            <div className="flex items-center gap-2">
              <span className={`text-2xl font-semibold ${longTermGain >= 0 ? 'text-gray-900' : 'text-red-600'}`}>
                {formatCurrency(longTermGain)}
              </span>
              {!isPaidUser && <Lock className="w-4 h-4 text-gray-400" />}
            </div>
          </CardContent>
        </Card>

        <Card className="bg-white border-gray-200 shadow-sm">
          <CardContent className="p-6">
            <p className="text-sm text-gray-500 mb-2">Crypto income</p>
            <span className="text-2xl font-semibold text-gray-900">
              {formatCurrency(cryptoIncome)}
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Account Breakdown Table */}
      <Card className="bg-white border-gray-200 shadow-sm">
        <CardContent className="p-0">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200">
                <th className="text-left py-4 px-6 text-sm font-medium text-gray-500">Account</th>
                <th className="text-center py-4 px-6 text-sm font-medium text-gray-500">2025 transactions</th>
                <th className="text-right py-4 px-6 text-sm font-medium text-gray-500">Preliminary gain/loss</th>
              </tr>
            </thead>
            <tbody>
              {exchangeSummary.length === 0 ? (
                <tr>
                  <td colSpan={3} className="py-8 text-center text-gray-500">
                    No accounts connected yet.{' '}
                    <button 
                      onClick={onOpenExchangeModal}
                      className="text-purple-600 hover:underline"
                    >
                      Connect an exchange
                    </button>
                  </td>
                </tr>
              ) : (
                <>
                  {exchangeSummary.map((exchange, idx) => (
                    <tr key={idx} className="border-b border-gray-100">
                      <td className="py-4 px-6">
                        <div className="flex items-center gap-3">
                          <div className="w-8 h-8 rounded-full bg-purple-100 flex items-center justify-center">
                            <span className="text-purple-600 font-semibold text-sm">
                              {exchange.name.charAt(0).toUpperCase()}
                            </span>
                          </div>
                          <span className="font-medium text-gray-900 capitalize">{exchange.name}</span>
                        </div>
                      </td>
                      <td className="py-4 px-6 text-center text-gray-700">{exchange.transactions}</td>
                      <td className={`py-4 px-6 text-right font-medium ${exchange.gainLoss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                        {formatCurrency(exchange.gainLoss)}
                      </td>
                    </tr>
                  ))}
                  <tr className="bg-gray-50">
                    <td className="py-4 px-6 font-semibold text-gray-900">Total</td>
                    <td className="py-4 px-6 text-center font-semibold text-gray-900">{totalTransactions}</td>
                    <td className={`py-4 px-6 text-right font-semibold ${totalGainLoss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
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
          <Button className="bg-purple-600 hover:bg-purple-700 text-white">
            <Download className="w-4 h-4 mr-2" />
            Download Tax Report
          </Button>
        </div>
      )}
    </div>
  );
};
