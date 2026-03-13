'use client';

import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useRouter } from 'next/navigation';
import { dataApi, getWSUrl, normalizeOhlcvTuple } from '@/lib/api';
import type { OHLCV } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { ArrowLeft, Loader2, Activity, Clock, TrendingUp, TrendingDown, FlaskConical } from 'lucide-react';
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

type ChartCandle = OHLCV & { timeStr: string };

const RANGE_PRESETS = [
  { label: '7D', days: 7 },
  { label: '30D', days: 30 },
  { label: '90D', days: 90 },
] as const;

function formatDateInput(value: Date) {
  return value.toISOString().split('T')[0];
}

function defaultRangeStart(days: number) {
  const start = new Date();
  start.setDate(start.getDate() - days);
  return formatDateInput(start);
}

function defaultRangeEnd() {
  return formatDateInput(new Date());
}

function parseDateInput(value: string | null) {
  if (!value) {
    return null;
  }

  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return value;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : formatDateInput(date);
}

function toRangeStartIso(value: string) {
  return new Date(`${value}T00:00:00.000Z`).toISOString();
}

function toRangeEndIso(value: string) {
  return new Date(`${value}T23:59:59.999Z`).toISOString();
}

function formatCandle(candle: OHLCV): ChartCandle {
  return {
    ...candle,
    timeStr: format(new Date(candle.time), 'yyyy-MM-dd HH:mm'),
  };
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ChartCandle }> }) {
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

  const marketId = searchParams.get('market_id');
  const symbol = searchParams.get('symbol') || '';
  const exchange = searchParams.get('exchange') || '';
  const requestedTimeframe = searchParams.get('timeframe');
  const requestedStartTime = searchParams.get('start_time');
  const requestedEndTime = searchParams.get('end_time');

  const [timeframe, setTimeframe] = useState(
    requestedTimeframe && TIMEFRAMES_SHORT.some((option) => option.value === requestedTimeframe)
      ? requestedTimeframe
      : '1h',
  );
  const [startDate, setStartDate] = useState(
    parseDateInput(requestedStartTime) ?? defaultRangeStart(30),
  );
  const [endDate, setEndDate] = useState(
    parseDateInput(requestedEndTime) ?? defaultRangeEnd(),
  );
  const [data, setData] = useState<ChartCandle[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastPrice, setLastPrice] = useState<number>(0);
  const [priceChange, setPriceChange] = useState<number>(0);

  const handleOpenBacktest = useCallback(() => {
    if (!marketId) {
      return;
    }

    const params = new URLSearchParams({
      market_id: marketId,
      timeframe,
    });

    if (symbol) {
      params.set('symbol', symbol);
    }

    params.set('start_date', startDate);
    params.set('end_date', endDate);

    router.push(`/backtest?${params.toString()}`);
  }, [endDate, marketId, router, startDate, symbol, timeframe]);

  useEffect(() => {
    if (requestedTimeframe && TIMEFRAMES_SHORT.some((option) => option.value === requestedTimeframe)) {
      setTimeframe(requestedTimeframe);
    }
    const parsedStartDate = parseDateInput(requestedStartTime);
    const parsedEndDate = parseDateInput(requestedEndTime);

    if (parsedStartDate) {
      setStartDate(parsedStartDate);
    }

    if (parsedEndDate) {
      setEndDate(parsedEndDate);
    }
  }, [requestedEndTime, requestedStartTime, requestedTimeframe]);

  const fetchData = useCallback(async () => {
    if (!marketId) return;
    if (startDate > endDate) {
      setData([]);
      setLoading(false);
      return;
    }

    setLoading(true);
    try {
      const { data: ohlcvData } = await dataApi.getOHLCV({
        market_id: parseInt(marketId),
        timeframe,
        start_time: toRangeStartIso(startDate),
        end_time: toRangeEndIso(endDate),
        limit: 500,
      });

      const formatted = ohlcvData.map(formatCandle);

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
  }, [endDate, marketId, startDate, timeframe]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // WebSocket for real-time updates
  useEffect(() => {
    if (!marketId || !timeframe) return;

    const ws = new WebSocket(
      getWSUrl(`/ws/data/ohlcv?market_id=${marketId}&timeframe=${timeframe}`)
    );

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        if (message.type === 'ohlcv_update' && Array.isArray(message.data)) {
          const candle = normalizeOhlcvTuple(message.data);
          setData((prev) => {
            const newData = [...prev];
            const lastIndex = newData.length - 1;
            if (lastIndex >= 0 && newData[lastIndex].time === candle.time) {
              newData[lastIndex] = formatCandle(candle);
            } else {
              newData.push(formatCandle(candle));
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

        <div className="flex flex-wrap items-center justify-end gap-2">
          <Button
            variant="outline"
            onClick={handleOpenBacktest}
            className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
          >
            <FlaskConical className="w-4 h-4 mr-2" />
            Backtest This Market
          </Button>
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

      <Card className="bg-slate-900 border-slate-800">
        <CardContent className="flex flex-col gap-4 pt-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="flex flex-wrap items-center gap-2">
            {RANGE_PRESETS.map((preset) => (
              <Button
                key={preset.label}
                variant="outline"
                size="sm"
                onClick={() => {
                  setStartDate(defaultRangeStart(preset.days));
                  setEndDate(defaultRangeEnd());
                }}
                className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
              >
                {preset.label}
              </Button>
            ))}
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex flex-col gap-2 text-sm text-slate-400">
              Start Date
              <Input
                type="date"
                value={startDate}
                onChange={(event) => setStartDate(event.target.value)}
                className="bg-slate-800 border-slate-700 text-white"
              />
            </label>
            <label className="flex flex-col gap-2 text-sm text-slate-400">
              End Date
              <Input
                type="date"
                value={endDate}
                onChange={(event) => setEndDate(event.target.value)}
                className="bg-slate-800 border-slate-700 text-white"
              />
            </label>
          </div>
        </CardContent>
      </Card>

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
          ) : startDate > endDate ? (
            <div className="flex items-center justify-center h-[500px]">
              <p className="text-slate-400">Start date must be on or before end date</p>
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
