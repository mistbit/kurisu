import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import ChartPage from '@/app/(dashboard)/chart/page';

const {
  searchParamValues,
  pushMock,
  backMock,
  getOHLCVMock,
  normalizeOhlcvTupleMock,
  websocketCloseMock,
} = vi.hoisted(() => ({
  searchParamValues: {} as Record<string, string | undefined>,
  pushMock: vi.fn(),
  backMock: vi.fn(),
  getOHLCVMock: vi.fn(),
  normalizeOhlcvTupleMock: vi.fn((tuple: [number, number, number, number, number, number]) => ({
    time: tuple[0],
    open: tuple[1],
    high: tuple[2],
    low: tuple[3],
    close: tuple[4],
    volume: tuple[5],
  })),
  websocketCloseMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => ({
    get: (key: string) => searchParamValues[key] ?? null,
  }),
  useRouter: () => ({
    push: pushMock,
    back: backMock,
  }),
}));

vi.mock('@/lib/api', () => ({
  dataApi: {
    getOHLCV: getOHLCVMock,
  },
  getWSUrl: (path: string) => `ws://example.test${path}`,
  normalizeOhlcvTuple: normalizeOhlcvTupleMock,
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }: { children?: unknown }) => (
    <div data-testid="responsive-container">{children}</div>
  ),
  ComposedChart: ({ children }: { children?: unknown }) => <div>{children}</div>,
  XAxis: () => null,
  YAxis: () => null,
  Tooltip: () => null,
  Area: () => null,
  Bar: () => null,
  CartesianGrid: () => null,
}));

describe('ChartPage', () => {
  beforeEach(() => {
    pushMock.mockReset();
    backMock.mockReset();
    getOHLCVMock.mockReset();
    normalizeOhlcvTupleMock.mockClear();
    websocketCloseMock.mockReset();

    for (const key of Object.keys(searchParamValues)) {
      delete searchParamValues[key];
    }

    searchParamValues.market_id = '99';
    searchParamValues.symbol = 'ETH/USDT';
    searchParamValues.exchange = 'binance';

    getOHLCVMock.mockResolvedValue({
      data: [
        {
          time: 1700000000000,
          open: 100,
          high: 102,
          low: 99,
          close: 101,
          volume: 1000,
        },
        {
          time: 1700003600000,
          open: 101,
          high: 104,
          low: 100,
          close: 103,
          volume: 1200,
        },
      ],
    });

    class MockWebSocket {
      onmessage: ((event: MessageEvent) => void) | null = null;

      constructor(public url: string) {}

      close() {
        websocketCloseMock(this.url);
      }
    }

    vi.stubGlobal('WebSocket', MockWebSocket as unknown as typeof WebSocket);
  });

  it('opens backtest with the current market and timeframe', async () => {
    render(<ChartPage />);

    expect(await screen.findByText('ETH/USDT')).toBeInTheDocument();

    await waitFor(() => {
      expect(getOHLCVMock).toHaveBeenCalledWith({
        market_id: 99,
        timeframe: '1h',
        start_time: expect.any(String),
        end_time: expect.any(String),
        limit: 500,
      });
    });

    await userEvent.click(screen.getByRole('button', { name: '4h' }));

    await waitFor(() => {
      expect(getOHLCVMock).toHaveBeenCalledWith({
        market_id: 99,
        timeframe: '4h',
        start_time: expect.any(String),
        end_time: expect.any(String),
        limit: 500,
      });
    });

    const [startDateInput, endDateInput] = screen.getAllByDisplayValue(/\d{4}-\d{2}-\d{2}/);

    await userEvent.click(screen.getByRole('button', { name: /backtest this market/i }));

    expect(pushMock).toHaveBeenCalledWith(
      `/backtest?market_id=99&timeframe=4h&symbol=ETH%2FUSDT&start_date=${encodeURIComponent(
        (startDateInput as HTMLInputElement).value,
      )}&end_date=${encodeURIComponent((endDateInput as HTMLInputElement).value)}`,
    );
  });

  it('uses timeframe and range from query params when opening chart from backtest', async () => {
    searchParamValues.timeframe = '4h';
    searchParamValues.start_time = '2026-03-01T00:00:00.000Z';
    searchParamValues.end_time = '2026-03-10T23:59:59.999Z';

    render(<ChartPage />);

    await waitFor(() => {
      expect(getOHLCVMock).toHaveBeenCalledWith({
        market_id: 99,
        timeframe: '4h',
        start_time: '2026-03-01T00:00:00.000Z',
        end_time: '2026-03-10T23:59:59.999Z',
        limit: 500,
      });
    });
  });

  it('refetches data when the date range is changed manually', async () => {
    render(<ChartPage />);

    const [startDateInput, endDateInput] = (await screen.findAllByDisplayValue(
      /\d{4}-\d{2}-\d{2}/,
    )) as HTMLInputElement[];

    fireEvent.change(startDateInput, { target: { value: '2026-03-02' } });
    fireEvent.change(endDateInput, { target: { value: '2026-03-08' } });

    await waitFor(() => {
      expect(getOHLCVMock).toHaveBeenLastCalledWith({
        market_id: 99,
        timeframe: '1h',
        start_time: '2026-03-02T00:00:00.000Z',
        end_time: '2026-03-08T23:59:59.999Z',
        limit: 500,
      });
    });
  });
});
