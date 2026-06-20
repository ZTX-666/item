export interface PaginationParams {
  page: number;
  perPage: number;
}

export interface PaginatedResult<T> {
  data: T[];
  pagination: {
    page: number;
    per_page: number;
    total: number;
    total_pages: number;
  };
}

export function normalizePagination(page?: number, perPage?: number): PaginationParams {
  return {
    page: Math.max(1, page ?? 1),
    perPage: Math.min(50, Math.max(1, perPage ?? 20)),
  };
}

export function paginatedResponse<T>(
  data: T[],
  total: number,
  params: PaginationParams,
): PaginatedResult<T> {
  return {
    data,
    pagination: {
      page: params.page,
      per_page: params.perPage,
      total,
      total_pages: Math.ceil(total / params.perPage),
    },
  };
}
