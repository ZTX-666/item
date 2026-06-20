export interface LoginRequest {
    email: string;
    password: string;
}

export interface TokenResponse {
    access_token: string;
    token_type: string;
}

export interface MeResponse {
    id: string;
    username: string;
    email: string;
    roles: string[];
    scopes: string[];
}