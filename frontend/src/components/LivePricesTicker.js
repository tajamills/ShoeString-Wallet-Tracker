import React, { useState, useEffect } from 'react';
import { ChartLineUp, ChartLineDown } from '@phosphor-icons/react';
import Marquee from 'react-fast-marquee';
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
    const interval = setInterval(fetchPrices, 30000);
    return () => clearInterval(interval);
  }, []);

  const renderPriceItem = (asset) => {
    const priceData = prices[asset.symbol];
    const change = priceData?.change_24h;
    const isPositive = change >= 0;
    
    return (
      <div 
        key={asset.symbol} 
        className="flex items-center gap-3 mx-8 shrink-0"
      >
        <span className="text-[#8A8A93] text-xs font-mono tracking-wider">
          {asset.symbol}
        </span>
        <span className="text-white font-mono text-sm tabular-nums">
          {formatPrice(priceData?.price)}
        </span>
        {change !== null && change !== undefined && (
          <span className={`flex items-center gap-1 text-xs font-mono tabular-nums ${
            isPositive ? 'text-[#00C805]' : 'text-[#FF3B30]'
          }`}>
            {isPositive ? (
              <ChartLineUp size={12} weight="bold" />
            ) : (
              <ChartLineDown size={12} weight="bold" />
            )}
            {formatChange(change)}
          </span>
        )}
      </div>
    );
  };

  if (loading) {
    return (
      <div className="w-full bg-[#0C0C0E] border-b border-[#1F1F22]">
        <div className="px-4 py-2">
          <div className="flex items-center justify-center gap-8">
            {TRACKED_ASSETS.map((asset) => (
              <div key={asset.symbol} className="flex items-center gap-3">
                <span className="text-[#4A4A52] font-mono text-xs">{asset.symbol}</span>
                <div className="h-4 w-20 bg-[#1F1F22]"></div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="w-full bg-[#0C0C0E] border-b border-[#1F1F22]">
      <Marquee gradient={false} speed={40} pauseOnHover={true}>
        {TRACKED_ASSETS.map(renderPriceItem)}
        {TRACKED_ASSETS.map((asset) => renderPriceItem({ ...asset, symbol: asset.symbol }))}
      </Marquee>
    </div>
  );
};

export default LivePricesTicker;
