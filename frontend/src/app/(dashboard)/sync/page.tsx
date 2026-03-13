'use client';

import { useCallback, useEffect, useState } from 'react';
import { formatDistanceToNow } from 'date-fns';
import { Loader2, RefreshCw, Search, ServerCrash, UploadCloud } from 'lucide-react';
import { toast } from 'sonner';

import { dataApi } from '@/lib/api';
import { TIMEFRAMES_WITH_LABELS } from '@/lib/constants';
import type { BackfillTaskStatus, SyncState } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

const STATUS_OPTIONS = [
  { value: 'all', label: 'All statuses' },
  { value: 'idle', label: 'Idle' },
  { value: 'syncing', label: 'Syncing' },
  { value: 'error', label: 'Error' },
] as const;

function formatDateTime(value: string | null) {
  if (!value) {
    return 'Never';
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Invalid date' : date.toLocaleString();
}

function formatRelativeTime(value: string | null) {
  if (!value) {
    return 'Never';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Invalid date';
  }

  return formatDistanceToNow(date, { addSuffix: true });
}

function renderStatusBadge(status: string) {
  if (status === 'error') {
    return <Badge variant="destructive">Error</Badge>;
  }

  if (status === 'syncing' || status === 'queued' || status === 'pending' || status === 'running') {
    return <Badge className="bg-amber-500/10 text-amber-300">Syncing</Badge>;
  }

  if (status === 'completed') {
    return <Badge className="bg-emerald-500/10 text-emerald-400">Completed</Badge>;
  }

  return <Badge className="bg-slate-700 text-slate-200">{status}</Badge>;
}

export default function SyncPage() {
  const [syncStates, setSyncStates] = useState<SyncState[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [timeframeFilter, setTimeframeFilter] = useState('all');
  const [togglingKey, setTogglingKey] = useState<string | null>(null);
  const [backfillingKey, setBackfillingKey] = useState<string | null>(null);
  const [taskStatus, setTaskStatus] = useState<BackfillTaskStatus | null>(null);

  const loadSyncStates = useCallback(async (showLoader = false) => {
    if (showLoader) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    try {
      const { data } = await dataApi.getSyncStates({ limit: 200 });
      setSyncStates(data.items);
    } catch {
      toast.error('Failed to load sync states');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadSyncStates(true);
  }, [loadSyncStates]);

  useEffect(() => {
    if (!taskStatus || !['queued', 'pending', 'running'].includes(taskStatus.status)) {
      return;
    }

    const interval = window.setInterval(async () => {
      try {
        const { data } = await dataApi.getBackfillStatus(taskStatus.task_id);
        setTaskStatus(data);

        if (data.status === 'completed') {
          toast.success(`Backfill task ${data.task_id} completed`);
          void loadSyncStates();
        }

        if (data.status === 'failed') {
          toast.error(data.error || `Backfill task ${data.task_id} failed`);
        }
      } catch {
        toast.error('Failed to refresh backfill task status');
      }
    }, 4000);

    return () => {
      window.clearInterval(interval);
    };
  }, [loadSyncStates, taskStatus]);

  const filteredStates = syncStates.filter((state) => {
    const matchesSearch =
      !search ||
      state.symbol.toLowerCase().includes(search.toLowerCase()) ||
      state.exchange.toLowerCase().includes(search.toLowerCase());

    const matchesStatus =
      statusFilter === 'all' || state.sync_status === statusFilter;

    const matchesTimeframe =
      timeframeFilter === 'all' || state.timeframe === timeframeFilter;

    return matchesSearch && matchesStatus && matchesTimeframe;
  });

  const autoSyncEnabledCount = syncStates.filter((state) => state.is_auto_syncing).length;
  const errorCount = syncStates.filter((state) => state.sync_status === 'error').length;

  const handleAutoSyncToggle = async (state: SyncState, enabled: boolean) => {
    if (!state.market_id) {
      toast.error('This row is missing a market_id, so auto-sync cannot be changed');
      return;
    }

    const key = `${state.id}:${state.timeframe}`;
    setTogglingKey(key);

    try {
      const { data } = await dataApi.setAutoSync({
        market_id: state.market_id,
        timeframes: [state.timeframe],
        enabled,
      });
      toast.success(data.message);
      await loadSyncStates();
    } catch {
      toast.error('Failed to update auto-sync setting');
    } finally {
      setTogglingKey(null);
    }
  };

  const handleBackfill = async (state: SyncState) => {
    if (!state.market_id) {
      toast.error('This row is missing a market_id, so backfill cannot be started');
      return;
    }

    const key = `${state.id}:${state.timeframe}`;
    setBackfillingKey(key);

    try {
      const { data } = await dataApi.startBackfill({
        market_ids: [state.market_id],
        timeframes: [state.timeframe],
      });

      setTaskStatus({
        task_id: data.task_id,
        status: data.status,
        total_combinations: data.estimated_timeframes,
        completed_combinations: 0,
        failed_combinations: 0,
        started_at: null,
        completed_at: null,
        error: null,
      });

      toast.success(data.message);
    } catch {
      toast.error('Failed to start backfill');
    } finally {
      setBackfillingKey(null);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Sync Control</h1>
          <p className="text-slate-400">
            Monitor sync state, toggle auto-sync, and trigger per-market backfills.
          </p>
        </div>
        <Button
          variant="outline"
          className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
          onClick={() => void loadSyncStates()}
          disabled={refreshing}
        >
          {refreshing ? (
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
          ) : (
            <RefreshCw className="mr-2 h-4 w-4" />
          )}
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-400">Tracked Sync States</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-white">{syncStates.length}</p>
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-400">Auto-Sync Enabled</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-emerald-400">{autoSyncEnabledCount}</p>
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-400">Rows With Errors</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-3xl font-semibold text-red-400">{errorCount}</p>
          </CardContent>
        </Card>
      </div>

      {taskStatus && (
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-white">
              <UploadCloud className="h-5 w-5 text-emerald-500" />
              Latest Backfill Task
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4 md:grid-cols-5">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Task ID</p>
              <p className="mt-1 font-mono text-sm text-white">{taskStatus.task_id}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Status</p>
              <div className="mt-1">{renderStatusBadge(taskStatus.status)}</div>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Progress</p>
              <p className="mt-1 text-sm text-white">
                {taskStatus.completed_combinations}/{taskStatus.total_combinations}
              </p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Failed</p>
              <p className="mt-1 text-sm text-white">{taskStatus.failed_combinations}</p>
            </div>
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Completed</p>
              <p className="mt-1 text-sm text-white">
                {taskStatus.completed_at ? formatDateTime(taskStatus.completed_at) : 'In progress'}
              </p>
            </div>
            {taskStatus.error && (
              <div className="md:col-span-5">
                <p className="text-xs uppercase tracking-wide text-slate-500">Error</p>
                <p className="mt-1 text-sm text-red-300">{taskStatus.error}</p>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Card className="border-slate-800 bg-slate-900">
        <CardHeader>
          <CardTitle className="text-white">Filters</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-[1.6fr,1fr,1fr]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-500" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search by symbol or exchange"
              className="border-slate-700 bg-slate-950 pl-10 text-white placeholder:text-slate-500"
            />
          </div>
          <Select value={statusFilter} onValueChange={(value) => setStatusFilter(value ?? 'all')}>
            <SelectTrigger className="w-full border-slate-700 bg-slate-950 text-white">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent className="border-slate-700 bg-slate-900 text-white">
              {STATUS_OPTIONS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={timeframeFilter} onValueChange={(value) => setTimeframeFilter(value ?? 'all')}>
            <SelectTrigger className="w-full border-slate-700 bg-slate-950 text-white">
              <SelectValue placeholder="Timeframe" />
            </SelectTrigger>
            <SelectContent className="border-slate-700 bg-slate-900 text-white">
              <SelectItem value="all">All timeframes</SelectItem>
              {TIMEFRAMES_WITH_LABELS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </CardContent>
      </Card>

      <Card className="border-slate-800 bg-slate-900">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-white">Sync States</CardTitle>
          <Badge variant="secondary" className="bg-slate-800 text-slate-300">
            {filteredStates.length} visible
          </Badge>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex min-h-[240px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-emerald-500" />
            </div>
          ) : filteredStates.length === 0 ? (
            <div className="flex min-h-[240px] flex-col items-center justify-center gap-3 text-center">
              <ServerCrash className="h-10 w-10 text-slate-600" />
              <div>
                <p className="text-white">No sync states match the current filters.</p>
                <p className="text-sm text-slate-500">
                  Try refreshing, or loosen the search, status, or timeframe filter.
                </p>
              </div>
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800 hover:bg-transparent">
                  <TableHead className="text-slate-400">Market</TableHead>
                  <TableHead className="text-slate-400">Timeframe</TableHead>
                  <TableHead className="text-slate-400">Status</TableHead>
                  <TableHead className="text-slate-400">Last Sync</TableHead>
                  <TableHead className="text-slate-400">Auto Sync</TableHead>
                  <TableHead className="text-slate-400">Error</TableHead>
                  <TableHead className="text-right text-slate-400">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredStates.map((state) => {
                  const rowKey = `${state.id}:${state.timeframe}`;
                  const isToggling = togglingKey === rowKey;
                  const isBackfilling = backfillingKey === rowKey;

                  return (
                    <TableRow key={rowKey} className="border-slate-800">
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium text-white">{state.symbol}</span>
                          <span className="text-xs text-slate-500">{state.exchange}</span>
                        </div>
                      </TableCell>
                      <TableCell className="font-mono text-white">{state.timeframe}</TableCell>
                      <TableCell>{renderStatusBadge(state.sync_status)}</TableCell>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="text-white">{formatRelativeTime(state.last_sync_time)}</span>
                          <span className="text-xs text-slate-500">
                            {formatDateTime(state.last_sync_time)}
                          </span>
                        </div>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Switch
                            checked={state.is_auto_syncing}
                            disabled={isToggling || !state.market_id}
                            onCheckedChange={(checked) =>
                              void handleAutoSyncToggle(state, checked)
                            }
                          />
                          <span className="text-sm text-slate-300">
                            {state.is_auto_syncing ? 'On' : 'Off'}
                          </span>
                          {isToggling && <Loader2 className="h-4 w-4 animate-spin text-emerald-400" />}
                        </div>
                      </TableCell>
                      <TableCell>
                        <p className="max-w-[240px] truncate text-sm text-slate-400">
                          {state.error_message || 'None'}
                        </p>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="outline"
                          size="sm"
                          className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
                          disabled={isBackfilling || !state.market_id}
                          onClick={() => void handleBackfill(state)}
                        >
                          {isBackfilling ? (
                            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                          ) : (
                            <UploadCloud className="mr-2 h-4 w-4" />
                          )}
                          Backfill
                        </Button>
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
