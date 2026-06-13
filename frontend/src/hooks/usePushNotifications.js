/**
 * Push Notification Hook for CryptoBagTracker
 * Handles service worker registration, permission requests, and subscription management
 */

import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

// Convert VAPID key from base64 URL to Uint8Array
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - base64String.length % 4) % 4);
  const base64 = (base64String + padding)
    .replace(/-/g, '+')
    .replace(/_/g, '/');
  
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  
  for (let i = 0; i < rawData.length; ++i) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
}

export function usePushNotifications(getAuthHeader) {
  const [isSupported, setIsSupported] = useState(false);
  const [isSubscribed, setIsSubscribed] = useState(false);
  const [permission, setPermission] = useState('default');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Check if push notifications are supported
  useEffect(() => {
    const supported = 'serviceWorker' in navigator && 
                      'PushManager' in window && 
                      'Notification' in window;
    setIsSupported(supported);
    
    if (supported) {
      setPermission(Notification.permission);
    }
  }, []);

  // Check current subscription status
  const checkSubscription = useCallback(async () => {
    if (!isSupported) {
      setLoading(false);
      return;
    }

    try {
      // Check with backend
      const response = await axios.get(`${API}/push/status`, {
        headers: getAuthHeader()
      });
      setIsSubscribed(response.data.subscribed);
    } catch (err) {
      console.error('Error checking push status:', err);
    } finally {
      setLoading(false);
    }
  }, [isSupported, getAuthHeader]);

  useEffect(() => {
    checkSubscription();
  }, [checkSubscription]);

  // Subscribe to push notifications
  const subscribe = useCallback(async () => {
    if (!isSupported) {
      setError('Push notifications are not supported in this browser');
      return false;
    }

    setLoading(true);
    setError(null);

    try {
      // Request notification permission
      const permissionResult = await Notification.requestPermission();
      setPermission(permissionResult);
      
      if (permissionResult !== 'granted') {
        setError('Notification permission denied');
        setLoading(false);
        return false;
      }

      // Register service worker
      const registration = await navigator.serviceWorker.register('/sw.js');
      await navigator.serviceWorker.ready;

      // Get VAPID public key from server
      const vapidResponse = await axios.get(`${API}/push/vapid-public-key`);
      const vapidPublicKey = vapidResponse.data.publicKey;

      // Subscribe to push
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(vapidPublicKey)
      });

      // Send subscription to server
      await axios.post(`${API}/push/subscribe`, {
        subscription: subscription.toJSON()
      }, {
        headers: getAuthHeader()
      });

      setIsSubscribed(true);
      setLoading(false);
      return true;
    } catch (err) {
      console.error('Error subscribing to push:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to enable push notifications');
      setLoading(false);
      return false;
    }
  }, [isSupported, getAuthHeader]);

  // Unsubscribe from push notifications
  const unsubscribe = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      // Unsubscribe from browser
      const registration = await navigator.serviceWorker.getRegistration();
      if (registration) {
        const subscription = await registration.pushManager.getSubscription();
        if (subscription) {
          await subscription.unsubscribe();
        }
      }

      // Unsubscribe from server
      await axios.delete(`${API}/push/unsubscribe`, {
        headers: getAuthHeader()
      });

      setIsSubscribed(false);
      setLoading(false);
      return true;
    } catch (err) {
      console.error('Error unsubscribing from push:', err);
      setError(err.response?.data?.detail || err.message || 'Failed to disable push notifications');
      setLoading(false);
      return false;
    }
  }, [getAuthHeader]);

  // Send test notification
  const sendTest = useCallback(async () => {
    try {
      const response = await axios.post(`${API}/push/test`, {
        title: 'CryptoBagTracker Test',
        body: 'Push notifications are working! You will receive alerts here.'
      }, {
        headers: getAuthHeader()
      });
      return response.data;
    } catch (err) {
      console.error('Error sending test push:', err);
      throw err;
    }
  }, [getAuthHeader]);

  return {
    isSupported,
    isSubscribed,
    permission,
    loading,
    error,
    subscribe,
    unsubscribe,
    sendTest,
    checkSubscription
  };
}

export default usePushNotifications;
