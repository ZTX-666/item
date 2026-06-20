import { apiClient } from './client';
import type { LoginRequest, TokenResponse, MeResponse } from '@/types/auth';

export const authApi = {
    login: (data: LoginRequest) =>
  apiClient.postForm<TokenResponse>('/auth/login', {
    username: data.email,
    password: data.password,
  }),

    me: () =>
        apiClient.get<MeResponse>('/auth/me')
};