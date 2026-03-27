import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { 
  Loader2, 
  RefreshCw, 
  Check, 
  X, 
  AlertTriangle, 
  Zap, 
  Target, 
  TrendingUp,
  ChevronDown,
  ChevronUp,
  Undo2,
  Filter,
  Play
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

/**
 * UnknownTransactionClassifier - UI for Unknown Transaction Reduction System
 * 
 * Features:
 * - Pattern Detection display with actionable groups
 * - Auto-classification with confidence scoring
 * - Bulk classification by pattern or destination
 * - Feedback loop for user decisions
 * - Metrics dashboard showing reduction rates
 */
export const UnknownTransactionClassifier = ({ onClassificationComplete }) => {
  const { getAuthHeader } = useAuth();
  
  // State
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [metrics, setMetrics] = useState(null);
  const [patterns, setPatterns] = useState([]);
  const [batches, setBatches] = useState([]);
  const [error, setError] = useState(null);
  
  // UI state
  const [expandedPattern, setExpandedPattern] = useState(null);
  const [activeTab, setActiveTab] = useState('suggestions'); // suggestions | patterns | metrics | batches
  const [selectedConfidence, setSelectedConfidence] = useState('all'); // all | auto_apply | suggest | unresolved

  // Fetch analysis on mount
  useEffect(() => {
    fetchAnalysis();
    fetchMetrics();
    fetchBatches();
  }, []);

  const fetchAnalysis = async () => {
    setAnalyzing(true);
    setError(null);
    
    try {
      const response = await axios.get(`${API}/custody/classify/analyze`, {
        headers: getAuthHeader()
      });
      
      if (response.data.success) {
        setAnalysis(response.data.analysis);
        setPatterns(response.data.analysis?.patterns || []);
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to analyze transactions');
    } finally {
      setAnalyzing(false);
    }
  };

  const fetchMetrics = async () => {
    try {
      const response = await axios.get(`${API}/custody/classify/metrics?days=30`, {
        headers: getAuthHeader()
      });
      
      if (response.data.success) {
        setMetrics(response.data.metrics);
      }
    } catch (err) {
      console.error('Failed to fetch metrics:', err);
    }
  };

  const fetchBatches = async () => {
    try {
      const response = await axios.get(`${API}/custody/classify/batches`, {
        headers: getAuthHeader()
      });
      
      if (response.data.success) {
        setBatches(response.data.batches || []);
      }
    } catch (err) {
      console.error('Failed to fetch batches:', err);
    }
  };

  const handleAutoClassify = async (dryRun = true) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post(
        `${API}/custody/classify/auto-apply?dry_run=${dryRun}`,
        {},
        { headers: getAuthHeader() }
      );
      
      if (response.data.success) {
        if (!dryRun && response.data.result.classified_count > 0) {
          // Refresh data after actual classification
          await fetchAnalysis();
          await fetchMetrics();
          await fetchBatches();
          if (onClassificationComplete) {
            onClassificationComplete(response.data.result.classified_count);
          }
        }
        return response.data.result;
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Auto-classification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleBulkClassifyByPattern = async (patternId, classification, dryRun = true) => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await axios.post(
        `${API}/custody/classify/by-pattern`,
        { pattern_id: patternId, classification, dry_run: dryRun },
        { headers: getAuthHeader() }
      );
      
      if (response.data.success && !dryRun) {
        await fetchAnalysis();
        await fetchMetrics();
        await fetchBatches();
        if (onClassificationComplete) {
          onClassificationComplete(response.data.result.classified_count);
        }
      }
      return response.data.result;
    } catch (err) {
      setError(err.response?.data?.detail || 'Pattern classification failed');
    } finally {
      setLoading(false);
    }
  };

  const handleDecision = async (txId, accept, overrideType = null) => {
    setLoading(true);
    
    try {
      const response = await axios.post(
        `${API}/custody/classify/decide`,
        { tx_id: txId, accept, override_type: overrideType },
        { headers: getAuthHeader() }
      );
      
      if (response.data.success) {
        // Remove from suggestions list
        setAnalysis(prev => {
          if (!prev) return prev;
          
          const removeFromList = (list) => list?.filter(s => s.tx_id !== txId) || [];
          
          return {
            ...prev,
            by_confidence: {
              auto_apply: removeFromList(prev.by_confidence?.auto_apply),
              suggest: removeFromList(prev.by_confidence?.suggest),
              unresolved: removeFromList(prev.by_confidence?.unresolved)
            }
          };
        });
        
        await fetchMetrics();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Decision failed');
    } finally {
      setLoading(false);
    }
  };

  const handleRollback = async (batchId) => {
    setLoading(true);
    
    try {
      const response = await axios.post(
        `${API}/custody/classify/rollback/${batchId}`,
        {},
        { headers: getAuthHeader() }
      );
      
      if (response.data.success) {
        await fetchAnalysis();
        await fetchMetrics();
        await fetchBatches();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Rollback failed');
    } finally {
      setLoading(false);
    }
  };

  // Get filtered suggestions
  const getSuggestions = useCallback(() => {
    if (!analysis?.by_confidence) return [];
    
    switch (selectedConfidence) {
      case 'auto_apply':
        return analysis.by_confidence.auto_apply || [];
      case 'suggest':
        return analysis.by_confidence.suggest || [];
      case 'unresolved':
        return analysis.by_confidence.unresolved || [];
      default:
        return [
          ...(analysis.by_confidence.auto_apply || []),
          ...(analysis.by_confidence.suggest || []),
          ...(analysis.by_confidence.unresolved || [])
        ];
    }
  }, [analysis, selectedConfidence]);

  const unknownCount = analysis?.unknown_count || 0;
  const autoApplyCount = analysis?.by_confidence?.auto_apply?.length || 0;
  const suggestCount = analysis?.by_confidence?.suggest?.length || 0;
  const unresolvedCount = analysis?.by_confidence?.unresolved?.length || 0;

  const confidenceBadgeColor = (level) => {
    switch (level) {
      case 'auto_apply': return 'bg-green-600';
      case 'suggest': return 'bg-yellow-600';
      case 'unresolved': return 'bg-gray-600';
      default: return 'bg-gray-600';
    }
  };

  const classificationTypeLabel = (type) => {
    const labels = {
      'internal_transfer': 'Internal Transfer',
      'external_transfer': 'External Transfer',
      'swap': 'Swap/Trade',
      'bridge': 'Bridge',
      'deposit': 'Exchange Deposit',
      'withdrawal': 'Exchange Withdrawal',
      'buy': 'Buy',
      'sell': 'Sell',
      'reward': 'Reward/Income',
      'staking': 'Staking',
      'unknown': 'Unknown'
    };
    return labels[type] || type;
  };

  return (
    <div className="space-y-6" data-testid="unknown-tx-classifier">
      {/* Header with Stats */}
      <Card className="bg-gray-800 border-gray-700">
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-white flex items-center gap-2">
              <Target className="w-5 h-5 text-purple-400" />
              Unknown Transaction Classifier
            </CardTitle>
            <Button
              variant="outline"
              size="sm"
              onClick={fetchAnalysis}
              disabled={analyzing}
              className="border-gray-600 text-gray-300 hover:bg-gray-700"
              data-testid="refresh-analysis-btn"
            >
              {analyzing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {/* Stats Overview */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
            <div className="bg-gray-900/50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-white">{unknownCount}</div>
              <div className="text-xs text-gray-400">Unknown Transactions</div>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-green-400">{autoApplyCount}</div>
              <div className="text-xs text-gray-400">Auto-Classifiable (&gt;95%)</div>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-yellow-400">{suggestCount}</div>
              <div className="text-xs text-gray-400">Suggested (70-95%)</div>
            </div>
            <div className="bg-gray-900/50 rounded-lg p-3 text-center">
              <div className="text-2xl font-bold text-gray-400">{unresolvedCount}</div>
              <div className="text-xs text-gray-400">Unresolved (&lt;70%)</div>
            </div>
          </div>

          {/* Progress Bar */}
          {unknownCount > 0 && (
            <div className="space-y-2">
              <div className="flex justify-between text-sm text-gray-400">
                <span>Classification Coverage</span>
                <span>{Math.round(((autoApplyCount + suggestCount) / unknownCount) * 100)}%</span>
              </div>
              <Progress 
                value={((autoApplyCount + suggestCount) / unknownCount) * 100} 
                className="h-2 bg-gray-700"
              />
            </div>
          )}

          {/* Quick Action: Auto-Classify High Confidence */}
          {autoApplyCount > 0 && (
            <div className="mt-4 p-3 bg-green-900/20 border border-green-700 rounded-lg">
              <div className="flex items-center justify-between">
                <div>
                  <div className="text-green-400 font-medium flex items-center gap-2">
                    <Zap className="w-4 h-4" />
                    {autoApplyCount} transactions ready for auto-classification
                  </div>
                  <p className="text-sm text-gray-400 mt-1">
                    These have &gt;95% confidence and can be safely auto-classified
                  </p>
                </div>
                <Button
                  onClick={() => handleAutoClassify(false)}
                  disabled={loading}
                  className="bg-green-600 hover:bg-green-700 text-white"
                  data-testid="auto-classify-btn"
                >
                  {loading ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <Play className="w-4 h-4 mr-2" />
                  )}
                  Auto-Classify All
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <div className="bg-red-900/20 border border-red-700 rounded-lg p-4 text-red-400" data-testid="error-message">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-4 h-4" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* Tab Navigation */}
      <div className="flex border-b border-gray-700">
        {['suggestions', 'patterns', 'metrics', 'batches'].map(tab => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 text-sm font-medium capitalize transition-colors ${
              activeTab === tab
                ? 'text-purple-400 border-b-2 border-purple-400'
                : 'text-gray-400 hover:text-gray-200'
            }`}
            data-testid={`tab-${tab}`}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'suggestions' && (
        <div className="space-y-4">
          {/* Confidence Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-gray-400" />
            <select
              value={selectedConfidence}
              onChange={(e) => setSelectedConfidence(e.target.value)}
              className="bg-gray-800 border border-gray-700 text-gray-300 rounded-md px-3 py-1 text-sm"
              data-testid="confidence-filter"
            >
              <option value="all">All Confidence Levels</option>
              <option value="auto_apply">Auto-Apply (&gt;95%)</option>
              <option value="suggest">Suggested (70-95%)</option>
              <option value="unresolved">Unresolved (&lt;70%)</option>
            </select>
          </div>

          {/* Suggestions List */}
          <div className="space-y-2">
            {getSuggestions().slice(0, 50).map((suggestion, idx) => (
              <Card key={suggestion.tx_id || idx} className="bg-gray-800 border-gray-700">
                <CardContent className="p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center gap-2 mb-1">
                        <Badge className={confidenceBadgeColor(suggestion.confidence_level)}>
                          {Math.round(suggestion.confidence * 100)}% confidence
                        </Badge>
                        <span className="text-gray-400 text-sm">
                          {suggestion.amount} {suggestion.asset}
                        </span>
                      </div>
                      <div className="text-white">
                        <span className="text-gray-400">Current:</span> {classificationTypeLabel(suggestion.current_type)}
                        <span className="mx-2 text-gray-500">→</span>
                        <span className="text-purple-400 font-medium">
                          {classificationTypeLabel(suggestion.suggested_type)}
                        </span>
                      </div>
                      {suggestion.reasoning && suggestion.reasoning.length > 0 && (
                        <p className="text-xs text-gray-500 mt-1">
                          {suggestion.reasoning[0]}
                        </p>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDecision(suggestion.tx_id, true)}
                        className="text-green-400 hover:bg-green-900/30"
                        data-testid={`accept-${suggestion.tx_id}`}
                      >
                        <Check className="w-4 h-4" />
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => handleDecision(suggestion.tx_id, false)}
                        className="text-red-400 hover:bg-red-900/30"
                        data-testid={`reject-${suggestion.tx_id}`}
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
            
            {getSuggestions().length === 0 && (
              <div className="text-center text-gray-500 py-8">
                No suggestions in this category
              </div>
            )}
            
            {getSuggestions().length > 50 && (
              <div className="text-center text-gray-400 py-4">
                Showing first 50 of {getSuggestions().length} suggestions
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'patterns' && (
        <div className="space-y-4">
          {patterns.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              No patterns detected. Run analysis to detect patterns.
            </div>
          ) : (
            patterns.slice(0, 20).map((pattern, idx) => (
              <Card key={pattern.pattern_id || idx} className="bg-gray-800 border-gray-700">
                <CardContent className="p-4">
                  <div 
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setExpandedPattern(expandedPattern === pattern.pattern_id ? null : pattern.pattern_id)}
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <Badge className={pattern.confidence >= 0.9 ? 'bg-green-600' : 'bg-yellow-600'}>
                          {Math.round(pattern.confidence * 100)}%
                        </Badge>
                        <span className="text-white font-medium capitalize">
                          {pattern.pattern_type?.replace('_', ' ')}
                        </span>
                        <span className="text-gray-400 text-sm">
                          ({pattern.match_count} transactions)
                        </span>
                      </div>
                      <p className="text-sm text-gray-400 mt-1 truncate max-w-md">
                        {pattern.pattern_value?.substring(0, 30)}...
                      </p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge className="bg-purple-600">
                        {classificationTypeLabel(pattern.suggested_classification)}
                      </Badge>
                      {expandedPattern === pattern.pattern_id ? (
                        <ChevronUp className="w-4 h-4 text-gray-400" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-gray-400" />
                      )}
                    </div>
                  </div>
                  
                  {expandedPattern === pattern.pattern_id && (
                    <div className="mt-4 pt-4 border-t border-gray-700">
                      <p className="text-sm text-gray-400 mb-3">{pattern.reasoning}</p>
                      <div className="flex gap-2">
                        <Button
                          size="sm"
                          onClick={() => handleBulkClassifyByPattern(
                            pattern.pattern_id,
                            pattern.suggested_classification,
                            false
                          )}
                          disabled={loading}
                          className="bg-purple-600 hover:bg-purple-700"
                          data-testid={`classify-pattern-${pattern.pattern_id}`}
                        >
                          {loading ? (
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                          ) : (
                            <Check className="w-4 h-4 mr-2" />
                          )}
                          Classify All {pattern.match_count}
                        </Button>
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}

      {activeTab === 'metrics' && (
        <div className="space-y-4">
          <Card className="bg-gray-800 border-gray-700">
            <CardHeader>
              <CardTitle className="text-white flex items-center gap-2">
                <TrendingUp className="w-5 h-5 text-green-400" />
                Classification Performance (30 days)
              </CardTitle>
            </CardHeader>
            <CardContent>
              {metrics ? (
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <div className="bg-gray-900/50 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-white">
                      {metrics.current_unknown}
                    </div>
                    <div className="text-sm text-gray-400">Current Unknown</div>
                  </div>
                  <div className="bg-gray-900/50 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-green-400">
                      {Math.round((metrics.suggestion_accuracy || 0) * 100)}%
                    </div>
                    <div className="text-sm text-gray-400">Accuracy Rate</div>
                  </div>
                  <div className="bg-gray-900/50 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-purple-400">
                      {metrics.accepted || 0}
                    </div>
                    <div className="text-sm text-gray-400">Accepted</div>
                  </div>
                  <div className="bg-gray-900/50 rounded-lg p-4 text-center">
                    <div className="text-3xl font-bold text-red-400">
                      {metrics.rejected || 0}
                    </div>
                    <div className="text-sm text-gray-400">Rejected</div>
                  </div>
                </div>
              ) : (
                <div className="text-center text-gray-500 py-8">
                  Loading metrics...
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === 'batches' && (
        <div className="space-y-4">
          {batches.length === 0 ? (
            <div className="text-center text-gray-500 py-8">
              No classification batches yet
            </div>
          ) : (
            batches.map((batch, idx) => (
              <Card key={batch.batch_id || idx} className="bg-gray-800 border-gray-700">
                <CardContent className="p-4">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">
                          Batch: {batch.batch_id?.substring(0, 8)}...
                        </span>
                        <Badge className={batch.rolled_back ? 'bg-gray-600' : 'bg-green-600'}>
                          {batch.rolled_back ? 'Rolled Back' : 'Applied'}
                        </Badge>
                      </div>
                      <p className="text-sm text-gray-400 mt-1">
                        {batch.count} transactions classified on {new Date(batch.created_at).toLocaleDateString()}
                      </p>
                    </div>
                    {!batch.rolled_back && (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleRollback(batch.batch_id)}
                        disabled={loading}
                        className="border-red-700 text-red-400 hover:bg-red-900/30"
                        data-testid={`rollback-${batch.batch_id}`}
                      >
                        <Undo2 className="w-4 h-4 mr-2" />
                        Rollback
                      </Button>
                    )}
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      )}
    </div>
  );
};

export default UnknownTransactionClassifier;
