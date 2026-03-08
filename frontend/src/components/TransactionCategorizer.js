import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { 
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue 
} from '@/components/ui/select';
import { 
  Loader2, 
  Tag, 
  Check, 
  X,
  AlertCircle,
  RefreshCw
} from 'lucide-react';

const TRANSACTION_CATEGORIES = [
  { value: 'trade', label: 'Trade', description: 'Exchange of one asset for another', color: 'bg-blue-600' },
  { value: 'income', label: 'Income', description: 'Mining, staking rewards, airdrops', color: 'bg-green-600' },
  { value: 'gift_received', label: 'Gift Received', description: 'Crypto received as a gift', color: 'bg-purple-600' },
  { value: 'gift_sent', label: 'Gift Sent', description: 'Crypto sent as a gift', color: 'bg-pink-600' },
  { value: 'payment', label: 'Payment', description: 'Payment for goods/services', color: 'bg-orange-600' },
  { value: 'transfer', label: 'Transfer', description: 'Movement between your own wallets', color: 'bg-gray-600' },
  { value: 'lost', label: 'Lost/Stolen', description: 'Lost access or theft', color: 'bg-red-600' },
  { value: 'fee', label: 'Fee', description: 'Network/transaction fees', color: 'bg-yellow-600' },
  { value: 'other', label: 'Other', description: 'Uncategorized transaction', color: 'bg-slate-600' }
];

export const TransactionCategorizer = ({ 
  isOpen, 
  onClose, 
  transactions, 
  onSaveCategories,
  getAuthHeader 
}) => {
  const [categories, setCategories] = useState({});
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  // Initialize categories from transactions
  React.useEffect(() => {
    if (transactions && transactions.length > 0) {
      const initialCategories = {};
      transactions.forEach(tx => {
        if (tx.hash) {
          initialCategories[tx.hash] = tx.category || autoDetectCategory(tx);
        }
      });
      setCategories(initialCategories);
    }
  }, [transactions]);

  const autoDetectCategory = (tx) => {
    // Auto-detect based on transaction type and patterns
    if (tx.type === 'sent') {
      return 'trade'; // Default sent to trade
    } else if (tx.type === 'received') {
      return 'trade'; // Default received to trade
    }
    return 'other';
  };

  const handleCategoryChange = (txHash, newCategory) => {
    setCategories(prev => ({
      ...prev,
      [txHash]: newCategory
    }));
  };

  const applyBulkCategory = (category) => {
    const newCategories = {};
    transactions.forEach(tx => {
      if (tx.hash) {
        newCategories[tx.hash] = category;
      }
    });
    setCategories(newCategories);
  };

  const handleSave = async () => {
    setSaving(true);
    setError('');
    setSuccess(false);

    try {
      // In a full implementation, this would save to the backend
      // For now, we'll pass the categories back to the parent
      await onSaveCategories(categories);
      setSuccess(true);
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      setError('Failed to save categories. Please try again.');
    } finally {
      setSaving(false);
    }
  };

  const getCategoryBadge = (category) => {
    const cat = TRANSACTION_CATEGORIES.find(c => c.value === category);
    if (!cat) return null;
    return (
      <Badge className={`${cat.color} text-white`}>
        {cat.label}
      </Badge>
    );
  };

  const formatAddress = (addr) => {
    if (!addr) return '';
    return `${addr.slice(0, 6)}...${addr.slice(-4)}`;
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-4xl bg-slate-800 border-slate-700 max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <Tag className="w-6 h-6 text-purple-400" />
            Categorize Transactions
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Categorize your transactions for accurate tax reporting. Categories affect how gains/losses are calculated.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-6">
          {/* Bulk Actions */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Quick Actions</h3>
            <div className="flex flex-wrap gap-2">
              {TRANSACTION_CATEGORIES.slice(0, 5).map(cat => (
                <Button
                  key={cat.value}
                  size="sm"
                  variant="outline"
                  className={`border-slate-600 text-gray-300 hover:${cat.color}`}
                  onClick={() => applyBulkCategory(cat.value)}
                >
                  Mark All as {cat.label}
                </Button>
              ))}
            </div>
          </div>

          {/* Transaction List */}
          <div className="space-y-3 max-h-[400px] overflow-y-auto">
            {transactions && transactions.length > 0 ? (
              transactions.slice(0, 50).map((tx, idx) => (
                <div 
                  key={tx.hash || idx} 
                  className="bg-slate-900/30 rounded-lg p-4 border border-slate-700"
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-2">
                        <Badge 
                          variant="outline" 
                          className={tx.type === 'sent' ? 'text-red-300 border-red-700' : 'text-green-300 border-green-700'}
                        >
                          {tx.type === 'sent' ? 'Sent' : 'Received'}
                        </Badge>
                        {tx.hash && (
                          <span className="text-gray-500 text-sm font-mono">
                            {formatAddress(tx.hash)}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-4 text-sm">
                        <span className="text-white font-semibold">
                          {tx.value} {tx.asset}
                        </span>
                        {tx.value_usd && (
                          <span className="text-gray-400">
                            (${tx.value_usd.toFixed(2)})
                          </span>
                        )}
                        <span className="text-gray-500">
                          {tx.type === 'sent' ? 'To: ' : 'From: '}
                          {formatAddress(tx.type === 'sent' ? tx.to : tx.from)}
                        </span>
                      </div>
                    </div>
                    
                    <div className="ml-4 min-w-[180px]">
                      <Select
                        value={categories[tx.hash] || 'other'}
                        onValueChange={(value) => handleCategoryChange(tx.hash, value)}
                      >
                        <SelectTrigger className="bg-slate-800 border-slate-600 text-white">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent className="bg-slate-800 border-slate-600">
                          {TRANSACTION_CATEGORIES.map(cat => (
                            <SelectItem 
                              key={cat.value} 
                              value={cat.value}
                              className="text-white hover:bg-slate-700"
                            >
                              <div className="flex items-center gap-2">
                                <div className={`w-3 h-3 rounded-full ${cat.color}`} />
                                {cat.label}
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  </div>
                </div>
              ))
            ) : (
              <div className="text-center text-gray-400 py-8">
                No transactions to categorize
              </div>
            )}
          </div>

          {transactions && transactions.length > 50 && (
            <Alert className="bg-blue-900/20 border-blue-700 text-blue-300">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>
                Showing first 50 transactions. Export to CSV to categorize all transactions.
              </AlertDescription>
            </Alert>
          )}

          {/* Category Legend */}
          <div className="bg-slate-900/50 rounded-lg p-4">
            <h3 className="text-sm font-semibold text-white mb-3">Category Guide</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-2 text-sm">
              {TRANSACTION_CATEGORIES.map(cat => (
                <div key={cat.value} className="flex items-center gap-2">
                  <div className={`w-3 h-3 rounded-full ${cat.color}`} />
                  <span className="text-white font-medium">{cat.label}:</span>
                  <span className="text-gray-400 text-xs">{cat.description}</span>
                </div>
              ))}
            </div>
          </div>

          {error && (
            <Alert className="bg-red-900/20 border-red-700 text-red-300">
              <X className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {success && (
            <Alert className="bg-green-900/20 border-green-700 text-green-300">
              <Check className="h-4 w-4" />
              <AlertDescription>Categories saved successfully!</AlertDescription>
            </Alert>
          )}

          {/* Action Buttons */}
          <div className="flex gap-3 pt-4">
            <Button
              onClick={handleSave}
              disabled={saving}
              className="flex-1 bg-purple-600 hover:bg-purple-700"
            >
              {saving ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Saving...
                </>
              ) : (
                <>
                  <Check className="mr-2 h-4 w-4" />
                  Save Categories
                </>
              )}
            </Button>
            <Button
              onClick={onClose}
              variant="outline"
              className="border-slate-600"
              disabled={saving}
            >
              Cancel
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
