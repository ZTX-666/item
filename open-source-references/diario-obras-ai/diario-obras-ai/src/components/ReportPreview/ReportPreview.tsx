import React, { useEffect, useRef, useState } from 'react';
import { X, ArrowLeft, Download, Loader2 } from 'lucide-react';
import { Photo } from '../../types';

interface ReportPreviewProps {
  isOpen: boolean;
  onClose: () => void;
  onGenerate: () => void;
  photos: Photo[];
  audioTranscription: string | null;
  projectName: string;
  projectLocation: string;
  contractor?: string;
  supervisor?: string;
  isGenerating?: boolean;
  onProjectNameChange?: (name: string) => void;
}

export const ReportPreview: React.FC<ReportPreviewProps> = ({
  isOpen,
  onClose,
  onGenerate,
  photos,
  audioTranscription,
  projectName,
  projectLocation,
  contractor,
  supervisor,
  isGenerating = false,
  onProjectNameChange,
}) => {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<HTMLElement>(null);
  const [localProjectName, setLocalProjectName] = useState(projectName);

  useEffect(() => {
    setLocalProjectName(projectName);
  }, [projectName]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;

    if (isOpen) {
      triggerRef.current = document.activeElement as HTMLElement;
      dialog.showModal();
      closeButtonRef.current?.focus();
      setLocalProjectName(projectName);
    } else {
      dialog.close();
      triggerRef.current?.focus();
    }
  }, [isOpen, projectName]);

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog || !isOpen) return;

    const handleKeyDown = (e: Event) => {
      const keyboardEvent = e as KeyboardEvent;
      if (keyboardEvent.key === 'Escape') {
        keyboardEvent.preventDefault();
        onClose();
      }
    };

    const handleFocusTrap = (e: Event) => {
      const keyboardEvent = e as KeyboardEvent;
      if (keyboardEvent.key !== 'Tab') return;

      const focusableElements = dialog.querySelectorAll(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      const firstElement = focusableElements[0] as HTMLElement;
      const lastElement = focusableElements[focusableElements.length - 1] as HTMLElement;

      if (keyboardEvent.shiftKey) {
        if (document.activeElement === firstElement) {
          keyboardEvent.preventDefault();
          lastElement?.focus();
        }
      } else {
        if (document.activeElement === lastElement) {
          keyboardEvent.preventDefault();
          firstElement?.focus();
        }
      }
    };

    dialog.addEventListener('keydown', handleKeyDown);
    dialog.addEventListener('keydown', handleFocusTrap);

    return () => {
      dialog.removeEventListener('keydown', handleKeyDown);
      dialog.removeEventListener('keydown', handleFocusTrap);
    };
  }, [isOpen, onClose]);

  const handleBackdropClick = (e: React.MouseEvent<HTMLDialogElement>) => {
    if (e.target === dialogRef.current) {
      onClose();
    }
  };

  const handleProjectNameChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setLocalProjectName(e.target.value);
    onProjectNameChange?.(e.target.value);
  };

  if (!isOpen) {
    return null;
  }

  return (
    <dialog
      ref={dialogRef}
      className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm transition-opacity duration-300 ease-in-out"
      onClick={handleBackdropClick}
      aria-modal="true"
      aria-labelledby="preview-title"
    >
      <div
        onClick={(e) => e.stopPropagation()}
        className="relative w-full max-w-5xl max-h-[90vh] overflow-auto bg-white rounded-xl shadow-2xl flex flex-col"
        role="document"
      >
        <button
          ref={closeButtonRef}
          onClick={onClose}
          className="absolute top-4 right-4 z-10 p-2 bg-gray-100 hover:bg-gray-200 text-gray-600 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-gray-500"
          aria-label="Fechar prévia"
        >
          <X size={24} />
        </button>

        <header className="sticky top-0 z-10 bg-white border-b border-gray-200 px-6 py-4">
          <h2 id="preview-title" className="text-2xl font-bold text-gray-900">
            Prévia do Relatório de Obra
          </h2>
        </header>

        <div className="p-6 flex-1 overflow-auto space-y-6">
          <section>
            <label htmlFor="project-name-input" className="block text-sm font-medium text-gray-700 mb-2">
              Nome do Projeto
            </label>
            <input
              id="project-name-input"
              type="text"
              value={localProjectName}
              onChange={handleProjectNameChange}
              className="w-full px-4 py-3 text-lg border border-gray-300 rounded-lg focus:ring-2 focus:ring-green-600 focus:border-transparent outline-none transition-shadow duration-200"
              aria-label="Nome do projeto editável"
            />
          </section>

          <section className="bg-gray-50 rounded-lg p-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <p className="text-sm font-semibold text-gray-700 mb-1">Local</p>
                <p className="text-lg font-medium text-gray-900">{projectLocation}</p>
              </div>
              {contractor && (
                <div>
                  <p className="text-sm font-semibold text-gray-700 mb-1">Contratada</p>
                  <p className="text-lg font-medium text-gray-900">{contractor}</p>
                </div>
              )}
              {supervisor && (
                <div>
                  <p className="text-sm font-semibold text-gray-700 mb-1">Responsável</p>
                  <p className="text-lg font-medium text-gray-900">{supervisor}</p>
                </div>
              )}
            </div>
          </section>

          <section>
            <h3 className="text-lg font-semibold text-gray-900 mb-3 flex items-center gap-2">
              <Download size={20} className="text-green-600" />
              Fotos ({photos.length})
            </h3>
            {photos.length > 0 ? (
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
                {photos.map((photo) => (
                  <div
                    key={photo.id}
                    className="bg-gray-100 rounded-lg overflow-hidden"
                    role="img"
                    aria-label={`Foto: ${photo.name}`}
                  >
                    <img
                      src={photo.preview}
                      alt={photo.name}
                      className="w-full h-48 object-cover"
                      loading="lazy"
                    />
                    <div className="p-2 bg-white">
                      <p className="text-sm font-medium text-gray-900 truncate">
                        {photo.name}
                      </p>
                      <p className="text-xs text-gray-600">
                        {(photo.size / 1024).toFixed(1)} KB
                      </p>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 bg-gray-50 rounded-lg">
                <p className="text-gray-500">Nenhuma foto adicionada</p>
              </div>
            )}
          </section>

          {audioTranscription && (
            <section>
              <h3 className="text-lg font-semibold text-gray-900 mb-3">
                Transcrição de Áudio
              </h3>
              <div className="bg-amber-50 border border-amber-200 rounded-lg p-4">
                <p className="text-gray-700 whitespace-pre-wrap leading-relaxed">
                  {audioTranscription}
                </p>
              </div>
            </section>
          )}
        </div>

        <footer className="sticky bottom-0 bg-white border-t border-gray-200 px-6 py-4">
          <div className="flex flex-col-reverse sm:flex-row justify-between items-center gap-4">
            <button
              onClick={onClose}
              disabled={isGenerating}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-6 py-3 border-2 border-gray-300 text-gray-700 rounded-lg font-semibold hover:bg-gray-50 transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-gray-500 focus:ring-offset-2"
              aria-label="Voltar para edição"
              type="button"
            >
              <ArrowLeft size={20} />
              <span>Voltar</span>
            </button>

            <button
              onClick={onGenerate}
              disabled={photos.length === 0 || isGenerating}
              className="w-full sm:w-auto flex items-center justify-center gap-2 px-8 py-3 bg-green-600 hover:bg-green-700 text-white rounded-lg font-semibold transition-all hover:shadow-lg disabled:bg-gray-400 disabled:cursor-not-allowed disabled:shadow-none focus:outline-none focus:ring-2 focus:ring-green-500 focus:ring-offset-2"
              aria-label={isGenerating ? 'Gerando relatório...' : 'Gerar relatório de obra'}
              type="button"
            >
              {isGenerating ? (
                <>
                  <Loader2 size={20} className="animate-spin" />
                  <span>Gerando...</span>
                </>
              ) : (
                <>
                  <Download size={20} />
                  <span>GERAR RELATÓRIO</span>
                </>
              )}
            </button>
          </div>
        </footer>
      </div>
    </dialog>
  );
};
