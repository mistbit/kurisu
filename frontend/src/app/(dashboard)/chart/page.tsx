'use client';

import { useEffect, useState, useCallback, useRef, useMemo } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { dataApi, getWSUrl } from '@/lib/api';
import type { OHLCV } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ArrowLeft, Loader2, Activity, Clock, TrendingUp, TrendingDown } from 'lucide-react';
import {
  ComposedChart,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Area,
  Bar,
  CartesianGrid,
} from 'recharts';
import { format } from 'date-fns';
import { TIMEFRAMES_SHORT } from '@/lib/constants';

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: OHLCV & { timeStr: string } }> }) {
  if (!active || !payload || !payload.length) return null;

  const data = payload[0].payload;
  return (
    <div className="bg-slate-900 border border-slate-700 p-3 rounded-lg shadow-xl">
      <p className="text-slate-400 text-xs mb-2">{data.timeStr}</p>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
        <span className="text-slate-500">O:</span>
        <span className="text-white font-mono">{data.open.toFixed(2)}</span>
        <span className="text-slate-500">H:</span>
        <span className="text-white font-mono">{data.high.toFixed(2)}</span>
        <span className="text-slate-500">L:</span>
        <span className="text-white font-mono">{data.low.toFixed(2)}</span>
        <span className="text-slate-500">C:</span>
        <span className="text-white font-mono">{data.close.toFixed(2)}</span>
        <span className="text-slate-500">Vol:</span>
        <span className="text-white font-mono">{data.volume.toFixed(2)}</span>
      </div>
    </div>
  );
}

export default function ChartPage() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const wsRef = useRef<WebSocket | null>(null);

  const marketId = searchParams.get('market_id');
  const symbol = searchParams.get('symbol') || '';
  const exchange = searchParams.get('exchange') || '';

  const [timeframe, setTimeframe] = useState('1h');
  const [data, setData] = useState<Array<OHLCV & { timeStr: string }>>([]);
  const [loading, setLoading] = useState(true);
  const [lastPrice, setLastPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);

  const fetchData = useCallback(async () => {
    if (!marketId) return;

    setLoading(true);
    try {
      const endTime = Date.now();
      const startTime = endTime - 30 * 24 * 60 * 60 * 1000; // 30 days

      const { data: ohlcvData } = await dataApi.getOHLCV({
        market_id: parseInt(marketId),
        timeframe,
        start_time: startTime,
        end_time: endTime,
        limit: 500,
      });

      const formatted = ohlcvData.map((item) => ({
        time: item[0],
        open: item[1],
        high: item[2],
        low: item[3],
        close: item[4],
        volume: item[5],
        timeStr: format(new Date(item[0]), 'yyyy-MM-dd HH:mm'),
      }));

      setData(formatted);

      if (formatted.length > 0) {
        const last = formatted[formatted.length - 1];
        const first = formatted[0];
        setLastPrice(last.close);
        setPriceChange(((last.close - first.open) / first.open) * 100);
      }
    } catch (error) {
      console.error('Failed to fetch OHLCV data:', error);
    } finally {
      setLoading(false);
    }
  }, [marketId, timeframe]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // WebSocket for real-time updates
  useEffect(() => {
    if (!marketId || !timeframe) return;

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/api/v1/ws/ohlcv?market_id=${marketId}&timeframe=${timeframe}`;

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'ohlcv') {
          const candle = message.data as OHLCV;
          setData((prev) => {
            const newData = [...prev];
            const lastIndex = newData.length - 1;
            if (lastIndex >= 0 && newData[lastIndex].time === candle.time) {
              newData[lastIndex] = {
                ...candle,
                timeStr: format(new Date(candle.time), 'yyyy-MM-dd HH:mm'),
              };
            } else {
              newData.push({
                ...candle,
                timeStr: format(new Date(candle.time), 'yyyy-MM-dd HH:mm'),
              });
            }
            if (newData.length > 500) newData.shift();
            return newData;
          });
          setLastPrice(candle.close);
        }
      } catch (e) {
        console.error('WebSocket message error:', e);
      }
    };

    return () => {
      ws.close();
    };
  }, [marketId, timeframe]);

  if (!marketId) {
    return (
      <div className="flex flex-col items-center justify-center h-[60vh]">
        <p className="text-slate-400 mb-4">No market selected</p>
        <Button onClick={() => router.push('/markets')}>
          <ArrowLeft className="w-4 h-4 mr-2" />
          Go to Markets
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.back()}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-2xl font-bold text-white">{symbol}</h1>
              <Badge variant="secondary" className="bg-slate-800 text-slate-300">
                {exchange}
              </Badge>
            </div>
            <p className="text-slate-400 text-sm">
              {lastPrice.toFixed(2)} ({priceChange >= 0 ? '+' : ''}
              {priceChange.toFixed(2)}%)
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {TIMEFRAMES_SHORT.map((tf) => (
            <Button
              key={tf.value}
              variant={timeframe === tf.value ? 'default' : 'outline'}
              size="sm"
              onClick={() => setTimeframe(tf.value)}
              className={
                timeframe === tf.value
                  ? 'bg-emerald-600 hover:bg-emerald-700'
                  : 'border-slate-700 text-slate-400 hover:bg-slate-800'
              }
            >
              {tf.label}
            </Button>
          ))}
        </div>
      </div>

      {/* Chart */}
      <Card className="bg-slate-900 border-slate-800">
        <CardHeader className="pb-0">
          <div className="flex items-center justify-between">
            <CardTitle className="text-white flex items-center gap-2">
              <Activity className="w-5 h-5 text-emerald-500" />
              Price Chart
            </CardTitle>
            <div className="flex items-center gap-4 text-sm text-slate-400">
              <span className="flex items-center gap-1">
                <Clock className="w-4 h-4" />
                {data.length} candles
              </span>
            </div>
          </div>
        </CardHeader>
        <CardContent className="pt-4">
          {loading ? (
            <div className="flex items-center justify-center h-[500px]">
              <Loader2 className="w-8 h-8 animate-spin text-emerald-500" />
            </div>
          ) : data.length === 0 ? (
            <div className="flex items-center justify-center h-[500px]">
              <p className="text-slate-400">No data available</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height={500}>
              <ComposedChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorVolume" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#10b981" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="#10b981" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" vertical={false} />
                <XAxis
                  dataKey="timeStr"
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  interval="preserveStartEnd"
                />
                <YAxis
                  yAxisId="left"
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  domain={['auto', 'auto']}
                  tickFormatter={(value) => value.toFixed(2)}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  stroke="#64748b"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  domain={[0, 'auto']}
                  tickFormatter={(value) => value.toFixed(0)}
                />
                <Tooltip content={<CustomTooltip />} />
                <Area
                  yAxisId="left"
                  type="monotone"
                  dataKey="close"
                  stroke="#10b981"
                  strokeWidth={2}
                  fill="url(#colorVolume)"
                  name="Price"
                />
                <Bar
                  yAxisId="right"
                  dataKey="volume"
                  fill="#10b981"
                  opacity={0.3}
                  name="Volume"
                />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </CardContent>
      </Card>

      {/* Price Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 text-sm">24h High</span>
              {priceChange >= 0 ? (
                <TrendingUp className="w-4 h-4 text-emerald-500" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-500" />
              )}
            </div>
            <p className="text-2xl font-bold text-white mt-1">
              {data.length > 0 ? Math.max(...data.map((d) => d.high)).toFixed(2) : '-'}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="pt-6">
            <div className="flex items-center justify-between">
              <span className="text-slate-400 text-sm">24h Low</span>
              {priceChange >= 0 ? (
                <TrendingUp className="w-4 h-4 text-emerald-500" />
              ) : (
                <TrendingDown className="w-4 h-4 text-red-500" />
              )}
            </div>
            <p className="text-2xl font-bold text-white mt-1">
              {data.length > 0 ? Math.min(...data.map((d) => d.low)).toFixed(2) : '-'}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="pt-6">
            <span className="text-slate-400 text-sm">24h Volume</span>
            <p className="text-2xl font-bold text-white mt-1">
              {data.length > 0 ? data.reduce((sum, d) => sum + d.volume, 0).toFixed(0) : '-'}
            </p>
          </CardContent>
        </Card>
        <Card className="bg-slate-900 border-slate-800">
          <CardContent className="pt-6">
            <span className="text-slate-400 text-sm">Change</span>
            <p
              className={`text-2xl font-bold mt-1 ${
                priceChange >= 0 ? 'text-emerald-500' : 'text-red-500'
              }`}
            >
              {priceChange >= 0 ? '+' : ''}
              {priceChange.toFixed(2)}%
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}