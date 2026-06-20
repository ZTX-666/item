import React, { useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { Upload } from 'lucide-react';

export interface AudioFile {
  id: string;
  file: File;
  url: string;
}

interface AudioUploadProps {
  onFilesSelected: (files: AudioFile[]) => void;
  maxFiles?: number;
  maxSizeMB?: number;
  className?: string;
}

export const AudioUpload: React.FC<AudioUploadProps> = ({
  onFilesSelected,
  maxFiles = 5,
  maxSizeMB = 50,
  className = '',
}) => {
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadingFiles, setUploadingFiles] = useState<Set<string>>(new Set());

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: async (acceptedFiles: File[]) => {
      const validFiles = acceptedFiles.filter(file => {
        // Validar tipo
        if (!file.type.startsWith('audio/')) {
          return false;
        }
        // Validar tamanho
        if (file.size > maxSizeMB * 1024 * 1024) {
          return false;
        }
        return true;
      });

      const audioFiles: AudioFile[] = [];

      for (let i = 0; i < validFiles.length; i++) {
        const file = validFiles[i];
        const fileId = `audio_${Date.now()}_${i}`;
        setUploadingFiles(prev => new Set([...prev, fileId]));

        // Criar URL preview
        const url = URL.createObjectURL(file);

        // Simular progresso
        for (let progress = 0; progress <= 100; progress += 10) {
          await new Promise(resolve => setTimeout(resolve, 50));
          setUploadProgress(progress);
        }

        audioFiles.push({
          id: fileId,
          file,
          url,
        });

        setUploadingFiles(prev => {
          const next = new Set(prev);
          next.delete(fileId);
          return next;
        });
      }

      onFilesSelected(audioFiles);
      setUploadProgress(0);
    },
    accept: {
      'audio/*': ['.mp3', '.m4a', '.wav', '.webm', '.ogg'],
    },
    multiple: true,
    maxFiles,
  });

  return (
    <div
      {...getRootProps()}
      className={`
        border-2 border-dashed rounded-xl p-8 text-center transition-all
        ${isDragActive ? 'border-accent bg-accent/10' : 'border-primary-dark hover:border-accent'}
        ${className}
      `}
    >
      <input {...getInputProps()} />

      <div className="flex flex-col items-center">
        <div className="w-16 h-16 mb-4 rounded-full bg-secondary-light flex items-center justify-center">
          <Upload className="w-8 h-8 text-white" />
        </div>
        <p className="text-lg font-medium text-primary mb-2">
          {isDragActive ? 'Solte os arquivos de áudio aqui' : 'Arraste áudios ou clique para selecionar'}
        </p>
        <p className="text-sm text-primary-light mb-4">
          MP3, M4A, WAV, WEBM, OGG (máx. {maxSizeMB}MB cada, {maxFiles} arquivos)
        </p>

        {/* Upload Progress */}
        {uploadingFiles.size > 0 && (
          <div className="w-full max-w-md mx-auto">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-primary">
                Carregando {uploadingFiles.size} arquivo(s)...
              </span>
              <span className="text-sm font-medium text-primary-dark">
                {uploadProgress}%
              </span>
            </div>
            <div className="w-full bg-gray-200 rounded-full h-2 overflow-hidden">
              <div
                className="bg-secondary transition-all duration-300 h-full"
                style={{ width: `${uploadProgress}%` }}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
