import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import MarketsPage from '@/app/(dashboard)/markets/page';

const { pushMock, listMock, syncMock, toastSuccessMock, toastErrorMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  listMock: vi.fn(),
  syncMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock('@/lib/api', () => ({
  marketsApi: {
    list: listMock,
    sync: syncMock,
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: toastSuccessMock,
    error: toastErrorMock,
  },
}));

describe('MarketsPage', () => {
  beforeEach(() => {
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
    syncMock.mockResolvedValue({
      data: {
        synced: 1,
        message: 'Synced 1 markets',
      },
    });
  });

  it('loads markets and sends the default exchange list to sync', async () => {
    render(<MarketsPage />);

    const marketLabels = await screen.findAllByText('BTC/USDT');
    expect(marketLabels).toHaveLength(2);

    await userEvent.click(screen.getByRole('button', { name: /sync/i }));

    await waitFor(() => {
      expect(syncMock).toHaveBeenCalledWith({
        exchanges: ['binance', 'bybit', 'okx', 'coinbase'],
      });
    });

    expect(toastSuccessMock).toHaveBeenCalledWith('Synced 1 markets');
    expect(listMock).toHaveBeenCalledTimes(2);
  });
});
