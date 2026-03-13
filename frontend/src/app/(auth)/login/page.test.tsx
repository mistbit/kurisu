import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import LoginPage from '@/app/(auth)/login/page';

const { pushMock, setTokenMock, setUserMock, loginMock, meMock, toastSuccessMock, toastErrorMock } =
  vi.hoisted(() => ({
    pushMock: vi.fn(),
    setTokenMock: vi.fn(),
    setUserMock: vi.fn(),
    loginMock: vi.fn(),
    meMock: vi.fn(),
    toastSuccessMock: vi.fn(),
    toastErrorMock: vi.fn(),
  }));

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    push: pushMock,
  }),
}));

vi.mock('@/lib/auth-store', () => ({
  useAuthStore: () => ({
    setToken: setTokenMock,
    setUser: setUserMock,
  }),
}));

vi.mock('@/lib/api', () => ({
  authApi: {
    login: loginMock,
    me: meMock,
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: toastSuccessMock,
    error: toastErrorMock,
  },
}));

describe('LoginPage', () => {
  beforeEach(() => {
    loginMock.mockResolvedValue({
      data: {
        access_token: 'test-token',
        token_type: 'bearer',
        expires_in: 1800,
      },
    });
    meMock.mockResolvedValue({
      data: {
        id: 1,
        username: 'alice',
        email: 'alice@example.com',
        is_active: true,
        is_superuser: false,
        created_at: '2026-03-13T00:00:00Z',
      },
    });
  });

  it('submits credentials and redirects on success', async () => {
    render(<LoginPage />);

    await userEvent.type(screen.getByLabelText(/username/i), 'alice');
    await userEvent.type(screen.getByLabelText(/password/i), 'hunter2');
    await userEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith({
        username: 'alice',
        password: 'hunter2',
      });
    });

    expect(setTokenMock).toHaveBeenCalledWith('test-token');
    expect(meMock).toHaveBeenCalledTimes(1);
    expect(setUserMock).toHaveBeenCalledWith(
      expect.objectContaining({
        username: 'alice',
        email: 'alice@example.com',
      }),
    );
    expect(toastSuccessMock).toHaveBeenCalledWith('Login successful');
    expect(pushMock).toHaveBeenCalledWith('/markets');
  });
});
