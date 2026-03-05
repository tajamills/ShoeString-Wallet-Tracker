import { useState, useEffect } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

export const usePayment = (user, getAuthHeader, fetchUserProfile) => {
  const [paymentSuccess, setPaymentSuccess] = useState(false);
  const [paymentError, setPaymentError] = useState('');

  // Check for payment success on URL
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search);
    const sessionId = urlParams.get('session_id');

    if (sessionId && user) {
      pollPaymentStatus(sessionId);
    }
  }, [user]);

  const pollPaymentStatus = async (sessionId, attempts = 0) => {
    const maxAttempts = 5;

    if (attempts >= maxAttempts) {
      setPaymentError('Payment verification timed out. Please check your subscription status.');
      return;
    }

    try {
      const response = await axios.get(
        `${API}/payments/status/${sessionId}`,
        { headers: getAuthHeader() }
      );

      if (response.data.payment_status === 'paid') {
        setPaymentSuccess(true);
        setPaymentError('');
        await fetchUserProfile();
        // Remove session_id from URL
        window.history.replaceState({}, document.title, window.location.pathname);
        return;
      }

      if (response.data.status !== 'expired') {
        setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2000);
      } else {
        setPaymentError('Payment session expired.');
      }
    } catch (err) {
      console.error('Error checking payment status:', err);
      if (attempts < maxAttempts) {
        setTimeout(() => pollPaymentStatus(sessionId, attempts + 1), 2000);
      }
    }
  };

  return {
    paymentSuccess,
    paymentError,
    setPaymentSuccess,
    setPaymentError
  };
};
