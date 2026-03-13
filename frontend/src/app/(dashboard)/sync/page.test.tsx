import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SyncPage from '@/app/(dashboard)/sync/page';

const {
  getSyncStatesMock,
  startBackfillMock,
  getBackfillStatusMock,
  setAutoSyncMock,
  toastSuccessMock,
  toastErrorMock,
} = vi.hoisted(() => ({
  getSyncStatesMock: vi.fn(),
  startBackfillMock: vi.fn(),
  getBackfillStatusMock: vi.fn(),
  setAutoSyncMock: vi.fn(),
  toastSuccessMock: vi.fn(),
  toastErrorMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  dataApi: {
    getSyncStates: getSyncStatesMock,
    startBackfill: startBackfillMock,
    getBackfillStatus: getBackfillStatusMock,
    setAutoSync: setAutoSyncMock,
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: toastSuccessMock,
    error: toastErrorMock,
  },
}));

describe('SyncPage', () => {
  beforeEach(() => {
    getSyncStatesMock.mockResolvedValue({
      data: {
        items: [
          {
            id: 11,
            market_id: 99,
            exchange: 'binance',
            symbol: 'ETH/USDT',
            timeframe: '1h',
            sync_status: 'idle',
            last_sync_time: '2026-03-13T00:00:00Z',
            backfill_completed_until: null,
            is_auto_syncing: false,
            error_message: null,
            last_error_time: null,
            created_at: '2026-03-13T00:00:00Z',
            updated_at: '2026-03-13T00:00:00Z',
          },
        ],
        total: 1,
      },
    });
    startBackfillMock.mockResolvedValue({
      data: {
        task_id: 'backfill_20260313_120000',
        status: 'queued',
        estimated_markets: 1,
        estimated_timeframes: 1,
        message: 'Backfill task queued for 1 combinations',
      },
    });
    getBackfillStatusMock.mockResolvedValue({
      data: {
        task_id: 'backfill_20260313_120000',
        status: 'completed',
        total_combinations: 1,
        completed_combinations: 1,
        failed_combinations: 0,
        started_at: '2026-03-13T12:00:00Z',
        completed_at: '2026-03-13T12:00:01Z',
        error: null,
      },
    });
    setAutoSyncMock.mockResolvedValue({
      data: {
        updated: 1,
        message: 'Auto-sync enabled for 1 timeframes',
      },
    });
  });

  it('loads sync rows and starts a backfill task from the row action', async () => {
    render(<SyncPage />);

    expect(await screen.findByText('ETH/USDT')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /backfill/i }));

    await waitFor(() => {
      expect(startBackfillMock).toHaveBeenCalledWith({
        market_ids: [99],
        timeframes: ['1h'],
      });
    });

    expect(await screen.findByText('Latest Backfill Task')).toBeInTheDocument();
    expect(screen.getByText('backfill_20260313_120000')).toBeInTheDocument();
    expect(toastSuccessMock).toHaveBeenCalledWith('Backfill task queued for 1 combinations');
  });

  it('enables auto-sync from the row switch', async () => {
    getSyncStatesMock.mockReset();
    getSyncStatesMock
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 11,
              market_id: 99,
              exchange: 'binance',
              symbol: 'ETH/USDT',
              timeframe: '1h',
              sync_status: 'idle',
              last_sync_time: '2026-03-13T00:00:00Z',
              backfill_completed_until: null,
              is_auto_syncing: false,
              error_message: null,
              last_error_time: null,
              created_at: '2026-03-13T00:00:00Z',
              updated_at: '2026-03-13T00:00:00Z',
            },
          ],
          total: 1,
        },
      })
      .mockResolvedValueOnce({
        data: {
          items: [
            {
              id: 11,
              market_id: 99,
              exchange: 'binance',
              symbol: 'ETH/USDT',
              timeframe: '1h',
              sync_status: 'idle',
              last_sync_time: '2026-03-13T00:00:00Z',
              backfill_completed_until: null,
              is_auto_syncing: true,
              error_message: null,
              last_error_time: null,
              created_at: '2026-03-13T00:00:00Z',
              updated_at: '2026-03-13T00:00:00Z',
            },
          ],
          total: 1,
        },
      });

    render(<SyncPage />);

    const autoSyncSwitch = await screen.findByRole('switch');
    await userEvent.click(autoSyncSwitch);

    await waitFor(() => {
      expect(setAutoSyncMock).toHaveBeenCalledWith({
        market_id: 99,
        timeframes: ['1h'],
        enabled: true,
      });
    });

    expect(toastSuccessMock).toHaveBeenCalledWith('Auto-sync enabled for 1 timeframes');
    expect(await screen.findByText('On')).toBeInTheDocument();
  });

  it('polls backfill status until the task completes', async () => {
    const setIntervalSpy = vi.spyOn(window, 'setInterval').mockImplementation((callback) => {
      void Promise.resolve().then(async () => {
        if (typeof callback === 'function') {
          await callback();
        }
      });

      return 1 as unknown as ReturnType<typeof setInterval>;
    });
    vi.spyOn(window, 'clearInterval').mockImplementation(() => undefined);

    render(<SyncPage />);

    expect(await screen.findByText('ETH/USDT')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /backfill/i }));

    await waitFor(() => {
      expect(startBackfillMock).toHaveBeenCalledWith({
        market_ids: [99],
        timeframes: ['1h'],
      });
    });

    await waitFor(() => {
      expect(setIntervalSpy).toHaveBeenCalled();
    });

    expect(await screen.findByText('Latest Backfill Task')).toBeInTheDocument();

    await waitFor(() => {
      expect(getBackfillStatusMock).toHaveBeenCalledWith('backfill_20260313_120000');
    });

    expect(toastSuccessMock).toHaveBeenCalledWith(
      'Backfill task backfill_20260313_120000 completed',
    );
  });
});
