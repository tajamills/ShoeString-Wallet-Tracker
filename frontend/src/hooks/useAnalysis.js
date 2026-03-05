import { useState } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const useAnalysis = (getAuthHeader, fetchUserProfile) => {
  const [loading, setLoading] = useState(false);
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState('');
  const [multiChainResults, setMultiChainResults] = useState(null);
  const [analyzingAll, setAnalyzingAll] = useState(false);

  const analyzeWallet = async (address, chain, startDate, endDate) => {
    if (!address) {
      setError('Please enter a wallet address');
      return null;
    }

    // EVM chain validation
    if (['ethereum', 'arbitrum', 'bsc', 'polygon'].includes(chain)) {
      if (!address.startsWith('0x') || address.length !== 42) {
        setError('Please enter a valid address (0x...)');
        return null;
      }
    }

    setLoading(true);
    setError('');
    setAnalysis(null);
    setMultiChainResults(null);

    try {
      const payload = { address, chain };
      if (startDate) payload.start_date = startDate;
      if (endDate) payload.end_date = endDate;

      const response = await axios.post(
        `${API}/wallet/analyze`,
        payload,
        { headers: getAuthHeader() }
      );
      
      setAnalysis(response.data);
      if (fetchUserProfile) await fetchUserProfile();
      return response.data;
    } catch (err) {
      if (err.response?.status === 429) {
        setError('Daily limit reached! Upgrade to Premium for unlimited wallet analyses.');
      } else if (err.response?.status === 401) {
        setError('Please login to continue');
      } else {
        setError(err.response?.data?.detail || 'Failed to analyze wallet. Please try again.');
      }
      return null;
    } finally {
      setLoading(false);
    }
  };

  const analyzeAllChains = async (address, startDate, endDate) => {
    if (!address) {
      setError('Please enter a wallet address');
      return null;
    }

    if (!address.startsWith('0x') || address.length !== 42) {
      setError('Please enter a valid EVM address (0x...) for multi-chain analysis');
      return null;
    }

    setAnalyzingAll(true);
    setError('');
    setAnalysis(null);
    setMultiChainResults(null);

    try {
      const payload = { address, chain: 'ethereum' };
      if (startDate) payload.start_date = startDate;
      if (endDate) payload.end_date = endDate;

      const response = await axios.post(
        `${API}/wallet/analyze-all`,
        payload,
        { headers: getAuthHeader() }
      );

      setMultiChainResults(response.data);
      if (fetchUserProfile) await fetchUserProfile();
      return response.data;
    } catch (err) {
      if (err.response?.status === 403) {
        setError('Analyze All Chains is a Pro-only feature. Upgrade to Pro!');
      } else {
        setError(err.response?.data?.detail || 'Failed to analyze wallet across all chains');
      }
      return null;
    } finally {
      setAnalyzingAll(false);
    }
  };

  const clearAnalysis = () => {
    setAnalysis(null);
    setMultiChainResults(null);
    setError('');
  };

  return {
    loading,
    analysis,
    error,
    setError,
    multiChainResults,
    analyzingAll,
    analyzeWallet,
    analyzeAllChains,
    clearAnalysis,
    setAnalysis
  };
};
