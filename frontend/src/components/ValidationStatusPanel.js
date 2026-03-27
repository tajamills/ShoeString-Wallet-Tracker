import React, { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, XCircle, RefreshCw, FileText, ChevronDown, ChevronUp } from 'lucide-react';

/**
 * ValidationStatusPanel - P2 Frontend UI for Tax Validation Status
 * 
 * Displays:
 * - Overall validation status (valid/invalid/needs_review)
 * - Can export indicator
 * - Issue breakdown by severity
 * - Quick actions for common fixes
 */
const ValidationStatusPanel = ({ apiUrl, authHeader, onRefresh }) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [preExportCheck, setPreExportCheck] = useState(null);

  const fetchStatus = async () => {
    setLoading(true);
    setError(null);
    
    try {
      // Fetch validation status
      const statusRes = await fetch(`${apiUrl}/api/custody/validation-status`, {
        headers: authHeader
      });
      
      if (!statusRes.ok) throw new Error('Failed to fetch validation status');
      const statusData = await statusRes.json();
      setStatus(statusData.validation_status);
      
      // Fetch pre-export check for detailed issues
      const preExportRes = await fetch(`${apiUrl}/api/custody/beta/pre-export-check?tax_year=2024`, {
        headers: authHeader
      });
      
      if (preExportRes.ok) {
        const preExportData = await preExportRes.json();
        setPreExportCheck(preExportData);
      }
      
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
  }, [apiUrl]);

  const handleRefresh = () => {
    fetchStatus();
    if (onRefresh) onRefresh();
  };

  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg p-4 border border-gray-700" data-testid="validation-status-loading">
        <div className="flex items-center gap-2 text-gray-400">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span>Checking validation status...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 rounded-lg p-4 border border-red-700" data-testid="validation-status-error">
        <div className="flex items-center gap-2 text-red-400">
          <XCircle className="w-4 h-4" />
          <span>Error: {error}</span>
        </div>
      </div>
    );
  }

  const canExport = preExportCheck?.can_export ?? status?.can_export ?? false;
  const validationStatus = preExportCheck?.validation_status ?? status?.is_valid ? 'valid' : 'invalid';
  const blockingIssues = preExportCheck?.blocking_issues_count ?? 0;
  const unresolvedReviews = preExportCheck?.unresolved_review_count ?? 0;

  const getStatusColor = () => {
    if (canExport) return 'bg-green-900/20 border-green-700';
    if (validationStatus === 'needs_review') return 'bg-yellow-900/20 border-yellow-700';
    return 'bg-red-900/20 border-red-700';
  };

  const getStatusIcon = () => {
    if (canExport) return <CheckCircle className="w-5 h-5 text-green-400" />;
    if (validationStatus === 'needs_review') return <AlertTriangle className="w-5 h-5 text-yellow-400" />;
    return <XCircle className="w-5 h-5 text-red-400" />;
  };

  const getStatusText = () => {
    if (canExport) return 'Ready for Export';
    if (validationStatus === 'needs_review') return 'Needs Review';
    return 'Export Blocked';
  };

  return (
    <div className={`rounded-lg p-4 border ${getStatusColor()}`} data-testid="validation-status-panel">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          {getStatusIcon()}
          <div>
            <h3 className="font-semibold text-white" data-testid="validation-status-title">
              Tax Validation Status
            </h3>
            <p className={`text-sm ${canExport ? 'text-green-400' : 'text-red-400'}`} data-testid="validation-status-text">
              {getStatusText()}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
            title="Refresh status"
            data-testid="validation-refresh-btn"
          >
            <RefreshCw className="w-4 h-4 text-gray-400" />
          </button>
          
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-2 hover:bg-gray-700 rounded-lg transition-colors"
            data-testid="validation-expand-btn"
          >
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-gray-400" />
            ) : (
              <ChevronDown className="w-4 h-4 text-gray-400" />
            )}
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 mt-4">
        <div className="bg-gray-900/50 rounded-lg p-3 text-center">
          <div className={`text-2xl font-bold ${blockingIssues > 0 ? 'text-red-400' : 'text-green-400'}`}>
            {blockingIssues}
          </div>
          <div className="text-xs text-gray-400">Blocking Issues</div>
        </div>
        
        <div className="bg-gray-900/50 rounded-lg p-3 text-center">
          <div className={`text-2xl font-bold ${unresolvedReviews > 0 ? 'text-yellow-400' : 'text-green-400'}`}>
            {unresolvedReviews}
          </div>
          <div className="text-xs text-gray-400">Unresolved Reviews</div>
        </div>
        
        <div className="bg-gray-900/50 rounded-lg p-3 text-center">
          <div className={`text-2xl font-bold ${canExport ? 'text-green-400' : 'text-red-400'}`}>
            {canExport ? 'YES' : 'NO'}
          </div>
          <div className="text-xs text-gray-400">Can Export</div>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && preExportCheck && (
        <div className="mt-4 space-y-4" data-testid="validation-details">
          {/* Blocking Issues */}
          {preExportCheck.blocking_issues && preExportCheck.blocking_issues.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-red-400 mb-2">Blocking Issues</h4>
              <div className="space-y-2">
                {preExportCheck.blocking_issues.slice(0, 5).map((issue, idx) => (
                  <div key={idx} className="bg-red-900/20 rounded-lg p-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        issue.severity === 'critical' ? 'bg-red-600' : 'bg-orange-600'
                      }`}>
                        {issue.severity?.toUpperCase()}
                      </span>
                      <span className="text-gray-300">{issue.asset}</span>
                    </div>
                    <p className="text-gray-400 mt-1">{issue.description}</p>
                    {issue.recommendation && (
                      <p className="text-blue-400 text-xs mt-1">Fix: {issue.recommendation}</p>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Failed Invariants */}
          {preExportCheck.failed_invariants && preExportCheck.failed_invariants.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-yellow-400 mb-2">Failed Checks</h4>
              <div className="space-y-2">
                {preExportCheck.failed_invariants.map((check, idx) => (
                  <div key={idx} className="bg-yellow-900/20 rounded-lg p-3 text-sm">
                    <div className="font-medium text-gray-300">{check.check_name}</div>
                    {check.affected_assets && check.affected_assets.length > 0 && (
                      <div className="text-gray-400 text-xs mt-1">
                        Affected: {check.affected_assets.join(', ')}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Recommendation */}
          {preExportCheck.recommendation && (
            <div className="bg-blue-900/20 rounded-lg p-3 border border-blue-700">
              <div className="flex items-center gap-2">
                <FileText className="w-4 h-4 text-blue-400" />
                <span className="text-blue-300 text-sm">{preExportCheck.recommendation}</span>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Quick Actions */}
      {!canExport && (
        <div className="mt-4 flex gap-2">
          <a
            href="#review-queue"
            className="flex-1 bg-blue-600 hover:bg-blue-700 text-white text-sm py-2 px-4 rounded-lg text-center transition-colors"
            data-testid="review-queue-link"
          >
            Review Queue
          </a>
          <a
            href="#chain-of-custody"
            className="flex-1 bg-gray-700 hover:bg-gray-600 text-white text-sm py-2 px-4 rounded-lg text-center transition-colors"
            data-testid="chain-custody-link"
          >
            Chain of Custody
          </a>
        </div>
      )}
    </div>
  );
};

export default ValidationStatusPanel;
