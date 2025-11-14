import React, { useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, DollarSign, FileText, Download, TrendingUp, TrendingDown, Calendar } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const TaxDashboard = ({ 
  walletAddress, 
  selectedChain, 
  getAuthHeader,
  analysis 
}) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [taxSummary, setTaxSummary] = useState(null);
  const [form8949, setForm8949] = useState(null);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());

  const formatUSD = (num) => {
    if (num === undefined || num === null) return '$0.00';
    return new Intl.NumberFormat('en-US', {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(num);
  };

  const fetchTaxSummary = async () => {
    if (!walletAddress) {
      setError('Please analyze a wallet first');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(
        `${API}/tax/summary`,
        {
          address: walletAddress,
          chain: selectedChain
        },
        { headers: getAuthHeader() }
      );

      setTaxSummary(response.data);
    } catch (err) {
      console.error('Error fetching tax summary:', err);
      setError(err.response?.data?.detail || 'Failed to fetch tax summary');
    } finally {
      setLoading(false);
    }
  };

  const generateForm8949 = async (year) => {
    if (!walletAddress) {
      setError('Please analyze a wallet first');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const response = await axios.post(
        `${API}/tax/form-8949`,
        {
          address: walletAddress,
          chain: selectedChain,
          start_date: `${year}-01-01`,
          end_date: `${year}-12-31`
        },
        { headers: getAuthHeader() }
      );

      setForm8949(response.data);
    } catch (err) {
      console.error('Error generating Form 8949:', err);
      setError(err.response?.data?.detail || 'Failed to generate Form 8949');
    } finally {
      setLoading(false);
    }
  };

  const downloadForm8949CSV = () => {
    if (!form8949) return;

    // Create CSV content
    let csv = 'IRS Form 8949 - Sales and Other Dispositions of Capital Assets\n\n';
    csv += `Tax Year: ${form8949.tax_year}\n\n`;
    
    // Short-term transactions
    csv += 'PART I - SHORT-TERM CAPITAL GAINS AND LOSSES\n';
    csv += 'Description,Date Acquired,Date Sold,Proceeds,Cost Basis,Gain/Loss\n';
    form8949.part_1_short_term.transactions.forEach(t => {
      csv += `"${t.description}","${t.date_acquired}","${t.date_sold}",${t.proceeds},${t.cost_basis},${t.gain_or_loss}\n`;
    });
    csv += `\nTOTALS,,,${form8949.part_1_short_term.totals.proceeds},${form8949.part_1_short_term.totals.cost_basis},${form8949.part_1_short_term.totals.gain_or_loss}\n\n`;
    
    // Long-term transactions
    csv += 'PART II - LONG-TERM CAPITAL GAINS AND LOSSES\n';
    csv += 'Description,Date Acquired,Date Sold,Proceeds,Cost Basis,Gain/Loss\n';
    form8949.part_2_long_term.transactions.forEach(t => {
      csv += `"${t.description}","${t.date_acquired}","${t.date_sold}",${t.proceeds},${t.cost_basis},${t.gain_or_loss}\n`;
    });
    csv += `\nTOTALS,,,${form8949.part_2_long_term.totals.proceeds},${form8949.part_2_long_term.totals.cost_basis},${form8949.part_2_long_term.totals.gain_or_loss}\n`;

    // Create download link
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `form-8949-${form8949.tax_year}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    window.URL.revokeObjectURL(url);
  };

  const currentYear = new Date().getFullYear();
  const years = [currentYear - 2, currentYear - 1, currentYear];

  return (
    <div className="space-y-6">
      {/* Tax Dashboard Header */}
      <Card className="bg-gradient-to-br from-purple-900/30 to-indigo-800/20 border-purple-700">
        <CardHeader>
          <CardTitle className="text-white flex items-center gap-2">
            <FileText className="w-6 h-6 text-purple-400" />
            Tax Dashboard
            <Badge className="bg-purple-600 ml-2">Premium</Badge>
          </CardTitle>
          <CardDescription className="text-gray-400">
            Comprehensive tax reporting and IRS form generation
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-4">
            <Button
              onClick={fetchTaxSummary}
              disabled={loading || !walletAddress}
              className="bg-purple-600 hover:bg-purple-700"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Loading...
                </>
              ) : (
                <>
                  <Calendar className="mr-2 h-4 w-4" />
                  Load Multi-Year Summary
                </>
              )}
            </Button>

            {years.map(year => (
              <Button
                key={year}
                onClick={() => {
                  setSelectedYear(year);
                  generateForm8949(year);
                }}
                disabled={loading || !walletAddress}
                variant="outline"
                className="border-purple-600 text-purple-300 hover:bg-purple-900/30"
              >
                Generate Form 8949 ({year})
              </Button>
            ))}
          </div>

          {error && (
            <Alert className="mt-4 bg-red-900/20 border-red-900 text-red-300">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>

      {/* Tax Summary by Year */}
      {taxSummary && (
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader>
            <CardTitle className="text-white">Tax Summary by Year</CardTitle>
            <CardDescription className="text-gray-400">
              Capital gains breakdown across multiple tax years
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {Object.entries(taxSummary.tax_years || {}).map(([year, data]) => (
                <div key={year} className="bg-slate-900/50 rounded-lg p-4 border border-slate-700">
                  <div className="flex items-center justify-between mb-3">
                    <h3 className="text-xl font-bold text-white">{year}</h3>
                    <Badge className="bg-indigo-600">
                      {data.transactions} transaction{data.transactions !== 1 ? 's' : ''}
                    </Badge>
                  </div>
                  
                  <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <div className="bg-orange-900/20 rounded-lg p-3 border border-orange-700">
                      <div className="text-xs text-orange-300 mb-1">Short-Term Gains</div>
                      <div className={`text-2xl font-bold ${data.short_term_gains >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {data.short_term_gains >= 0 ? '+' : ''}{formatUSD(data.short_term_gains)}
                      </div>
                    </div>
                    
                    <div className="bg-blue-900/20 rounded-lg p-3 border border-blue-700">
                      <div className="text-xs text-blue-300 mb-1">Long-Term Gains</div>
                      <div className={`text-2xl font-bold ${data.long_term_gains >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {data.long_term_gains >= 0 ? '+' : ''}{formatUSD(data.long_term_gains)}
                      </div>
                    </div>
                    
                    <div className="bg-emerald-900/20 rounded-lg p-3 border border-emerald-700">
                      <div className="text-xs text-emerald-300 mb-1">Total Gain/Loss</div>
                      <div className={`text-2xl font-bold ${data.total_gain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                        {data.total_gain >= 0 ? '+' : ''}{formatUSD(data.total_gain)}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>

            {/* Overall Summary */}
            {taxSummary.overall_summary && (
              <div className="mt-6 bg-gradient-to-r from-indigo-900/30 to-purple-900/30 rounded-lg p-4 border border-indigo-700">
                <h3 className="text-white font-semibold mb-3">Overall Portfolio Summary</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                  <div>
                    <div className="text-gray-400">Total Realized</div>
                    <div className={`text-lg font-bold ${taxSummary.overall_summary.total_realized_gain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatUSD(taxSummary.overall_summary.total_realized_gain)}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Total Unrealized</div>
                    <div className={`text-lg font-bold ${taxSummary.overall_summary.total_unrealized_gain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                      {formatUSD(taxSummary.overall_summary.total_unrealized_gain)}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Buys</div>
                    <div className="text-lg font-bold text-white">
                      {taxSummary.overall_summary.buy_count}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Sells</div>
                    <div className="text-lg font-bold text-white">
                      {taxSummary.overall_summary.sell_count}
                    </div>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Form 8949 Data */}
      {form8949 && (
        <Card className="bg-slate-800/50 border-slate-700">
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="text-white">IRS Form 8949 - {form8949.tax_year}</CardTitle>
                <CardDescription className="text-gray-400">
                  Sales and Other Dispositions of Capital Assets
                </CardDescription>
              </div>
              <Button
                onClick={downloadForm8949CSV}
                className="bg-green-600 hover:bg-green-700"
              >
                <Download className="mr-2 h-4 w-4" />
                Download CSV
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {/* Short-Term Transactions */}
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-3">
                <Badge className="bg-orange-600">Part I: Short-Term</Badge>
                <span className="text-gray-400 text-sm">
                  {form8949.part_1_short_term.transactions.length} transaction(s)
                </span>
              </div>
              
              {form8949.part_1_short_term.transactions.length > 0 ? (
                <div className="bg-slate-900/50 rounded-lg p-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700">
                        <th className="text-left py-2 text-gray-400">Description</th>
                        <th className="text-left py-2 text-gray-400">Date Acquired</th>
                        <th className="text-left py-2 text-gray-400">Date Sold</th>
                        <th className="text-right py-2 text-gray-400">Proceeds</th>
                        <th className="text-right py-2 text-gray-400">Cost Basis</th>
                        <th className="text-right py-2 text-gray-400">Gain/Loss</th>
                      </tr>
                    </thead>
                    <tbody>
                      {form8949.part_1_short_term.transactions.map((tx, idx) => (
                        <tr key={idx} className="border-b border-slate-700/50">
                          <td className="py-2 text-white">{tx.description}</td>
                          <td className="py-2 text-gray-300">{tx.date_acquired}</td>
                          <td className="py-2 text-gray-300">{tx.date_sold}</td>
                          <td className="py-2 text-right text-white">{formatUSD(tx.proceeds)}</td>
                          <td className="py-2 text-right text-white">{formatUSD(tx.cost_basis)}</td>
                          <td className={`py-2 text-right font-semibold ${tx.gain_or_loss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {formatUSD(tx.gain_or_loss)}
                          </td>
                        </tr>
                      ))}
                      <tr className="border-t-2 border-orange-700 font-bold">
                        <td colSpan="3" className="py-2 text-white">TOTALS</td>
                        <td className="py-2 text-right text-white">{formatUSD(form8949.part_1_short_term.totals.proceeds)}</td>
                        <td className="py-2 text-right text-white">{formatUSD(form8949.part_1_short_term.totals.cost_basis)}</td>
                        <td className={`py-2 text-right ${form8949.part_1_short_term.totals.gain_or_loss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatUSD(form8949.part_1_short_term.totals.gain_or_loss)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-400 text-sm">No short-term transactions for this year</p>
              )}
            </div>

            {/* Long-Term Transactions */}
            <div>
              <div className="flex items-center gap-2 mb-3">
                <Badge className="bg-blue-600">Part II: Long-Term</Badge>
                <span className="text-gray-400 text-sm">
                  {form8949.part_2_long_term.transactions.length} transaction(s)
                </span>
              </div>
              
              {form8949.part_2_long_term.transactions.length > 0 ? (
                <div className="bg-slate-900/50 rounded-lg p-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-slate-700">
                        <th className="text-left py-2 text-gray-400">Description</th>
                        <th className="text-left py-2 text-gray-400">Date Acquired</th>
                        <th className="text-left py-2 text-gray-400">Date Sold</th>
                        <th className="text-right py-2 text-gray-400">Proceeds</th>
                        <th className="text-right py-2 text-gray-400">Cost Basis</th>
                        <th className="text-right py-2 text-gray-400">Gain/Loss</th>
                      </tr>
                    </thead>
                    <tbody>
                      {form8949.part_2_long_term.transactions.map((tx, idx) => (
                        <tr key={idx} className="border-b border-slate-700/50">
                          <td className="py-2 text-white">{tx.description}</td>
                          <td className="py-2 text-gray-300">{tx.date_acquired}</td>
                          <td className="py-2 text-gray-300">{tx.date_sold}</td>
                          <td className="py-2 text-right text-white">{formatUSD(tx.proceeds)}</td>
                          <td className="py-2 text-right text-white">{formatUSD(tx.cost_basis)}</td>
                          <td className={`py-2 text-right font-semibold ${tx.gain_or_loss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {formatUSD(tx.gain_or_loss)}
                          </td>
                        </tr>
                      ))}
                      <tr className="border-t-2 border-blue-700 font-bold">
                        <td colSpan="3" className="py-2 text-white">TOTALS</td>
                        <td className="py-2 text-right text-white">{formatUSD(form8949.part_2_long_term.totals.proceeds)}</td>
                        <td className="py-2 text-right text-white">{formatUSD(form8949.part_2_long_term.totals.cost_basis)}</td>
                        <td className={`py-2 text-right ${form8949.part_2_long_term.totals.gain_or_loss >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                          {formatUSD(form8949.part_2_long_term.totals.gain_or_loss)}
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>
              ) : (
                <p className="text-gray-400 text-sm">No long-term transactions for this year</p>
              )}
            </div>

            {/* Summary Card */}
            <div className="mt-6 bg-gradient-to-r from-green-900/30 to-emerald-900/30 rounded-lg p-4 border border-green-700">
              <h4 className="text-white font-semibold mb-3">Form 8949 Summary</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
                <div>
                  <div className="text-gray-400">Short-Term Total</div>
                  <div className={`text-lg font-bold ${form8949.summary.total_short_term_gain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatUSD(form8949.summary.total_short_term_gain)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Long-Term Total</div>
                  <div className={`text-lg font-bold ${form8949.summary.total_long_term_gain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatUSD(form8949.summary.total_long_term_gain)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Net Gain/Loss</div>
                  <div className={`text-lg font-bold ${form8949.summary.total_gain >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                    {formatUSD(form8949.summary.total_gain)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Total Transactions</div>
                  <div className="text-lg font-bold text-white">
                    {form8949.summary.transaction_count}
                  </div>
                </div>
              </div>
            </div>

            {/* Disclaimer */}
            <Alert className="mt-4 bg-yellow-900/20 border-yellow-700">
              <AlertDescription className="text-yellow-300 text-xs">
                <strong>Important:</strong> This Form 8949 data is for informational purposes only. 
                Please consult with a qualified tax professional before filing your taxes. 
                Additional forms (Schedule D, Form 1040) may be required.
              </AlertDescription>
            </Alert>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
