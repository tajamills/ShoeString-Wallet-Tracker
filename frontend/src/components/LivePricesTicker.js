import React, { useState, useEffect } from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const TRACKED_ASSETS = [
  { symbol: 'BTC', name: 'Bitcoin' },
  { symbol: 'ETH', name: 'Ethereum' },
  { symbol: 'SOL', name: 'Solana' },
  { symbol: 'XRP', name: 'XRP' },
  { symbol: 'DOGE', name: 'Dogecoin' }
];

const formatPrice = (price) => {
  if (!price) return '—';
  if (price >= 1000) return `$${price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
  if (price >= 1) return `$${price.toFixed(2)}`;
  return `$${price.toFixed(4)}`;
};

const formatChange = (change) => {
  if (change === null || change === undefined) return null;
  const formatted = Math.abs(change).toFixed(2);
  return change >= 0 ? `+${formatted}%` : `-${formatted}%`;
};

export const LivePricesTicker = () => {
  const [prices, setPrices] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPrices = async () => {
      try {
        const results = await Promise.all(
          TRACKED_ASSETS.map(async (asset) => {
            try {
              const response = await axios.get(
                `${BACKEND_URL}/api/alerts/public/price/${asset.symbol}`
              );
              return { symbol: asset.symbol, data: response.data };
            } catch (err) {
              return { symbol: asset.symbol, data: null };
            }
          })
        );
        
        const priceMap = {};
        results.forEach(({ symbol, data }) => {
          if (data && data.price) priceMap[symbol] = data;
        });
        setPrices(priceMap);
      } catch (err) {
        console.error('Failed to fetch prices:', err);
      } finally {
        setLoading(false);
      }
    };

    fetchPrices();
    const interval = setInterval(fetchPrices, 30000); // Update every 30s
    return () => clearInterval(interval);
  }, []);

  if (loading) {
    return (
      <div className="w-full bg-black/40 backdrop-blur-sm border-b border-white/5">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div className="flex items-center justify-center gap-8 overflow-x-auto">
            {TRACKED_ASSETS.map((asset) => (
              <div key={asset.symbol} className="flex items-center gap-3 animate-pulse">
                <span className="text-white/40 font-medium">{asset.symbol}</span>
                <div className="h-4 w-20 bg-white/10 rounded"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full bg-black/40 backdrop-blur-sm border-b border-white/5">
      <div className="max-w-6xl mx-auto px-4 py-3">
        <div className="flex items-center justify-center gap-6 md:gap-10 overflow-x-auto scrollbar-hide">
          {TRACKED_ASSETS.map((asset) => {
            const priceData = prices[asset.symbol];
            const change = priceData?.change_24h;
            const isPositive = change >= 0;
            
            return (
              <div 
                key={asset.symbol} 
                className="flex items-center gap-2 md:gap-3 shrink-0"
              >
                <span className="text-white/60 text-sm font-medium tracking-wide">
                  {asset.symbol}
                </span>
                <span className="text-white font-semibold text-sm md:text-base">
                  {formatPrice(priceData?.price)}
                </span>
                {change !== null && change !== undefined && (
                  <span className={`flex items-center gap-0.5 text-xs font-medium ${
                    isPositive ? 'text-emerald-400' : 'text-red-400'
                  }`}>
                    {isPositive ? (
                      <TrendingUp className="w-3 h-3" />
                    ) : (
                      <TrendingDown className="w-3 h-3" />
                    )}
                    {formatChange(change)}
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};

export default LivePricesTicker;
