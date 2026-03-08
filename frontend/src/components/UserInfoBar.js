import React from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { User, Crown, LogOut, Users } from 'lucide-react';

export const UserInfoBar = ({
  user,
  onLogin,
  onLogout,
  onUpgrade,
  onDowngrade,
  onOpenAffiliate
}) => {
  if (!user) {
    return (
      <Card className="bg-slate-800/50 border-slate-700" data-testid="login-prompt">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <p className="text-gray-300">Login to start analyzing wallets</p>
            <Button
              onClick={onLogin}
              className="bg-purple-600 hover:bg-purple-700"
              data-testid="login-button"
            >
              Login / Sign Up
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="bg-slate-800/50 border-slate-700" data-testid="user-info-bar">
      <CardContent className="py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <User className="w-5 h-5 text-purple-400" />
            <div>
              <p className="text-white font-medium">{user.email}</p>
              <div className="flex items-center gap-2 mt-1">
                <Badge
                  className={`${
                    user.subscription_tier === 'free'
                      ? 'bg-gray-600'
                      : 'bg-gradient-to-r from-yellow-600 to-orange-600'
                  }`}
                >
                  {user.subscription_tier !== 'free' && (
                    <Crown className="w-3 h-3 mr-1" />
                  )}
                  {user.subscription_tier === 'free' ? 'FREE' : 'UNLIMITED'}
                </Badge>
                <span className="text-sm text-gray-400">
                  {user.subscription_tier === 'free'
                    ? `${user.analysis_count || 0}/1 free analysis`
                    : 'Unlimited analyses'}
                </span>
                {user.subscription_tier !== 'free' && onDowngrade && (
                  <button
                    onClick={onDowngrade}
                    className="text-xs text-gray-500 hover:text-gray-400 underline ml-2"
                  >
                    manage
                  </button>
                )}
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            {user.subscription_tier === 'free' && (
              <Button
                onClick={onUpgrade}
                className="bg-gradient-to-r from-yellow-600 to-orange-600 hover:from-yellow-700 hover:to-orange-700"
                data-testid="upgrade-button"
              >
                <Crown className="w-4 h-4 mr-2" />
                Get Unlimited
              </Button>
            )}
            <Button
              variant="outline"
              onClick={onOpenAffiliate}
              className="border-purple-600 text-purple-300 hover:bg-purple-900/30"
              data-testid="affiliate-button"
            >
              <Users className="w-4 h-4 mr-2" />
              Affiliate
            </Button>
            <Button
              variant="outline"
              onClick={onLogout}
              className="border-slate-600 text-gray-300 hover:bg-slate-700"
              data-testid="logout-button"
            >
              <LogOut className="w-4 h-4 mr-2" />
              Logout
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};
