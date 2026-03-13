'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { marketsApi, backtestApi } from '@/lib/api';
import type { BacktestResult, Market } from '@/lib/types';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Loader2, Play, Target, BarChart3, Activity } from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { toast } from 'sonner';

const STRATEGIES = [
  { value: 'ma_crossover', label: 'Moving Average Crossover' },
  { value: 'rsi', label: 'RSI Mean Reversion' },
];

const TIMEFRAMES = [
  { value: '1m', label: '1 minute' },
  { value: '5m', label: '5 minutes' },
  { value: '15m', label: '15 minutes' },
  { value: '1h', label: '1 hour' },
  { value: '4h', label: '4 hours' },
  { value: '1d', label: '1 day' },
];

function isValidDateInput(value: string | null): value is string {
  return typeof value === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(value);
}

function normalizeDateInput(value: string | null): string {
  if (isValidDateInput(value)) {
    return value;
  }

  return '';
}

function getDefaultDateRange() {
  const now = new Date();
  const threeMonthsAgo = new Date(now);
  threeMonthsAgo.setMonth(threeMonthsAgo.getMonth() - 3);

  return {
    startDate: threeMonthsAgo.toISOString().split('T')[0],
    endDate: now.toISOString().split('T')[0],
  };
}

function toChartStartTime(value: string) {
  return new Date(`${value}T00:00:00.000Z`).toISOString();
}

function toChartEndTime(value: string) {
  return new Date(`${value}T23:59:59.999Z`).toISOString();
}

export default function BacktestPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedMarketId = searchParams.get('market_id') ?? '';
  const requestedTimeframe = searchParams.get('timeframe');
  const requestedStartDate = searchParams.get('start_date');
  const requestedEndDate = searchParams.get('end_date');
  const [markets, setMarkets] = useState<Market[]>([]);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<BacktestResult | null>(null);

  // Form state
  const [selectedMarketId, setSelectedMarketId] = useState<string>(requestedMarketId);
  const [strategy, setStrategy] = useState('ma_crossover');
  const [timeframe, setTimeframe] = useState<string>(
    requestedTimeframe && TIMEFRAMES.some((option) => option.value === requestedTimeframe)
      ? requestedTimeframe
      : '1h',
  );
  const [startDate, setStartDate] = useState<string>(normalizeDateInput(requestedStartDate));
  const [endDate, setEndDate] = useState<string>(normalizeDateInput(requestedEndDate));
  const [initialBalance, setInitialBalance] = useState('10000');

  // Strategy params
  const [fastPeriod, setFastPeriod] = useState('10');
  const [slowPeriod, setSlowPeriod] = useState('20');
  const [rsiPeriod, setRsiPeriod] = useState('14');

  const selectedMarket = markets.find((market) => market.id.toString() === selectedMarketId);

  useEffect(() => {
    if (requestedMarketId) {
      setSelectedMarketId(requestedMarketId);
    }

    if (requestedTimeframe && TIMEFRAMES.some((option) => option.value === requestedTimeframe)) {
      setTimeframe(requestedTimeframe);
    }

    if (isValidDateInput(requestedStartDate)) {
      setStartDate(requestedStartDate);
    }

    if (isValidDateInput(requestedEndDate)) {
      setEndDate(requestedEndDate);
    }
  }, [requestedEndDate, requestedMarketId, requestedStartDate, requestedTimeframe, searchParams]);

  useEffect(() => {
    if (startDate && endDate) {
      return;
    }

    const defaults = getDefaultDateRange();
    if (!startDate) {
      setStartDate(defaults.startDate);
    }
    if (!endDate) {
      setEndDate(defaults.endDate);
    }
  }, [endDate, startDate]);

  useEffect(() => {
    marketsApi
      .list({ limit: 50 })
      .then((res) => setMarkets(res.data.items))
      .catch(() => toast.error('Failed to load markets'));
  }, []);

  const handleRunBacktest = async () => {
    if (!selectedMarket || !startDate || !endDate) {
      toast.error('Please fill in all required fields');
      return;
    }

    setRunning(true);
    setResult(null);

    try {
      const { data } = await backtestApi.run({
        market_id: selectedMarket.id,
        symbol: selectedMarket.symbol,
        strategy,
        start_date: startDate,
        end_date: endDate,
        initial_balance: parseFloat(initialBalance),
        timeframe,
        params: {
          fast_period: parseInt(fastPeriod),
          slow_period: parseInt(slowPeriod),
          rsi_period: parseInt(rsiPeriod),
        },
      });

      setResult(data);
      toast.success('Backtest completed!');
    } catch (error: unknown) {
      const err = error as { response?: { data?: { detail?: string } } };
      toast.error(err.response?.data?.detail || 'Backtest failed');
    } finally {
      setRunning(false);
    }
  };

  const handleOpenChart = () => {
    if (!selectedMarket || !startDate || !endDate) {
      toast.error('Select a market and date range first');
      return;
    }

    const params = new URLSearchParams({
      market_id: selectedMarket.id.toString(),
      symbol: selectedMarket.symbol,
      exchange: selectedMarket.exchange,
      timeframe,
      start_time: toChartStartTime(startDate),
      end_time: toChartEndTime(endDate),
    });

    router.push(`/chart?${params.toString()}`);
  };

  const equityCurve = result?.equity_curve.map((value, index) => ({
    time: index,
    value,
  }));

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Backtest</h1>
          <p className="text-slate-400">Test your trading strategies with historical data</p>
        </div>
        <Button
          variant="outline"
          onClick={handleOpenChart}
          disabled={!selectedMarket}
          className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
        >
          <Activity className="w-4 h-4 mr-2" />
          Open in Chart
        </Button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration */}
        <Card className="bg-slate-900 border-slate-800 lg:col-span-1">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <Target className="w-5 h-5 text-emerald-500" />
              Configuration
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label className="text-slate-300">Market</Label>
              <Select value={selectedMarketId} onValueChange={(value) => value && setSelectedMarketId(value)}>
                <SelectTrigger className="bg-slate-800 border-slate-700 text-white">
                  <SelectValue placeholder="Select market" />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-slate-700">
                  {markets.map((m) => (
                    <SelectItem key={m.id} value={m.id.toString()} className="text-white">
                      {m.symbol} ({m.exchange})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-300">Strategy</Label>
              <Select value={strategy} onValueChange={(v) => v && setStrategy(v)}>
                <SelectTrigger className="bg-slate-800 border-slate-700 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-slate-700">
                  {STRATEGIES.map((s) => (
                    <SelectItem key={s.value} value={s.value} className="text-white">
                      {s.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-300">Timeframe</Label>
              <Select value={timeframe} onValueChange={(v) => v && setTimeframe(v)}>
                <SelectTrigger className="bg-slate-800 border-slate-700 text-white">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className="bg-slate-900 border-slate-700">
                  {TIMEFRAMES.map((t) => (
                    <SelectItem key={t.value} value={t.value} className="text-white">
                      {t.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label className="text-slate-300">Start Date</Label>
                <Input
                  type="date"
                  value={startDate}
                  onChange={(e) => setStartDate(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white"
                />
              </div>
              <div className="space-y-2">
                <Label className="text-slate-300">End Date</Label>
                <Input
                  type="date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white"
                />
              </div>
            </div>

            <div className="space-y-2">
              <Label className="text-slate-300">Initial Balance (USDT)</Label>
              <Input
                type="number"
                value={initialBalance}
                onChange={(e) => setInitialBalance(e.target.value)}
                className="bg-slate-800 border-slate-700 text-white"
              />
            </div>

            {/* Strategy Parameters */}
            {strategy === 'ma_crossover' && (
              <div className="grid grid-cols-2 gap-4 pt-4 border-t border-slate-800">
                <div className="space-y-2">
                  <Label className="text-slate-300">Fast Period</Label>
                  <Input
                    type="number"
                    value={fastPeriod}
                    onChange={(e) => setFastPeriod(e.target.value)}
                    className="bg-slate-800 border-slate-700 text-white"
                  />
                </div>
                <div className="space-y-2">
                  <Label className="text-slate-300">Slow Period</Label>
                  <Input
                    type="number"
                    value={slowPeriod}
                    onChange={(e) => setSlowPeriod(e.target.value)}
                    className="bg-slate-800 border-slate-700 text-white"
                  />
                </div>
              </div>
            )}

            {strategy === 'rsi' && (
              <div className="space-y-2 pt-4 border-t border-slate-800">
                <Label className="text-slate-300">RSI Period</Label>
                <Input
                  type="number"
                  value={rsiPeriod}
                  onChange={(e) => setRsiPeriod(e.target.value)}
                  className="bg-slate-800 border-slate-700 text-white"
                />
              </div>
            )}

            <Button
              className="w-full bg-emerald-600 hover:bg-emerald-700"
              onClick={handleRunBacktest}
              disabled={running}
            >
              {running ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Play className="w-4 h-4 mr-2" />
              )}
              Run Backtest
            </Button>
          </CardContent>
        </Card>

        {/* Results */}
        <Card className="bg-slate-900 border-slate-800 lg:col-span-2">
          <CardHeader>
            <CardTitle className="text-white flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-emerald-500" />
              Results
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!result ? (
              <div className="flex flex-col items-center justify-center h-[400px] text-slate-400">
                <BarChart3 className="w-16 h-16 mb-4 opacity-20" />
                <p>Configure and run a backtest to see results</p>
              </div>
            ) : (
              <Tabs defaultValue="overview" className="w-full">
                <TabsList className="bg-slate-800">
                  <TabsTrigger value="overview" className="text-slate-300">
                    Overview
                  </TabsTrigger>
                  <TabsTrigger value="chart" className="text-slate-300">
                    Equity Curve
                  </TabsTrigger>
                  <TabsTrigger value="trades" className="text-slate-300">
                    Trades ({result.trades.length})
                  </TabsTrigger>
                </TabsList>

                <TabsContent value="overview" className="mt-4">
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-slate-400 text-sm">Initial Balance</p>
                      <p className="text-2xl font-bold text-white">
                        ${result.initial_balance.toFixed(2)}
                      </p>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-slate-400 text-sm">Final Balance</p>
                      <p
                        className={`text-2xl font-bold ${
                          result.final_balance >= result.initial_balance
                            ? 'text-emerald-500'
                            : 'text-red-500'
                        }`}
                      >
                        ${result.final_balance.toFixed(2)}
                      </p>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-slate-400 text-sm">Total Return</p>
                      <p
                        className={`text-2xl font-bold ${
                          result.total_return >= 0 ? 'text-emerald-500' : 'text-red-500'
                        }`}
                      >
                        {result.total_return >= 0 ? '+' : ''}
                        {result.total_return.toFixed(2)}%
                      </p>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-slate-400 text-sm">Win Rate</p>
                      <p className="text-2xl font-bold text-white">
                        {result.win_rate.toFixed(1)}%
                      </p>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-slate-400 text-sm">Total Trades</p>
                      <p className="text-2xl font-bold text-white">{result.total_trades}</p>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-slate-400 text-sm">Profit Factor</p>
                      <p className="text-2xl font-bold text-white">
                        {result.profit_factor.toFixed(2)}
                      </p>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-slate-400 text-sm">Sharpe Ratio</p>
                      <p className="text-2xl font-bold text-white">
                        {result.sharpe_ratio.toFixed(2)}
                      </p>
                    </div>
                    <div className="bg-slate-800/50 rounded-lg p-4">
                      <p className="text-slate-400 text-sm">Max Drawdown</p>
                      <p className="text-2xl font-bold text-red-500">
                        -{result.max_drawdown.toFixed(2)}%
                      </p>
                    </div>
                  </div>
                </TabsContent>

                <TabsContent value="chart" className="mt-4">
                  {equityCurve && equityCurve.length > 0 ? (
                    <ResponsiveContainer width="100%" height={350}>
                      <LineChart data={equityCurve}>
                        <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                        <XAxis dataKey="time" stroke="#64748b" fontSize={12} />
                        <YAxis
                          stroke="#64748b"
                          fontSize={12}
                          domain={['auto', 'auto']}
                          tickFormatter={(value) => `$${value.toFixed(0)}`}
                        />
                        <Tooltip
                          contentStyle={{
                            backgroundColor: '#1e293b',
                            border: '1px solid #334155',
                            borderRadius: '8px',
                          }}
                          labelStyle={{ color: '#94a3b8' }}
                          formatter={(value) => [`$${(value as number).toFixed(2)}`, 'Balance']}
                        />
                        <Line
                          type="monotone"
                          dataKey="value"
                          stroke="#10b981"
                          strokeWidth={2}
                          dot={false}
                        />
                      </LineChart>
                    </ResponsiveContainer>
                  ) : (
                    <div className="flex items-center justify-center h-[350px] text-slate-400">
                      No equity curve data
                    </div>
                  )}
                </TabsContent>

                <TabsContent value="trades" className="mt-4">
                  <div className="max-h-[400px] overflow-y-auto">
                    <Table>
                      <TableHeader>
                        <TableRow className="border-slate-800 hover:bg-transparent">
                          <TableHead className="text-slate-400">Side</TableHead>
                          <TableHead className="text-slate-400">Entry</TableHead>
                          <TableHead className="text-slate-400">Exit</TableHead>
                          <TableHead className="text-slate-400">Qty</TableHead>
                          <TableHead className="text-slate-400">P&L</TableHead>
                          <TableHead className="text-slate-400">P&L %</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {result.trades.map((trade, idx) => (
                          <TableRow key={idx} className="border-slate-800">
                            <TableCell>
                              <Badge
                                className={
                                  trade.side === 'long' || trade.side === 'buy'
                                    ? 'bg-emerald-500/10 text-emerald-400'
                                    : 'bg-red-500/10 text-red-400'
                                }
                              >
                                {trade.side}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-white font-mono">
                              ${trade.entry_price.toFixed(2)}
                            </TableCell>
                            <TableCell className="text-white font-mono">
                              ${trade.exit_price.toFixed(2)}
                            </TableCell>
                            <TableCell className="text-white font-mono">
                              {trade.quantity.toFixed(4)}
                            </TableCell>
                            <TableCell
                              className={`font-mono ${
                                trade.pnl >= 0 ? 'text-emerald-500' : 'text-red-500'
                              }`}
                            >
                              {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                            </TableCell>
                            <TableCell
                              className={`font-mono ${
                                trade.pnl_percent >= 0 ? 'text-emerald-500' : 'text-red-500'
                              }`}
                            >
                              {trade.pnl_percent >= 0 ? '+' : ''}
                              {trade.pnl_percent.toFixed(2)}%
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>
                </TabsContent>
              </Tabs>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
