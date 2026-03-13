'use client';

import { useEffect, useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { marketsApi } from '@/lib/api';
import type { Market } from '@/lib/types';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Search, RefreshCw, ArrowRight, TrendingUp, TrendingDown, Loader2 } from 'lucide-react';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { toast } from 'sonner';
import { EXCHANGES } from '@/lib/constants';

export default function MarketsPage() {
  const [markets, setMarkets] = useState<Market[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [exchangeFilter, setExchangeFilter] = useState<string>('all');
  const [syncLoading, setSyncLoading] = useState(false);
  const router = useRouter();

  // Debounced search
  const [debouncedSearch, setDebouncedSearch] = useState('');
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  const fetchMarkets = useCallback(async () => {
    try {
      const params: Record<string, string | boolean | number> = { limit: 100 };
      if (debouncedSearch) params.symbol = debouncedSearch.toUpperCase();
      if (exchangeFilter !== 'all') params.exchange = exchangeFilter;

      const { data } = await marketsApi.list(params);
      setMarkets(data.items);
    } catch {
      toast.error('Failed to fetch markets');
    } finally {
      setLoading(false);
    }
  }, [debouncedSearch, exchangeFilter]);

  useEffect(() => {
    fetchMarkets();
  }, [fetchMarkets]);

  const handleSync = async () => {
    setSyncLoading(true);
    try {
      const { data } = await marketsApi.sync({
        exchanges: exchangeFilter !== 'all' ? [exchangeFilter] : [...EXCHANGES],
      });
      toast.success(data.message);
      fetchMarkets();
    } catch {
      toast.error('Sync failed');
    } finally {
      setSyncLoading(false);
    }
  };

  const handleMarketClick = (market: Market) => {
    router.push(`/chart?market_id=${market.id}&symbol=${market.symbol}&exchange=${market.exchange}`);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-white">Markets</h1>
          <p className="text-slate-400">Browse and monitor trading pairs</p>
        </div>
        <div className="flex items-center gap-3">
          <Select value={exchangeFilter} onValueChange={(v) => v && setExchangeFilter(v)}>
            <SelectTrigger className="w-[140px] bg-slate-900 border-slate-700 text-white">
              <SelectValue placeholder="Exchange" />
            </SelectTrigger>
            <SelectContent className="bg-slate-900 border-slate-700">
              <SelectItem value="all">All Exchanges</SelectItem>
              {EXCHANGES.map((ex) => (
                <SelectItem key={ex} value={ex} className="text-white">
                  {ex.charAt(0).toUpperCase() + ex.slice(1)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button
            variant="outline"
            className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
            onClick={handleSync}
            disabled={syncLoading}
          >
            {syncLoading ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <RefreshCw className="w-4 h-4 mr-2" />
            )}
            Sync
          </Button>
        </div>
      </div>

      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <Input
          placeholder="Search markets..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="pl-10 bg-slate-900 border-slate-700 text-white placeholder:text-slate-500"
        />
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
        </div>
      ) : markets.length === 0 ? (
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <p className="text-slate-400 mb-4">No markets found</p>
            <Button onClick={handleSync} disabled={syncLoading}>
              Sync Markets
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-4">
          {markets.map((market) => (
            <Card
              key={market.id}
              className="bg-slate-900 border-slate-800 hover:border-slate-700 transition-colors cursor-pointer"
              onClick={() => handleMarketClick(market)}
            >
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary" className="bg-slate-800 text-slate-300">
                      {market.exchange}
                    </Badge>
                    <CardTitle className="text-lg text-white">
                      {market.base_asset}/{market.quote_asset}
                    </CardTitle>
                  </div>
                  {market.active ? (
                    <Badge className="bg-emerald-500/10 text-emerald-400">Active</Badge>
                  ) : (
                    <Badge variant="destructive">Inactive</Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-sm text-slate-500">Symbol</p>
                    <p className="text-white font-mono">{market.symbol}</p>
                  </div>
                  <ArrowRight className="w-5 h-5 text-slate-500" />
                </div>
                <div className="mt-3 flex items-center gap-4 text-sm">
                  <div className="flex items-center text-slate-400">
                    <TrendingUp className="w-4 h-4 mr-1" />
                    {market.price_precision ?? '-'}
                  </div>
                  <div className="flex items-center text-slate-400">
                    <TrendingDown className="w-4 h-4 mr-1" />
                    {market.amount_precision ?? '-'}
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
