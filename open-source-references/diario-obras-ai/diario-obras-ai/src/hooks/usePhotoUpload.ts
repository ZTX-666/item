import { useState, useCallback } from 'react';
import { Photo } from '../types';

const API_BASE_URL = 'http://localhost:8000';

export const usePhotoUpload = () => {
  const [photos, setPhotos] = useState<Photo[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);

  const addPhotos = useCallback(async (files: File[]) => {
    setIsUploading(true);
    setUploadProgress(0);

    const newPhotos: Photo[] = [];

    for (let i = 0; i < files.length; i++) {
      const file = files[i];

      try {
        // Upload para backend
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`${API_BASE_URL}/api/fotos/upload`, {
          method: 'POST',
          body: formData,
        });

        if (!response.ok) {
          throw new Error('Erro ao fazer upload');
        }

        const uploadResponse = await response.json();

        // Create preview URL
        const preview = await new Promise<string>((resolve) => {
          const reader = new FileReader();
          reader.onloadend = () => resolve(reader.result as string);
          reader.readAsDataURL(file);
        });

        const photo: Photo = {
          id: uploadResponse.photo_id,
          url: uploadResponse.url,
          preview,
          name: file.name,
          size: file.size,
          type: file.type,
          lastModified: file.lastModified,
        };

        newPhotos.push(photo);
        setUploadProgress(((i + 1) / files.length) * 100);
      } catch (error) {
        console.error(`Erro ao upload ${file.name}:`, error);
      }
    }

    setPhotos(prev => [...prev, ...newPhotos]);
    setIsUploading(false);
    setUploadProgress(0);

    return newPhotos;
  }, []);

  const removePhoto = useCallback((photoId: string) => {
    setPhotos(prev => prev.filter(p => p.id !== photoId));
  }, []);

  const clearPhotos = useCallback(() => {
    setPhotos([]);
  }, []);

  const reorderPhotos = useCallback((fromIndex: number, toIndex: number) => {
    setPhotos(prev => {
      const result = [...prev];
      const [removed] = result.splice(fromIndex, 1);
      result.splice(toIndex, 0, removed);
      return result;
    });
  }, []);

  return {
    photos,
    isUploading,
    uploadProgress,
    addPhotos,
    removePhoto,
    clearPhotos,
    reorderPhotos,
  };
};
