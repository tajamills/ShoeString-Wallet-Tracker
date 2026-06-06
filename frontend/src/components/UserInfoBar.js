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
      <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]" data-testid="login-prompt">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <p className="text-white">Login to start analyzing wallets</p>
            <Button
              onClick={onLogin}
              className="bg-white text-black hover:bg-gray-200"
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
    <Card className="bg-[#0C0C0E]/50 border-[#1F1F22]" data-testid="user-info-bar">
      <CardContent className="py-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <User className="w-5 h-5 text-[#00C805]" />
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
                <span className="text-sm text-[#8A8A93]">
                  {user.subscription_tier === 'free'
                    ? `${user.analysis_count || 0}/1 free analysis`
                    : 'Unlimited analyses'}
                </span>
                {user.subscription_tier !== 'free' && onDowngrade && (
                  <button
                    onClick={onDowngrade}
                    className="text-xs text-[#4A4A52] hover:text-[#8A8A93] underline ml-2"
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
              className="border-[#1F1F22] text-[#00C805] hover:bg-[#161618]"
              data-testid="affiliate-button"
            >
              <Users className="w-4 h-4 mr-2" />
              Affiliate
            </Button>
            <Button
              variant="outline"
              onClick={onLogout}
              className="border-[#1F1F22] text-white hover:bg-[#161618]"
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
