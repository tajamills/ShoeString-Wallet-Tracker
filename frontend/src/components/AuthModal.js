import React, { useState } from 'react';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export const AuthModal = ({ isOpen, onClose }) => {
  const [mode, setMode] = useState('login'); // 'login', 'register', 'forgot'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState('');
  const { login, register } = useAuth();

  const resetForm = () => {
    setError('');
    setSuccessMessage('');
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSuccessMessage('');
    setLoading(true);

    try {
      if (mode === 'forgot') {
        await axios.post(`${API_URL}/api/auth/forgot-password`, { email });
        setSuccessMessage('If this email exists, a password reset link has been sent. Check your inbox.');
      } else if (mode === 'login') {
        await login(email, password);
        onClose();
      } else {
        await register(email, password);
        onClose();
      }
    } catch (err) {
      setError(err.response?.data?.detail || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const getTitle = () => {
    if (mode === 'forgot') return 'Reset Password';
    return mode === 'login' ? 'Login' : 'Sign Up';
  };

  const getDescription = () => {
    if (mode === 'forgot') return "Enter your email and we'll send you a reset link.";
    return mode === 'login' 
      ? 'Welcome back! Enter your credentials to continue.' 
      : 'Create an account to start tracking wallets.';
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-md bg-slate-800 border-slate-700" data-testid="auth-modal">
        <DialogHeader>
          <DialogTitle className="text-white text-2xl">
            {getTitle()}
          </DialogTitle>
          <DialogDescription className="text-gray-400">
            {getDescription()}
          </DialogDescription>
        </DialogHeader>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="email" className="text-gray-300">Email</Label>
            <Input
              id="email"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="bg-slate-700 border-slate-600 text-white"
              data-testid="email-input"
            />
          </div>
          
          {mode !== 'forgot' && (
            <div className="space-y-2">
              <Label htmlFor="password" className="text-gray-300">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="bg-slate-700 border-slate-600 text-white"
                data-testid="password-input"
              />
              {mode === 'register' && (
                <p className="text-xs text-gray-400">Minimum 6 characters</p>
              )}
            </div>
          )}

          {error && (
            <Alert className="bg-red-900/20 border-red-900 text-red-300" data-testid="auth-error">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {successMessage && (
            <Alert className="bg-green-900/20 border-green-900 text-green-300" data-testid="auth-success">
              <CheckCircle className="h-4 w-4 inline mr-2" />
              <AlertDescription className="inline">{successMessage}</AlertDescription>
            </Alert>
          )}

          <Button
            type="submit"
            className="w-full bg-purple-600 hover:bg-purple-700"
            disabled={loading || !!successMessage}
            data-testid="auth-submit-button"
          >
            {loading ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {mode === 'forgot' ? 'Sending...' : mode === 'login' ? 'Logging in...' : 'Creating account...'}
              </>
            ) : (
              mode === 'forgot' ? 'Send Reset Link' : mode === 'login' ? 'Login' : 'Sign Up'
            )}
          </Button>

          <div className="text-center text-sm space-y-2">
            {mode === 'login' && (
              <button
                type="button"
                onClick={() => { setMode('forgot'); resetForm(); }}
                className="text-gray-400 hover:text-gray-300 block w-full"
                data-testid="forgot-password-link"
              >
                Forgot your password?
              </button>
            )}
            
            {mode === 'forgot' ? (
              <button
                type="button"
                onClick={() => { setMode('login'); resetForm(); }}
                className="text-purple-400 hover:text-purple-300"
              >
                Back to login
              </button>
            ) : (
              <button
                type="button"
                onClick={() => {
                  setMode(mode === 'login' ? 'register' : 'login');
                  resetForm();
                }}
                className="text-purple-400 hover:text-purple-300"
              >
                {mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Login'}
              </button>
            )}
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
