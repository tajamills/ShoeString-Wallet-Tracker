import React, { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Loader2, CheckCircle, XCircle, Lock } from 'lucide-react';
import axios from 'axios';

const API_URL = process.env.REACT_APP_BACKEND_URL;

export const ResetPasswordPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState(false);

  // Validate token exists
  const isValidToken = token && token.length > 10;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');

    // Validate passwords match
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }

    // Validate password strength
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }

    setLoading(true);

    try {
      await axios.post(`${API_URL}/api/auth/reset-password`, {
        token: token,
        new_password: password
      });
      setSuccess(true);
    } catch (err) {
      const message = err.response?.data?.detail || 'Failed to reset password. The link may be expired.';
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  // If no token, show error
  if (!isValidToken) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-[#0C0C0E]/50 border-[#1F1F22]">
          <CardHeader className="text-center">
            <XCircle className="w-16 h-16 text-[#FF3B30] mx-auto mb-4" />
            <CardTitle className="text-white text-2xl">Invalid Reset Link</CardTitle>
            <CardDescription className="text-[#8A8A93]">
              This password reset link is invalid or has expired.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => window.location.href = '/'}
              className="w-full bg-white text-black hover:bg-gray-200"
            >
              Go to Homepage
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Success state
  if (success) {
    return (
      <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4">
        <Card className="w-full max-w-md bg-[#0C0C0E]/50 border-[#1F1F22]">
          <CardHeader className="text-center">
            <CheckCircle className="w-16 h-16 text-[#00C805] mx-auto mb-4" />
            <CardTitle className="text-white text-2xl">Password Reset!</CardTitle>
            <CardDescription className="text-[#8A8A93]">
              Your password has been successfully reset. You can now log in with your new password.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={() => window.location.href = '/'}
              className="w-full bg-white text-black hover:bg-gray-200"
            >
              Go to Login
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Reset password form
  return (
    <div className="min-h-screen bg-[#050505] flex items-center justify-center p-4">
      <Card className="w-full max-w-md bg-[#0C0C0E]/50 border-[#1F1F22]">
        <CardHeader className="text-center">
          <Lock className="w-12 h-12 text-[#00C805] mx-auto mb-2" />
          <CardTitle className="text-white text-2xl">Reset Your Password</CardTitle>
          <CardDescription className="text-[#8A8A93]">
            Enter your new password below
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="password" className="text-white">New Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="Enter new password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={6}
                className="bg-[#161618] border-[#1F1F22] text-white"
                data-testid="new-password-input"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="confirmPassword" className="text-white">Confirm Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="Confirm new password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={6}
                className="bg-[#161618] border-[#1F1F22] text-white"
                data-testid="confirm-password-input"
              />
            </div>

            {error && (
              <Alert className="bg-red-900/20 border-red-900 text-[#FF3B30]">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            <Button
              type="submit"
              className="w-full bg-white text-black hover:bg-gray-200"
              disabled={loading}
              data-testid="reset-password-submit"
            >
              {loading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Resetting...
                </>
              ) : (
                'Reset Password'
              )}
            </Button>
          </form>

          <div className="mt-4 text-center">
            <a href="/" className="text-sm text-[#00C805] hover:text-[#00C805]">
              Back to Homepage
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};
