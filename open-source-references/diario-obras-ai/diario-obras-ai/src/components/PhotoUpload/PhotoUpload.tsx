import React from 'react';
import { useDropzone } from 'react-dropzone';

interface PhotoUploadProps {
  onDrop: (files: File[]) => void;
  isUploading?: boolean;
  uploadProgress?: number;
  className?: string;
}

export const PhotoUpload: React.FC<PhotoUploadProps> = ({
  onDrop,
  isUploading = false,
  uploadProgress = 0,
  className = '',
}) => {
  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      'image/*': ['.png', '.jpg', '.jpeg', '.webp'],
    },
    multiple: true,
    disabled: isUploading,
  });

  return (
    <div
      {...getRootProps()}
      className={`
        border-2 border-dashed rounded-xl p-12 text-center transition-all
        ${isDragActive ? 'border-accent bg-accent/10' : 'border-primary-dark hover:border-accent'}
        ${isUploading ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}
        ${className}
      `}
    >
      <input {...getInputProps()} />

      {isUploading ? (
        <div>
          <div className="w-16 h-16 mx-auto mb-4 border-4 border-accent border-t-transparent rounded-full animate-spin"></div>
          <p className="text-lg font-medium text-primary">Carregando...</p>
          <p className="text-sm text-primary-light mt-2">{uploadProgress.toFixed(0)}%</p>
        </div>
      ) : (
        <div>
          <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-secondary-light flex items-center justify-center">
            <svg
              className="w-8 h-8 text-white"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
              />
            </svg>
          </div>
          <p className="text-lg font-medium text-primary">
            {isDragActive ? 'Solte as fotos aqui' : 'Arraste fotos aqui ou clique para selecionar'}
          </p>
          <p className="text-sm text-primary-light mt-2">PNG, JPG, WEBP (máx. 10MB cada)</p>
        </div>
      )}
    </div>
  );
};
