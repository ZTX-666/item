interface OrderPhotosRequest {
  projectId?: string;
  photos: {
    id: string;
    order: number;
  }[];
}

export async function orderPhotos(data: OrderPhotosRequest): Promise<void> {
  try {
    const response = await fetch("/api/fotos/ordenar", {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    });

    if (!response.ok) {
      throw new Error(`Failed to order photos: ${response.statusText}`);
    }
  } catch (error) {
    console.error('Error ordering photos:', error);
    throw error;
  }
}
