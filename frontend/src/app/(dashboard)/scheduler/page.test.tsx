import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import SchedulerPage from '@/app/(dashboard)/scheduler/page';

const { getStatusMock, toastErrorMock } = vi.hoisted(() => ({
  getStatusMock: vi.fn(),
  toastErrorMock: vi.fn(),
}));

vi.mock('@/lib/api', () => ({
  schedulerApi: {
    getStatus: getStatusMock,
  },
}));

vi.mock('sonner', () => ({
  toast: {
    error: toastErrorMock,
  },
}));

describe('SchedulerPage', () => {
  beforeEach(() => {
    getStatusMock.mockResolvedValue({
      data: {
        running: true,
        job_store: 'redis',
        active_connections: 3,
        jobs: [
          {
            id: 'sync_markets_metadata',
            name: 'Sync Markets Metadata',
            next_run_time: '2026-03-13T13:00:00Z',
            last_run_time: '2026-03-13T12:00:00Z',
            stats: {
              total_runs: 5,
              successful_runs: 4,
              failed_runs: 1,
              total_synced: 120,
              last_error: null,
            },
          },
        ],
      },
    });
  });

  it('renders scheduler status and job statistics', async () => {
    render(<SchedulerPage />);

    expect(await screen.findByText('Sync Markets Metadata')).toBeInTheDocument();
    expect(screen.getByText('redis')).toBeInTheDocument();
    expect(screen.getByText('120')).toBeInTheDocument();
    expect(screen.getByText('sync_markets_metadata')).toBeInTheDocument();
  });

  it('auto-refreshes scheduler data on the polling interval', async () => {
    let intervalCallback: (() => void) | undefined;
    vi.spyOn(window, 'setInterval').mockImplementation((callback, delay) => {
      if (delay === 15000) {
        intervalCallback = callback as () => void;
      }
      return 1 as unknown as ReturnType<typeof setInterval>;
    });
    vi.spyOn(window, 'clearInterval').mockImplementation(() => undefined);

    render(<SchedulerPage />);

    expect(await screen.findByText('Sync Markets Metadata')).toBeInTheDocument();

    await waitFor(() => {
      expect(intervalCallback).toBeTypeOf('function');
    });

    await act(async () => {
      intervalCallback?.();
    });

    await waitFor(() => {
      expect(getStatusMock).toHaveBeenCalledTimes(2);
    });
  });

  it('shows an error toast when a manual refresh fails', async () => {
    getStatusMock.mockReset();
    getStatusMock
      .mockResolvedValueOnce({
        data: {
          running: true,
          job_store: 'redis',
          active_connections: 3,
          jobs: [
            {
              id: 'sync_markets_metadata',
              name: 'Sync Markets Metadata',
              next_run_time: '2026-03-13T13:00:00Z',
              last_run_time: '2026-03-13T12:00:00Z',
              stats: {
                total_runs: 5,
                successful_runs: 4,
                failed_runs: 1,
                total_synced: 120,
                last_error: null,
              },
            },
          ],
        },
      })
      .mockRejectedValueOnce(new Error('boom'));

    render(<SchedulerPage />);

    expect(await screen.findByText('Sync Markets Metadata')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /refresh/i }));

    await waitFor(() => {
      expect(toastErrorMock).toHaveBeenCalledWith('Failed to load scheduler status');
    });
  });
});
