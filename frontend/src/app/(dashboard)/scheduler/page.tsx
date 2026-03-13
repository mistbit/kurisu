'use client';

import { useCallback, useEffect, useState } from 'react';
import { Clock3, Database, Loader2, RefreshCw, Server } from 'lucide-react';
import { toast } from 'sonner';

import { schedulerApi } from '@/lib/api';
import type { SchedulerJob, SchedulerStatus } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

function formatDateTime(value: string | null) {
  if (!value) {
    return 'Never';
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 'Invalid date' : date.toLocaleString();
}

function getStatNumber(job: SchedulerJob, key: string) {
  const value = job.stats[key];
  return typeof value === 'number' ? value : 0;
}

export default function SchedulerPage() {
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const loadStatus = useCallback(async (showLoader = false) => {
    if (showLoader) {
      setLoading(true);
    } else {
      setRefreshing(true);
    }

    try {
      const { data } = await schedulerApi.getStatus();
      setStatus(data);
    } catch {
      toast.error('Failed to load scheduler status');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus(true);
  }, [loadStatus]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void loadStatus();
    }, 15000);

    return () => {
      window.clearInterval(interval);
    };
  }, [loadStatus]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">Scheduler Monitor</h1>
          <p className="text-slate-400">
            Observe job cadence, Redis job storage, and run statistics from the backend scheduler.
          </p>
        </div>
        <Button
          variant="outline"
          className="border-slate-700 text-slate-300 hover:bg-slate-800 hover:text-white"
          onClick={() => void loadStatus()}
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

      <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-400">Scheduler</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <div>
              <p className="text-2xl font-semibold text-white">
                {status?.running ? 'Running' : 'Stopped'}
              </p>
            </div>
            <Server className="h-6 w-6 text-emerald-500" />
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-400">Job Store</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <p className="text-2xl font-semibold text-white">
              {status?.job_store ?? 'Unknown'}
            </p>
            <Database className="h-6 w-6 text-sky-400" />
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-400">Active Streams</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <p className="text-2xl font-semibold text-white">
              {status?.active_connections ?? 0}
            </p>
            <Clock3 className="h-6 w-6 text-amber-400" />
          </CardContent>
        </Card>
        <Card className="border-slate-800 bg-slate-900">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm text-slate-400">Tracked Jobs</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center justify-between">
            <p className="text-2xl font-semibold text-white">{status?.jobs.length ?? 0}</p>
            <RefreshCw className="h-6 w-6 text-violet-400" />
          </CardContent>
        </Card>
      </div>

      <Card className="border-slate-800 bg-slate-900">
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-white">Job Details</CardTitle>
          <Badge variant="secondary" className="bg-slate-800 text-slate-300">
            Auto-refresh every 15s
          </Badge>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex min-h-[240px] items-center justify-center">
              <Loader2 className="h-8 w-8 animate-spin text-emerald-500" />
            </div>
          ) : !status || status.jobs.length === 0 ? (
            <div className="flex min-h-[240px] items-center justify-center text-slate-400">
              No scheduler jobs were reported by the backend.
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow className="border-slate-800 hover:bg-transparent">
                  <TableHead className="text-slate-400">Job</TableHead>
                  <TableHead className="text-slate-400">Next Run</TableHead>
                  <TableHead className="text-slate-400">Last Run</TableHead>
                  <TableHead className="text-slate-400">Runs</TableHead>
                  <TableHead className="text-slate-400">Success</TableHead>
                  <TableHead className="text-slate-400">Failed</TableHead>
                  <TableHead className="text-slate-400">Synced</TableHead>
                  <TableHead className="text-slate-400">Last Error</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {status.jobs.map((job) => (
                  <TableRow key={job.id} className="border-slate-800">
                    <TableCell>
                      <div className="flex flex-col">
                        <span className="font-medium text-white">{job.name}</span>
                        <span className="font-mono text-xs text-slate-500">{job.id}</span>
                      </div>
                    </TableCell>
                    <TableCell className="text-white">
                      {formatDateTime(job.next_run_time)}
                    </TableCell>
                    <TableCell className="text-white">
                      {formatDateTime(job.last_run_time)}
                    </TableCell>
                    <TableCell className="text-white">
                      {getStatNumber(job, 'total_runs')}
                    </TableCell>
                    <TableCell className="text-emerald-400">
                      {getStatNumber(job, 'successful_runs')}
                    </TableCell>
                    <TableCell className="text-red-400">
                      {getStatNumber(job, 'failed_runs')}
                    </TableCell>
                    <TableCell className="text-white">
                      {getStatNumber(job, 'total_synced')}
                    </TableCell>
                    <TableCell>
                      <p className="max-w-[240px] truncate text-sm text-slate-400">
                        {(typeof job.stats.last_error === 'string' && job.stats.last_error) || 'None'}
                      </p>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
