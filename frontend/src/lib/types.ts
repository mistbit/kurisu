export type AuthToken = {
  access_token: string;
  token_type: string;
  expires_in: number;
};

export type User = {
  id: number;
  username: string;
  email: string;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
};

export type Market = {
  id: number;
  exchange: string;
  symbol: string;
  base_asset: string;
  quote_asset: string;
  active: boolean;
  meta: Record<string, unknown> | null;
  exchange_symbol: string | null;
  price_precision: number | null;
  amount_precision: number | null;
};

export type OhlcvTuple = [number, number, number, number, number, number];

export type OHLCV = {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
};

export type BacktestTrade = {
  entry_time: number;
  exit_time: number;
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  pnl_percent: number;
};

export type BacktestResult = {
  initial_balance: number;
  final_balance: number;
  total_return: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  profit_factor: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  max_drawdown: number;
  trades: BacktestTrade[];
  equity_curve: number[];
};

export type SyncState = {
  id: number;
  market_id: number | null;
  exchange: string;
  symbol: string;
  timeframe: string;
  sync_status: string;
  last_sync_time: string | null;
  backfill_completed_until: string | null;
  is_auto_syncing: boolean;
  error_message: string | null;
  last_error_time: string | null;
  created_at: string;
  updated_at: string;
};

export type AutoSyncResponse = {
  updated: number;
  message: string;
};

export type BackfillResponse = {
  task_id: string;
  status: string;
  estimated_markets: number;
  estimated_timeframes: number;
  message: string;
};

export type BackfillTaskStatus = {
  task_id: string;
  status: string;
  total_combinations: number;
  completed_combinations: number;
  failed_combinations: number;
  started_at: string | null;
  completed_at: string | null;
  error: string | null;
};

export type SchedulerJob = {
  id: string;
  name: string;
  next_run_time: string | null;
  last_run_time: string | null;
  stats: Record<string, unknown>;
};

export type SchedulerStatus = {
  running: boolean;
  job_store: string;
  jobs: SchedulerJob[];
  active_connections: number;
};
