import axios from 'axios';

import { useAuthStore } from '@/lib/auth-store';
import type {
  AutoSyncResponse,
  BackfillResponse,
  BackfillTaskStatus,
  AuthToken,
  BacktestResult,
  Market,
  OHLCV,
  OhlcvTuple,
  SchedulerStatus,
  SyncState,
  User,
} from '@/lib/types';

type ApiResult<T> = Promise<{ data: T }>;

type LoginPayload = {
  username: string;
  password: string;
};

type RegisterPayload = {
  username: string;
  email: string;
  password: string;
};

type MarketListParams = {
  exchange?: string;
  symbol?: string;
  active?: boolean;
  limit?: number;
  offset?: number;
};

type BacktestRunPayload = {
  market_id: number;
  symbol?: string;
  strategy: string;
  start_date: string;
  end_date: string;
  initial_balance: number;
  timeframe: string;
  params?: {
    fast_period?: number;
    slow_period?: number;
    rsi_period?: number;
    rsi_oversold?: number;
    rsi_overbought?: number;
  };
};

type OhlcvQuery = {
  market_id: number;
  timeframe: string;
  start_time: string | number | Date;
  end_time?: string | number | Date;
  limit?: number;
  order?: 'asc' | 'desc';
};

type BackfillPayload = {
  market_ids?: number[];
  timeframes: string[];
  start_time?: string | number | Date;
  end_time?: string | number | Date;
  symbol_pattern?: string;
  force?: boolean;
};

function trimTrailingSlash(value: string) {
  return value.replace(/\/+$/, '');
}

function resolveApiBaseUrl() {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;
  if (configuredBaseUrl) {
    const normalized = trimTrailingSlash(configuredBaseUrl);
    return normalized.endsWith('/api/v1') ? normalized : `${normalized}/api/v1`;
  }

  return 'http://localhost:8000/api/v1';
}

function resolveWsBaseUrl() {
  const configuredWsUrl = process.env.NEXT_PUBLIC_WS_BASE_URL;
  if (configuredWsUrl) {
    return trimTrailingSlash(configuredWsUrl);
  }

  return resolveApiBaseUrl()
    .replace(/\/api\/v1$/, '')
    .replace(/^http:\/\//, 'ws://')
    .replace(/^https:\/\//, 'wss://');
}

function toIsoString(value: string | number | Date | undefined) {
  if (value === undefined) {
    return undefined;
  }

  if (value instanceof Date) {
    return value.toISOString();
  }

  if (typeof value === 'number') {
    return new Date(value).toISOString();
  }

  return value;
}

export function normalizeOhlcvTuple(tuple: OhlcvTuple): OHLCV {
  const [time, open, high, low, close, volume] = tuple;
  return { time, open, high, low, close, volume };
}

const apiClient = axios.create({
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.request.use((config) => {
  config.baseURL = resolveApiBaseUrl();

  const token =
    useAuthStore.getState().token ??
    (typeof window !== 'undefined' ? window.localStorage.getItem('token') : null);

  if (token) {
    config.headers = config.headers ?? {};
    config.headers.Authorization = `Bearer ${token}`;
  }

  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (axios.isAxiosError(error) && error.response?.status === 401 && typeof window !== 'undefined') {
      useAuthStore.getState().logout();

      if (!window.location.pathname.startsWith('/login') && !window.location.pathname.startsWith('/register')) {
        window.location.href = '/login';
      }
    }

    return Promise.reject(error);
  },
);

export const authApi = {
  async register(payload: RegisterPayload): ApiResult<User> {
    const response = await apiClient.post<User>('/auth/register', payload);
    return { data: response.data };
  },

  async login(payload: LoginPayload): ApiResult<AuthToken> {
    const response = await apiClient.post<AuthToken>('/auth/login', payload);
    return { data: response.data };
  },

  async me(): ApiResult<User> {
    const response = await apiClient.get<User>('/auth/me');
    return { data: response.data };
  },
};

export const marketsApi = {
  async list(params: MarketListParams = {}): ApiResult<{ items: Market[] }> {
    const response = await apiClient.get<Market[]>('/markets', { params });
    return { data: { items: response.data } };
  },

  async sync(filters?: { exchanges?: string[] }): ApiResult<{ synced: number; message: string }> {
    const response = await apiClient.post<{ synced: number }>('/markets/sync', filters ?? {});
    return {
      data: {
        synced: response.data.synced,
        message: `Synced ${response.data.synced} markets`,
      },
    };
  },
};

export const backtestApi = {
  async run(payload: BacktestRunPayload): ApiResult<BacktestResult> {
    const response = await apiClient.post<BacktestResult>('/backtest/run', {
      market_id: payload.market_id,
      symbol: payload.symbol,
      strategy: payload.strategy,
      start_date: payload.start_date,
      end_date: payload.end_date,
      initial_balance: payload.initial_balance,
      timeframe: payload.timeframe,
      ...payload.params,
    });

    return { data: response.data };
  },
};

export const dataApi = {
  async getOHLCV(params: OhlcvQuery): ApiResult<OHLCV[]> {
    const response = await apiClient.get<OhlcvTuple[]>('/data/ohlcv', {
      params: {
        ...params,
        start_time: toIsoString(params.start_time),
        end_time: toIsoString(params.end_time),
      },
    });

    return { data: response.data.map(normalizeOhlcvTuple) };
  },

  async getSyncStates(params: Record<string, unknown> = {}): ApiResult<{ items: SyncState[]; total: number }> {
    const response = await apiClient.get<{ items: SyncState[]; total: number }>('/data/sync_state', {
      params,
    });
    return { data: response.data };
  },

  async setAutoSync(payload: {
    market_id: number;
    timeframes: string[];
    enabled: boolean;
  }): ApiResult<AutoSyncResponse> {
    const response = await apiClient.post<AutoSyncResponse>('/data/auto_sync', payload);
    return { data: response.data };
  },

  async startBackfill(payload: BackfillPayload): ApiResult<BackfillResponse> {
    const response = await apiClient.post<BackfillResponse>('/data/backfill', {
      ...payload,
      start_time: toIsoString(payload.start_time),
      end_time: toIsoString(payload.end_time),
    });
    return { data: response.data };
  },

  async getBackfillStatus(taskId: string): ApiResult<BackfillTaskStatus> {
    const response = await apiClient.get<BackfillTaskStatus>(`/data/backfill/${taskId}`);
    return { data: response.data };
  },
};

export const schedulerApi = {
  async getStatus(): ApiResult<SchedulerStatus> {
    const response = await apiClient.get<SchedulerStatus>('/scheduler/status');

    return { data: response.data };
  },
};

export function getWSUrl(path: string) {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${resolveWsBaseUrl()}${normalizedPath}`;
}
