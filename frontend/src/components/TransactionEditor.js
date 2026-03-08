/**
 * TransactionEditor - Edit cost basis and acquisition dates for transfers
 * 
 * When crypto is transferred from a cold wallet to an exchange, the exchange
 * only sees the receive date, not the original purchase date. This component
 * allows users to correct the acquisition date for accurate holding period
 * calculation (short-term vs long-term gains).
 */
import React, { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card, CardContent } from '@/components/ui/card';
import { 
  Loader2, 
  Edit2, 
  Save, 
  AlertTriangle,
  ArrowRight,
  Calendar,
  DollarSign,
  Info
} from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const TransactionEditor = ({ isOpen, onClose, getAuthHeader, onUpdate }) => {
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [potentialTransfers, setPotentialTransfers] = useState([]);
  const [editingTx, setEditingTx] = useState(null);
  const [formData, setFormData] = useState({
    original_purchase_date: '',
    original_cost_basis: '',
    notes: ''
  });
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    if (isOpen) {
      fetchPotentialTransfers();
    }
  }, [isOpen]);

  const fetchPotentialTransfers = async () => {
    setLoading(true);
    try {
      const response = await axios.get(`${API}/exchanges/transactions/transfers`, {
        headers: getAuthHeader()
      });
      setPotentialTransfers(response.data.potential_transfers || []);
    } catch (err) {
      setError('Failed to load potential transfers');
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (transfer) => {
    setEditingTx(transfer.receive_tx);
    setFormData({
      original_purchase_date: '',
      original_cost_basis: '',
      notes: `Transfer from external wallet - ${transfer.asset}`
    });
    setMessage('');
    setError('');
  };

  const handleSave = async () => {
    if (!editingTx) return;
    
    setSaving(true);
    setError('');
    
    try {
      await axios.put(
        `${API}/exchanges/transactions/${editingTx.tx_id}/cost-basis`,
        {
          tx_id: editingTx.tx_id,
          original_purchase_date: formData.original_purchase_date || null,
          original_cost_basis: formData.original_cost_basis ? parseFloat(formData.original_cost_basis) : null,
          is_transfer: true,
          notes: formData.notes
        },
        { headers: getAuthHeader() }
      );
      
      setMessage('Transaction updated successfully! Tax calculations will now use the original purchase date.');
      setEditingTx(null);
      fetchPotentialTransfers();
      
      if (onUpdate) {
        onUpdate();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to update transaction');
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'N/A';
    return new Date(dateStr).toLocaleDateString();
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="bg-slate-900 border-slate-700 max-w-2xl max-h-[80vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <Edit2 className="w-5 h-5 text-purple-400" />
            Adjust Cost Basis for Transfers
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            When you transfer crypto from a cold wallet, update the original purchase date for accurate tax calculations.
          </DialogDescription>
        </DialogHeader>

        {/* Info Alert */}
        <Alert className="bg-blue-900/30 border-blue-700 text-blue-300">
          <Info className="w-4 h-4" />
          <AlertDescription className="text-sm">
            <strong>Why this matters:</strong> If you held crypto for over 1 year before selling, 
            it qualifies for long-term capital gains rates. Transfers between your own wallets 
            don't reset the holding period.
          </AlertDescription>
        </Alert>

        {/* Messages */}
        {message && (
          <Alert className="bg-green-900/30 border-green-700 text-green-300">
            <AlertDescription>{message}</AlertDescription>
          </Alert>
        )}
        {error && (
          <Alert className="bg-red-900/30 border-red-700 text-red-300">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {/* Loading State */}
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-8 h-8 animate-spin text-purple-400" />
          </div>
        ) : (
          <>
            {/* Edit Form */}
            {editingTx && (
              <Card className="bg-slate-800/50 border-purple-600">
                <CardContent className="pt-4 space-y-4">
                  <div className="flex items-center justify-between">
                    <h3 className="text-white font-medium">
                      Editing: {editingTx.amount} {editingTx.asset}
                    </h3>
                    <Badge className="bg-purple-600">
                      Received: {formatDate(editingTx.timestamp)}
                    </Badge>
                  </div>

                  <div className="grid gap-4">
                    <div>
                      <label className="text-sm text-gray-400 mb-1 block">
                        <Calendar className="w-3 h-3 inline mr-1" />
                        Original Purchase Date
                      </label>
                      <Input
                        type="date"
                        value={formData.original_purchase_date}
                        onChange={(e) => setFormData({...formData, original_purchase_date: e.target.value})}
                        className="bg-slate-700 border-slate-600 text-white"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        When did you originally buy this {editingTx.asset}?
                      </p>
                    </div>

                    <div>
                      <label className="text-sm text-gray-400 mb-1 block">
                        <DollarSign className="w-3 h-3 inline mr-1" />
                        Original Cost Basis (USD) - Optional
                      </label>
                      <Input
                        type="number"
                        step="0.01"
                        placeholder="e.g., 5000.00"
                        value={formData.original_cost_basis}
                        onChange={(e) => setFormData({...formData, original_cost_basis: e.target.value})}
                        className="bg-slate-700 border-slate-600 text-white"
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        Total USD you paid for this {editingTx.asset}
                      </p>
                    </div>

                    <div>
                      <label className="text-sm text-gray-400 mb-1 block">Notes (Optional)</label>
                      <Input
                        type="text"
                        value={formData.notes}
                        onChange={(e) => setFormData({...formData, notes: e.target.value})}
                        className="bg-slate-700 border-slate-600 text-white"
                      />
                    </div>
                  </div>

                  <div className="flex gap-2 justify-end">
                    <Button
                      variant="outline"
                      onClick={() => setEditingTx(null)}
                      className="border-slate-600 text-gray-300"
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleSave}
                      disabled={saving || !formData.original_purchase_date}
                      className="bg-purple-600 hover:bg-purple-700"
                    >
                      {saving ? (
                        <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      ) : (
                        <Save className="w-4 h-4 mr-2" />
                      )}
                      Save Changes
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Potential Transfers List */}
            {!editingTx && (
              <div className="space-y-3">
                <h3 className="text-white text-sm font-medium">
                  Potential Transfers ({potentialTransfers.length} found)
                </h3>
                
                {potentialTransfers.length === 0 ? (
                  <p className="text-gray-400 text-sm py-4 text-center">
                    No potential transfers detected. Transfers are identified when crypto is 
                    received and sold within 30 days.
                  </p>
                ) : (
                  potentialTransfers.slice(0, 10).map((transfer, idx) => (
                    <Card key={idx} className="bg-slate-800/50 border-slate-700">
                      <CardContent className="pt-4">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <Badge className="bg-blue-600">{transfer.asset}</Badge>
                            <div className="text-sm">
                              <span className="text-green-400">
                                Received {transfer.receive_tx.amount?.toFixed(4)}
                              </span>
                              <ArrowRight className="w-3 h-3 inline mx-2 text-gray-500" />
                              <span className="text-red-400">
                                Sold {transfer.days_between} days later
                              </span>
                            </div>
                          </div>
                          <Button
                            size="sm"
                            onClick={() => handleEdit(transfer)}
                            className="bg-purple-600 hover:bg-purple-700"
                          >
                            <Edit2 className="w-3 h-3 mr-1" />
                            Edit
                          </Button>
                        </div>
                        <p className="text-xs text-gray-500 mt-2">
                          Received: {formatDate(transfer.receive_tx.timestamp)}
                        </p>
                      </CardContent>
                    </Card>
                  ))
                )}

                {potentialTransfers.length > 10 && (
                  <p className="text-xs text-gray-500 text-center">
                    Showing first 10 of {potentialTransfers.length} potential transfers
                  </p>
                )}
              </div>
            )}
          </>
        )}
      </DialogContent>
    </Dialog>
  );
};
