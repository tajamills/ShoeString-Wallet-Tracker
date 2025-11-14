import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, Download, FileSpreadsheet, AlertCircle } from 'lucide-react';
import axios from 'axios';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const ExportModal = ({ isOpen, onClose, analysis, selectedChain, getAuthHeader, getChainSymbol }) => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [exportProgress, setExportProgress] = useState(null);
  const [exportMode, setExportMode] = useState('current'); // 'current' or 'all'

  const exportCurrentPage = () => {
    // Export only what's currently displayed (quick export)
    const headers = ['Type', 'Hash', 'Asset', 'Amount', 'Address', 'Label/Exchange', 'Block Number'];
    const rows = analysis.recentTransactions.map(tx => {
      const address = tx.type === 'sent' ? (tx.to || 'N/A') : (tx.from || 'N/A');
      const label = tx.type === 'sent' ? (tx.to_label || '') : (tx.from_label || '');
      return [
        tx.type,
        tx.hash || 'N/A',
        tx.asset,
        tx.value,
        address,
        label,
        tx.blockNum || 'N/A'
      ];
    });

    const summaryRows = [
      ['Crypto Bag Tracker - Transaction Export'],
      [''],
      ['Wallet Address', analysis.address],
      ['Chain', (analysis.chain || selectedChain).toUpperCase()],
      ['Export Date', new Date().toISOString()],
      ['Export Type', 'Recent Transactions Only'],
      [''],
      ['Summary'],
      ['Total Received', `${analysis.totalEthReceived} ${getChainSymbol(analysis.chain || selectedChain)}`],
      ['Total Sent', `${analysis.totalEthSent} ${getChainSymbol(analysis.chain || selectedChain)}`],
      ['Gas Fees', `${analysis.totalGasFees} ${getChainSymbol(analysis.chain || selectedChain)}`],
      ['Net Balance', `${analysis.netEth} ${getChainSymbol(analysis.chain || selectedChain)}`],
      [''],
      ['Transactions']
    ];

    const csvContent = [
      ...summaryRows.map(row => row.join(',')),
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    downloadCSV(csvContent, `recent-transactions-${analysis.address.substring(0, 8)}`);
    onClose();
  };

  const exportAllTransactions = async () => {
    setLoading(true);
    setError('');
    setExportProgress({ current: 0, total: 0 });

    try {
      const PAGE_SIZE = 1000;
      let currentPage = 1;
      let allTransactions = [];
      let hasMore = true;

      // Fetch first page to get total count
      const firstPageResponse = await axios.post(
        `${API}/wallet/export-paginated?page=1&page_size=${PAGE_SIZE}`,
        {
          address: analysis.address,
          chain: analysis.chain || selectedChain
        },
        { headers: getAuthHeader() }
      );

      const totalPages = firstPageResponse.data.total_pages;
      const totalTransactions = firstPageResponse.data.total_transactions;

      setExportProgress({ current: 1, total: totalPages, transactions: firstPageResponse.data.transactions.length });
      allTransactions = [...firstPageResponse.data.transactions];

      // Fetch remaining pages
      for (let page = 2; page <= totalPages; page++) {
        const response = await axios.post(
          `${API}/wallet/export-paginated?page=${page}&page_size=${PAGE_SIZE}`,
          {
            address: analysis.address,
            chain: analysis.chain || selectedChain
          },
          { headers: getAuthHeader() }
        );

        allTransactions = [...allTransactions, ...response.data.transactions];
        setExportProgress({ 
          current: page, 
          total: totalPages, 
          transactions: allTransactions.length 
        });

        // Add small delay to avoid rate limiting
        await new Promise(resolve => setTimeout(resolve, 500));
      }

      // Generate CSV with all transactions
      const headers = ['Type', 'Hash', 'Asset', 'Amount', 'Address', 'Label/Exchange', 'Block Number'];
      const rows = allTransactions.map(tx => {
        const address = tx.type === 'sent' ? (tx.to || 'N/A') : (tx.from || 'N/A');
        const label = tx.type === 'sent' ? (tx.to_label || '') : (tx.from_label || '');
        return [
          tx.type,
          tx.hash || 'N/A',
          tx.asset,
          tx.value,
          address,
          label,
          tx.blockNum || 'N/A'
        ];
      });

      const summaryRows = [
        ['Crypto Bag Tracker - Full Transaction Export'],
        [''],
        ['Wallet Address', analysis.address],
        ['Chain', (analysis.chain || selectedChain).toUpperCase()],
        ['Export Date', new Date().toISOString()],
        ['Export Type', 'Complete History'],
        ['Total Transactions', totalTransactions],
        [''],
        ['Summary'],
        ['Total Received', `${analysis.totalEthReceived} ${getChainSymbol(analysis.chain || selectedChain)}`],
        ['Total Sent', `${analysis.totalEthSent} ${getChainSymbol(analysis.chain || selectedChain)}`],
        ['Gas Fees', `${analysis.totalGasFees} ${getChainSymbol(analysis.chain || selectedChain)}`],
        ['Net Balance', `${analysis.netEth} ${getChainSymbol(analysis.chain || selectedChain)}`],
        [''],
        ['Transactions']
      ];

      const csvContent = [
        ...summaryRows.map(row => row.join(',')),
        headers.join(','),
        ...rows.map(row => row.join(','))
      ].join('\n');

      downloadCSV(csvContent, `full-export-${analysis.address.substring(0, 8)}`);
      onClose();

    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to export all transactions');
    } finally {
      setLoading(false);
      setExportProgress(null);
    }
  };

  const downloadCSV = (csvContent, filename) => {
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    const url = URL.createObjectURL(blob);
    link.setAttribute('href', url);
    link.setAttribute('download', `${filename}-${Date.now()}.csv`);
    link.style.visibility = 'hidden';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-slate-800 border-slate-700">
        <DialogHeader>
          <DialogTitle className="text-white flex items-center gap-2">
            <FileSpreadsheet className="w-5 h-5 text-green-400" />
            Export Transactions
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            Choose your export option
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="space-y-4">
            <div className="text-center">
              <Loader2 className="w-12 h-12 text-purple-400 animate-spin mx-auto mb-4" />
              <p className="text-white font-semibold">Exporting All Transactions...</p>
              {exportProgress && (
                <div className="mt-4 space-y-2">
                  <p className="text-gray-400 text-sm">
                    Page {exportProgress.current} of {exportProgress.total}
                  </p>
                  <p className="text-gray-400 text-sm">
                    {exportProgress.transactions} transactions collected
                  </p>
                  <div className="w-full bg-slate-700 rounded-full h-2">
                    <div 
                      className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${(exportProgress.current / exportProgress.total) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <Alert className="bg-blue-900/20 border-blue-700 text-blue-300">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription className="text-sm">
                <strong>Recent Transactions:</strong> Quick export (~{analysis.recentTransactions?.length || 20} transactions)<br/>
                <strong>All Transactions:</strong> Complete history (may take 10-60 seconds for large wallets)
              </AlertDescription>
            </Alert>

            <div className="grid grid-cols-1 gap-3">
              <Button
                onClick={exportCurrentPage}
                className="w-full bg-green-600 hover:bg-green-700 h-12"
              >
                <Download className="mr-2 h-4 w-4" />
                Export Recent ({analysis.recentTransactions?.length || 20} txns)
              </Button>

              <Button
                onClick={exportAllTransactions}
                className="w-full bg-purple-600 hover:bg-purple-700 h-12"
              >
                <FileSpreadsheet className="mr-2 h-4 w-4" />
                Export All Transactions
              </Button>
            </div>

            {error && (
              <Alert className="bg-red-900/20 border-red-700 text-red-300">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button
              onClick={onClose}
              variant="outline"
              className="w-full border-slate-600"
            >
              Cancel
            </Button>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
