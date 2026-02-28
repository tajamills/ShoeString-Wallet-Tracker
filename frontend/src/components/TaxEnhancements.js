import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Input } from '@/components/ui/input';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue 
} from '@/components/ui/select';
import { 
  Loader2, 
  FileText, 
  Download,
  Calendar,
  Wand2,
  AlertCircle,
  Check
} from 'lucide-react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL;

export const ScheduleDExport = ({ 
  isOpen, 
  onClose, 
  address,
  chain,
  getAuthHeader 
}) => {
  const [taxYear, setTaxYear] = useState(new Date().getFullYear());
  const [format, setFormat] = useState('text');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [supportedYears, setSupportedYears] = useState([]);

  useEffect(() => {
    // Fetch supported tax years
    const fetchYears = async () => {
      try {
        const response = await axios.get(`${API}/api/tax/supported-years`);
        setSupportedYears(response.data.years);
        setTaxYear(response.data.current_year);
      } catch (err) {
        // Default years if API fails
        const currentYear = new Date().getFullYear();
        setSupportedYears(Array.from({ length: currentYear - 2019 }, (_, i) => 2020 + i));
      }
    };
    fetchYears();
  }, []);

  const handleExport = async () => {
    setLoading(true);
    setError('');

    try {
      const response = await axios.post(
        `${API}/api/tax/export-schedule-d`,
        {
          address,
          chain,
          tax_year: taxYear,
          format
        },
        { 
          headers: getAuthHeader(),
          responseType: 'blob'
        }
      );

      // Download the file
      const blob = new Blob([response.data], { 
        type: format === 'csv' ? 'text/csv' : 'text/plain' 
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `schedule-d-${address.substring(0, 8)}-${taxYear}.${format === 'csv' ? 'csv' : 'txt'}`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      onClose();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to export Schedule D');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-slate-800 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <FileText className="w-5 h-5 text-green-400" />
            Export Schedule D
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Generate IRS Schedule D summary for a specific tax year
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-300">Tax Year</label>
            <Select value={taxYear.toString()} onValueChange={(v) => setTaxYear(parseInt(v))}>
              <SelectTrigger className="bg-slate-900 border-slate-600 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-600">
                {supportedYears.map(year => (
                  <SelectItem key={year} value={year.toString()} className="text-white">
                    {year}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-300">Format</label>
            <Select value={format} onValueChange={setFormat}>
              <SelectTrigger className="bg-slate-900 border-slate-600 text-white">
                <SelectValue />
              </SelectTrigger>
              <SelectContent className="bg-slate-800 border-slate-600">
                <SelectItem value="text" className="text-white">
                  Text Summary (.txt)
                </SelectItem>
                <SelectItem value="csv" className="text-white">
                  CSV for Tax Software (.csv)
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <Alert className="bg-blue-900/20 border-blue-700 text-blue-300">
            <Calendar className="h-4 w-4" />
            <AlertDescription className="text-sm">
              Schedule D summarizes your capital gains and losses for the tax year.
              Only transactions with sell dates in {taxYear} will be included.
            </AlertDescription>
          </Alert>

          {error && (
            <Alert className="bg-red-900/20 border-red-700 text-red-300">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <div className="flex gap-3">
          <Button
            onClick={handleExport}
            disabled={loading}
            className="flex-1 bg-green-600 hover:bg-green-700"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Download className="mr-2 h-4 w-4" />
                Export Schedule D
              </>
            )}
          </Button>
          <Button
            onClick={onClose}
            variant="outline"
            className="border-slate-600"
            disabled={loading}
          >
            Cancel
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};

export const BatchCategorizationModal = ({
  isOpen,
  onClose,
  address,
  chain,
  getAuthHeader,
  onCategorized
}) => {
  const [rules, setRules] = useState([
    { type: 'tx_type', value: 'received', category: 'income' }
  ]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [result, setResult] = useState(null);

  const ruleTypes = [
    { value: 'tx_type', label: 'Transaction Type' },
    { value: 'address', label: 'Address Match' },
    { value: 'amount_gt', label: 'Amount Greater Than' },
    { value: 'amount_lt', label: 'Amount Less Than' },
    { value: 'asset', label: 'Asset Type' }
  ];

  const categories = [
    { value: 'trade', label: 'Trade' },
    { value: 'income', label: 'Income' },
    { value: 'gift_received', label: 'Gift Received' },
    { value: 'gift_sent', label: 'Gift Sent' },
    { value: 'payment', label: 'Payment' },
    { value: 'transfer', label: 'Transfer' },
    { value: 'staking', label: 'Staking Reward' },
    { value: 'airdrop', label: 'Airdrop' },
    { value: 'fee', label: 'Fee' },
    { value: 'other', label: 'Other' }
  ];

  const addRule = () => {
    setRules([...rules, { type: 'tx_type', value: '', category: 'other' }]);
  };

  const removeRule = (index) => {
    setRules(rules.filter((_, i) => i !== index));
  };

  const updateRule = (index, field, value) => {
    const newRules = [...rules];
    newRules[index][field] = value;
    setRules(newRules);
  };

  const handleApplyRules = async () => {
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await axios.post(
        `${API}/api/tax/batch-categorize`,
        { address, chain, rules },
        { headers: getAuthHeader() }
      );

      setResult(response.data);
      if (onCategorized) {
        onCategorized(response.data.categories);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to apply rules');
    } finally {
      setLoading(false);
    }
  };

  const handleAutoCategories = async () => {
    setLoading(true);
    setError('');
    setResult(null);

    try {
      const response = await axios.post(
        `${API}/api/tax/auto-categorize`,
        { address, chain },
        { headers: getAuthHeader() }
      );

      setResult(response.data);
      if (onCategorized) {
        onCategorized(response.data.categories);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to auto-categorize');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-2xl bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <Wand2 className="w-5 h-5 text-purple-400" />
            Batch Categorization
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Create rules to automatically categorize multiple transactions at once
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Auto-categorize button */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <h4 className="text-sm font-semibold text-white mb-2">Quick Action</h4>
            <Button
              onClick={handleAutoCategories}
              disabled={loading}
              variant="outline"
              className="w-full border-purple-600 text-purple-300 hover:bg-purple-900/30"
            >
              <Wand2 className="mr-2 h-4 w-4" />
              Auto-Categorize All Transactions
            </Button>
            <p className="text-xs text-gray-500 mt-2">
              Uses smart detection to categorize transactions based on patterns
            </p>
          </div>

          {/* Custom rules */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-semibold text-white">Custom Rules</h4>
              <Button
                onClick={addRule}
                size="sm"
                variant="outline"
                className="border-slate-600 text-gray-300"
              >
                + Add Rule
              </Button>
            </div>

            {rules.map((rule, index) => (
              <div key={index} className="bg-slate-900/30 rounded-lg p-3 border border-slate-700">
                <div className="grid grid-cols-3 gap-2">
                  <Select 
                    value={rule.type} 
                    onValueChange={(v) => updateRule(index, 'type', v)}
                  >
                    <SelectTrigger className="bg-slate-800 border-slate-600 text-white text-sm">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent className="bg-slate-800 border-slate-600">
                      {ruleTypes.map(t => (
                        <SelectItem key={t.value} value={t.value} className="text-white">
                          {t.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>

                  {rule.type === 'tx_type' ? (
                    <Select 
                      value={rule.value} 
                      onValueChange={(v) => updateRule(index, 'value', v)}
                    >
                      <SelectTrigger className="bg-slate-800 border-slate-600 text-white text-sm">
                        <SelectValue placeholder="Select..." />
                      </SelectTrigger>
                      <SelectContent className="bg-slate-800 border-slate-600">
                        <SelectItem value="received" className="text-white">Received</SelectItem>
                        <SelectItem value="sent" className="text-white">Sent</SelectItem>
                      </SelectContent>
                    </Select>
                  ) : (
                    <Input
                      value={rule.value}
                      onChange={(e) => updateRule(index, 'value', e.target.value)}
                      placeholder={rule.type === 'address' ? '0x...' : 'Value'}
                      className="bg-slate-800 border-slate-600 text-white text-sm"
                    />
                  )}

                  <div className="flex gap-2">
                    <Select 
                      value={rule.category} 
                      onValueChange={(v) => updateRule(index, 'category', v)}
                    >
                      <SelectTrigger className="bg-slate-800 border-slate-600 text-white text-sm flex-1">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-slate-800 border-slate-600">
                        {categories.map(c => (
                          <SelectItem key={c.value} value={c.value} className="text-white">
                            {c.label}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    
                    {rules.length > 1 && (
                      <Button
                        onClick={() => removeRule(index)}
                        size="sm"
                        variant="ghost"
                        className="text-red-400 hover:text-red-300 px-2"
                      >
                        ×
                      </Button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>

          {error && (
            <Alert className="bg-red-900/20 border-red-700 text-red-300">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {result && (
            <Alert className="bg-green-900/20 border-green-700 text-green-300">
              <Check className="h-4 w-4" />
              <AlertDescription>
                Successfully categorized {result.count} transactions!
              </AlertDescription>
            </Alert>
          )}
        </div>

        <div className="flex gap-3">
          <Button
            onClick={handleApplyRules}
            disabled={loading || rules.length === 0}
            className="flex-1 bg-purple-600 hover:bg-purple-700"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Applying...
              </>
            ) : (
              <>
                <Check className="mr-2 h-4 w-4" />
                Apply Rules
              </>
            )}
          </Button>
          <Button
            onClick={onClose}
            variant="outline"
            className="border-slate-600"
            disabled={loading}
          >
            Close
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
