import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import BacktestPage from '@/app/(dashboard)/backtest/page';

const { listMock, runMock, toastSuccessMock, toastErrorMock, searchParamValues, pushMock } = vi.hoisted(() => ({
  listMock: vi.fn(),
  runMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
  searchParamValues: {} as Record<string, string | undefined>,
  pushMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => ({
    get: (key: string) => searchParamValues[key] ?? null,
  }),
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock('@/lib/api', () => ({
  marketsApi: {
    list: listMock,
  },
  backtestApi: {
    run: runMock,
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: toastSuccessMock,
    error: toastErrorMock,
  },
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children?: unknown }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  LineChart: ({ children }: { children?: unknown }) => <div>{children}</div>,
  Line: () => null,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  CartesianGrid: () => null,
}));

describe('BacktestPage', () => {
  beforeEach(() => {
    listMock.mockReset();
    runMock.mockReset();
    toastSuccessMock.mockReset();
    toastErrorMock.mockReset();
    pushMock.mockReset();
    for (const key of Object.keys(searchParamValues)) {
      delete searchParamValues[key];
    }

    listMock.mockResolvedValue({
      data: {
        items: [
          {
            id: 7,
            exchange: 'binance',
            symbol: 'BTC/USDT',
            base_asset: 'BTC',
            quote_asset: 'USDT',
            active: true,
            meta: {},
            exchange_symbol: 'BTCUSDT',
            price_precision: 2,
            amount_precision: 6,
          },
        ],
      },
    });

    runMock.mockResolvedValue({
      data: {
        initial_balance: 10000,
        final_balance: 10325.25,
        total_return: 3.25,
        total_trades: 1,
        winning_trades: 1,
        losing_trades: 0,
        win_rate: 100,
        profit_factor: 2.4,
        sharpe_ratio: 1.3,
        sortino_ratio: 1.7,
        max_drawdown: 4.5,
        trades: [
          {
            entry_time: 1700000000000,
            exit_time: 1700003600000,
            symbol: 'BTC/USDT',
            side: 'long',
            entry_price: 100,
            exit_price: 103.5,
            quantity: 1.2,
            pnl: 4.2,
            pnl_percent: 3.5,
          },
        ],
        equity_curve: [10000, 10125, 10325.25],
      },
    });
  });

  async function selectMarket(label: string) {
    await userEvent.click(screen.getByText('Select market'));
    await userEvent.click(await screen.findByText(label));
  }

  function toChartStartTime(value: string) {
    return new Date(`${value}T00:00:00.000Z`).toISOString();
  }

  function toChartEndTime(value: string) {
    return new Date(`${value}T23:59:59.999Z`).toISOString();
  }

  it('loads markets and renders results after a successful run', async () => {
    render(<BacktestPage />);

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledWith({ limit: 50 });
    });

    const [startDateInput, endDateInput] = screen.getAllByDisplayValue(/\d{4}-\d{2}-\d{2}/);

    await selectMarket('BTC/USDT (binance)');
    await userEvent.click(screen.getByRole('button', { name: /run backtest/i }));

    await waitFor(() => {
      expect(runMock).toHaveBeenCalledWith({
        market_id: 7,
        symbol: 'BTC/USDT',
        strategy: 'ma_crossover',
        start_date: (startDateInput as HTMLInputElement).value,
        end_date: (endDateInput as HTMLInputElement).value,
        initial_balance: 10000,
        timeframe: '1h',
        params: {
          fast_period: 10,
          slow_period: 20,
          rsi_period: 14,
        },
      });
    });

    expect(toastSuccessMock).toHaveBeenCalledWith('Backtest completed!');
    expect(await screen.findByText('$10325.25')).toBeInTheDocument();
    expect(screen.getByText('Trades (1)')).toBeInTheDocument();
    expect(screen.getByText('+3.25%')).toBeInTheDocument();
  });

  it('prefills market and timeframe from chart query params', async () => {
    searchParamValues.market_id = '7';
    searchParamValues.timeframe = '4h';
    searchParamValues.start_date = '2026-03-01';
    searchParamValues.end_date = '2026-03-10';

    render(<BacktestPage />);

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledWith({ limit: 50 });
    });

    expect(screen.getByDisplayValue('2026-03-01')).toBeInTheDocument();
    expect(screen.getByDisplayValue('2026-03-10')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /run backtest/i }));

    await waitFor(() => {
      expect(runMock).toHaveBeenCalledWith({
        market_id: 7,
        symbol: 'BTC/USDT',
        strategy: 'ma_crossover',
        start_date: '2026-03-01',
        end_date: '2026-03-10',
        initial_balance: 10000,
        timeframe: '4h',
        params: {
          fast_period: 10,
          slow_period: 20,
          rsi_period: 14,
        },
      });
    });
  });

  it('opens the matching chart view with market, timeframe, and date range', async () => {
    searchParamValues.market_id = '7';
    searchParamValues.timeframe = '4h';
    searchParamValues.start_date = '2026-03-01';
    searchParamValues.end_date = '2026-03-10';

    render(<BacktestPage />);

    await waitFor(() => {
      expect(listMock).toHaveBeenCalledWith({ limit: 50 });
    });

    await userEvent.click(screen.getByRole('button', { name: /open in chart/i }));

    expect(pushMock).toHaveBeenCalledWith(
      `/chart?market_id=7&symbol=BTC%2FUSDT&exchange=binance&timeframe=4h&start_time=${encodeURIComponent(
        toChartStartTime('2026-03-01'),
      )}&end_time=${encodeURIComponent(toChartEndTime('2026-03-10'))}`,
    );
  });

  it('shows a validation error when required fields are missing', async () => {
    render(<BacktestPage />);

    await waitFor(() => {
      expect(listMock).toHaveBeenCalled();
    });

    await userEvent.click(screen.getByRole('button', { name: /run backtest/i }));

    expect(runMock).not.toHaveBeenCalled();
    expect(toastErrorMock).toHaveBeenCalledWith('Please fill in all required fields');
  });

  it('shows the backend error message when a backtest run fails', async () => {
    runMock.mockRejectedValue({
      response: {
        data: {
          detail: 'No data available for the specified period',
        },
      },
    });

    render(<BacktestPage />);

    await waitFor(() => {
      expect(listMock).toHaveBeenCalled();
    });

    await selectMarket('BTC/USDT (binance)');
    await userEvent.click(screen.getByRole('button', { name: /run backtest/i }));

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith('No data available for the specified period');
    });
  });
});
