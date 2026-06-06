import React, { useState, useEffect } from 'react';
import { AlertTriangle, CheckCircle, XCircle, RefreshCw, FileText, ChevronDown, ChevronUp, Target, TrendingUp, TrendingDown, BarChart2 } from 'lucide-react';

/**
 * ValidationStatusPanel - P2 Frontend UI for Tax Validation Status
 * 
 * Displays:
 * - Overall validation status (valid/invalid/needs_review)
 * - Can export indicator
 * - Issue breakdown by severity
 * - Classification effectiveness metrics
 * - Quick actions for common fixes
 */
const ValidationStatusPanel = ({ apiUrl, authHeader, onRefresh, onOpenClassifier, onOpenChainOfCustody, onOpenReviewQueue }) => {
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [expanded, setExpanded] = useState(false);
  const [preExportCheck, setPreExportCheck] = useState(null);
  const [unknownCount, setUnknownCount] = useState(0);
  const [effectiveness, setEffectiveness] = useState(null);
  const [showEffectiveness, setShowEffectiveness] = useState(false);

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
      
      // Fetch unknown transaction count for classification
      try {
        const classifyRes = await fetch(`${apiUrl}/api/custody/classify/metrics?days=30`, {
          headers: authHeader
        });
        if (classifyRes.ok) {
          const classifyData = await classifyRes.json();
          setUnknownCount(classifyData.metrics?.current_unknown || 0);
        }
      } catch (classifyErr) {
        console.log('Could not fetch classification metrics:', classifyErr);
      }
      
      // Fetch effectiveness metrics
      try {
        const effectivenessRes = await fetch(`${apiUrl}/api/custody/classify/effectiveness?days=30`, {
          headers: authHeader
        });
        if (effectivenessRes.ok) {
          const effectivenessData = await effectivenessRes.json();
          setEffectiveness(effectivenessData.effectiveness);
        }
      } catch (effectivenessErr) {
        console.log('Could not fetch effectiveness metrics:', effectivenessErr);
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
        <div className="flex items-center gap-2 text-[#8A8A93]">
          <RefreshCw className="w-4 h-4 animate-spin" />
          <span>Checking validation status...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-900/20 rounded-lg p-4 border border-red-700" data-testid="validation-status-error">
        <div className="flex items-center gap-2 text-[#FF3B30]">
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
    if (canExport) return <CheckCircle className="w-5 h-5 text-[#00C805]" />;
    if (validationStatus === 'needs_review') return <AlertTriangle className="w-5 h-5 text-[#FFB800]" />;
    return <XCircle className="w-5 h-5 text-[#FF3B30]" />;
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
            <p className={`text-sm ${canExport ? 'text-[#00C805]' : 'text-[#FF3B30]'}`} data-testid="validation-status-text">
              {getStatusText()}
            </p>
          </div>
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={handleRefresh}
            className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            title="Refresh status"
            data-testid="validation-refresh-btn"
          >
            <RefreshCw className="w-4 h-4 text-white" />
          </button>
          
          <button
            onClick={() => setExpanded(!expanded)}
            className="p-2 bg-gray-700 hover:bg-gray-600 rounded-lg transition-colors"
            data-testid="validation-expand-btn"
          >
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-[#8A8A93]" />
            ) : (
              <ChevronDown className="w-4 h-4 text-[#8A8A93]" />
            )}
          </button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-3 gap-4 mt-4">
        <div className="bg-gray-900/50 rounded-lg p-3 text-center">
          <div className={`text-2xl font-bold ${blockingIssues > 0 ? 'text-[#FF3B30]' : 'text-[#00C805]'}`}>
            {blockingIssues}
          </div>
          <div className="text-xs text-[#8A8A93]">Blocking Issues</div>
        </div>
        
        <div className="bg-gray-900/50 rounded-lg p-3 text-center">
          <div className={`text-2xl font-bold ${unresolvedReviews > 0 ? 'text-[#FFB800]' : 'text-[#00C805]'}`}>
            {unresolvedReviews}
          </div>
          <div className="text-xs text-[#8A8A93]">Unresolved Reviews</div>
        </div>
        
        <div className="bg-gray-900/50 rounded-lg p-3 text-center">
          <div className={`text-2xl font-bold ${canExport ? 'text-[#00C805]' : 'text-[#FF3B30]'}`}>
            {canExport ? 'YES' : 'NO'}
          </div>
          <div className="text-xs text-[#8A8A93]">Can Export</div>
        </div>
      </div>

      {/* Expanded Details */}
      {expanded && preExportCheck && (
        <div className="mt-4 space-y-4" data-testid="validation-details">
          {/* Blocking Issues */}
          {preExportCheck.blocking_issues && preExportCheck.blocking_issues.length > 0 && (
            <div>
              <h4 className="text-sm font-medium text-[#FF3B30] mb-2">Blocking Issues</h4>
              <div className="space-y-2">
                {preExportCheck.blocking_issues.slice(0, 5).map((issue, idx) => (
                  <div key={idx} className="bg-red-900/20 rounded-lg p-3 text-sm">
                    <div className="flex items-center gap-2">
                      <span className={`px-2 py-0.5 rounded text-xs font-medium ${
                        issue.severity === 'critical' ? 'bg-[#FF3B30]' : 'bg-orange-600'
                      }`}>
                        {issue.severity?.toUpperCase()}
                      </span>
                      <span className="text-white">{issue.asset}</span>
                    </div>
                    <p className="text-[#8A8A93] mt-1">{issue.description}</p>
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
              <h4 className="text-sm font-medium text-[#FFB800] mb-2">Failed Checks</h4>
              <div className="space-y-2">
                {preExportCheck.failed_invariants.map((check, idx) => (
                  <div key={idx} className="bg-yellow-900/20 rounded-lg p-3 text-sm">
                    <div className="font-medium text-white">{check.check_name}</div>
                    {check.affected_assets && check.affected_assets.length > 0 && (
                      <div className="text-[#8A8A93] text-xs mt-1">
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

      {/* Classification Effectiveness Metrics */}
      {effectiveness && (effectiveness.auto_classified_count > 0 || effectiveness.user_confirmed_count > 0) && (
        <div className="mt-4">
          <button
            onClick={() => setShowEffectiveness(!showEffectiveness)}
            className="flex items-center gap-2 text-sm text-[#8A8A93] hover:text-gray-200 transition-colors"
            data-testid="toggle-effectiveness-btn"
          >
            <BarChart2 className="w-4 h-4" />
            <span>Classification Effectiveness</span>
            {showEffectiveness ? (
              <ChevronUp className="w-4 h-4" />
            ) : (
              <ChevronDown className="w-4 h-4" />
            )}
          </button>
          
          {showEffectiveness && (
            <div className="mt-3 space-y-3" data-testid="effectiveness-panel">
              {/* Summary Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                <div className="bg-gray-900/50 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-[#00C805]">
                    {effectiveness.unknown_reduction}
                  </div>
                  <div className="text-xs text-[#8A8A93]">Unknowns Reduced</div>
                </div>
                <div className="bg-gray-900/50 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-blue-400">
                    {effectiveness.auto_classified_count}
                  </div>
                  <div className="text-xs text-[#8A8A93]">Auto-Classified</div>
                </div>
                <div className="bg-gray-900/50 rounded-lg p-2 text-center">
                  <div className="text-lg font-bold text-[#00C805]">
                    {effectiveness.user_confirmed_count}
                  </div>
                  <div className="text-xs text-[#8A8A93]">User Confirmed</div>
                </div>
                <div className="bg-gray-900/50 rounded-lg p-2 text-center">
                  <div className={`text-lg font-bold ${effectiveness.overall_precision >= 0.9 ? 'text-[#00C805]' : effectiveness.overall_precision >= 0.7 ? 'text-[#FFB800]' : 'text-[#FF3B30]'}`}>
                    {Math.round(effectiveness.overall_precision * 100)}%
                  </div>
                  <div className="text-xs text-[#8A8A93]">Precision</div>
                </div>
              </div>
              
              {/* Export Readiness Improvement */}
              {effectiveness.export_readiness_improved && (
                <div className="bg-green-900/20 border border-green-700 rounded-lg p-2 text-center">
                  <div className="flex items-center justify-center gap-2 text-[#00C805]">
                    <TrendingUp className="w-4 h-4" />
                    <span className="text-sm font-medium">Export Readiness Improved!</span>
                  </div>
                  <div className="text-xs text-[#8A8A93] mt-1">
                    {effectiveness.validation_status_before} → {effectiveness.validation_status_after}
                  </div>
                </div>
              )}
              
              {/* Confidence Bucket Breakdown */}
              {effectiveness.confidence_buckets && effectiveness.confidence_buckets.length > 0 && (
                <div>
                  <h5 className="text-xs font-medium text-[#8A8A93] mb-2">Precision by Confidence</h5>
                  <div className="space-y-1">
                    {effectiveness.confidence_buckets
                      .filter(b => b.total_classified > 0)
                      .map((bucket, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs">
                          <span className="text-[#8A8A93] capitalize">{bucket.bucket_name.replace('_', ' ')}</span>
                          <span className="text-white">
                            {bucket.user_confirmed}/{bucket.user_confirmed + bucket.user_rejected} 
                            <span className={`ml-2 ${bucket.precision >= 0.9 ? 'text-[#00C805]' : bucket.precision >= 0.7 ? 'text-[#FFB800]' : 'text-[#FF3B30]'}`}>
                              ({Math.round(bucket.precision * 100)}%)
                            </span>
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
              
              {/* Classification Type Breakdown */}
              {effectiveness.classification_types && effectiveness.classification_types.length > 0 && (
                <div>
                  <h5 className="text-xs font-medium text-[#8A8A93] mb-2">By Classification Type</h5>
                  <div className="grid grid-cols-2 gap-1">
                    {effectiveness.classification_types
                      .filter(t => t.total_classified > 0)
                      .slice(0, 6)
                      .map((type, idx) => (
                        <div key={idx} className="flex items-center justify-between text-xs bg-gray-900/30 rounded px-2 py-1">
                          <span className="text-[#8A8A93] capitalize">{type.classification_type.replace('_', ' ')}</span>
                          <span className="text-white">{type.total_classified}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
              
              {/* Rollback Warning */}
              {effectiveness.rollback_count > 0 && (
                <div className="flex items-center gap-2 text-xs text-[#FFB800]">
                  <AlertTriangle className="w-3 h-3" />
                  <span>{effectiveness.rollback_count} classification(s) rolled back</span>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Quick Actions */}
      <div className="mt-4 space-y-2">
        {/* Unknown Transaction Classifier - Show if there are unknowns */}
        {unknownCount > 0 && (
          <div className="bg-[#0C0C0E]/20 border border-[#1F1F22] rounded-lg p-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Target className="w-4 h-4 text-[#00C805]" />
                <span className="text-[#00C805] text-sm">
                  {unknownCount} unknown transactions need classification
                </span>
              </div>
              {onOpenClassifier && (
                <button
                  onClick={onOpenClassifier}
                  className="bg-white text-black hover:bg-gray-200 text-white text-sm py-1 px-3 rounded transition-colors"
                  data-testid="open-classifier-btn"
                >
                  Classify
                </button>
              )}
            </div>
          </div>
        )}
        
        {!canExport && (
          <div className="flex gap-2">
            <button
              onClick={onOpenReviewQueue}
              className="flex-1 bg-white text-black hover:bg-gray-200 text-white text-sm py-2 px-4 rounded-lg text-center transition-colors"
              data-testid="review-queue-link"
            >
              Review Queue
            </button>
            <button
              onClick={onOpenChainOfCustody}
              className="flex-1 bg-gray-700 hover:bg-gray-600 text-white text-sm py-2 px-4 rounded-lg text-center transition-colors"
              data-testid="chain-custody-link"
            >
              Chain of Custody
            </button>
          </div>
        )}
      </div>
    </div>
  );
};

export default ValidationStatusPanel;
