import React from 'react';
import { Mic, Square, Trash2 } from 'lucide-react';
import { useAudioRecorder, AudioRecording } from '../../hooks/useAudioRecorder';

interface AudioRecorderProps {
  onRecordingComplete?: (recording: AudioRecording) => void;
  className?: string;
}

export const AudioRecorder: React.FC<AudioRecorderProps> = ({
  onRecordingComplete,
  className = '',
}) => {
  const {
    isRecording,
    recordingTime,
    recordings,
    error,
    startRecording,
    stopRecording,
    removeRecording,
    clearRecordings,
  } = useAudioRecorder();

  return (
    <div className={`bg-white rounded-lg shadow-md p-6 ${className}`}>
      <h2 className="text-xl font-semibold text-primary-dark mb-4">
        Gravar Áudio de Explicação
      </h2>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-4">
          <p className="text-red-600 text-sm">{error}</p>
        </div>
      )}

      {/* Recording Controls */}
      <div className="flex items-center space-x-4 mb-6">
        {!isRecording ? (
          <button
            onClick={startRecording}
            className="flex items-center space-x-2 px-6 py-3 bg-accent hover:bg-accent-light text-white rounded-lg font-medium transition-colors"
          >
            <Mic size={20} />
            <span>Iniciar Gravação</span>
          </button>
        ) : (
          <button
            onClick={stopRecording}
            className="flex items-center space-x-2 px-6 py-3 bg-red-500 hover:bg-red-600 text-white rounded-lg font-medium transition-colors animate-pulse"
          >
            <Square size={20} />
            <span>Parar Gravação</span>
          </button>
        )}

        {isRecording && (
          <div className="flex items-center space-x-2">
            <div className="w-3 h-3 bg-red-500 rounded-full animate-pulse"></div>
            <span className="text-lg font-mono text-primary-dark">
              {recordingTime}
            </span>
          </div>
        )}
      </div>

      {/* Recordings List */}
      {recordings.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-primary-dark">
              Gravações Salvas ({recordings.length})
            </h3>
            <button
              onClick={clearRecordings}
              className="px-4 py-2 text-sm text-red-500 hover:text-red-600 transition-colors"
            >
              Limpar Todas
            </button>
          </div>

          <div className="space-y-3">
            {recordings.map((recording) => (
              <div
                key={recording.id}
                className="flex items-center justify-between bg-gray-50 rounded-lg p-4"
              >
                {/* Audio Player */}
                <div className="flex-1">
                  <audio
                    controls
                    src={recording.url}
                    className="w-full"
                  />
                  <div className="flex items-center space-x-4 mt-2 text-sm text-primary">
                    <span>
                      Duração: {recording.duration}s
                    </span>
                    <span>
                      Tamanho: {(recording.size / 1024).toFixed(1)} KB
                    </span>
                    <span>
                      {recording.createdAt.toLocaleString('pt-BR')}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <div className="flex items-center space-x-2 ml-4">
                  <button
                    onClick={() => onRecordingComplete?.(recording)}
                    className="px-4 py-2 bg-secondary text-white rounded-lg hover:bg-secondary-light transition-colors text-sm"
                  >
                    Usar no Relatório
                  </button>
                  <button
                    onClick={() => removeRecording(recording.id)}
                    className="p-2 text-red-500 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                    title="Remover gravação"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Instructions */}
      {recordings.length === 0 && (
        <div className="bg-gray-50 rounded-lg p-4">
          <p className="text-sm text-primary">
            <strong>Como usar:</strong>
          </p>
          <ol className="list-decimal list-inside text-sm text-primary mt-2 space-y-1">
            <li>Clique em "Iniciar Gravação" para gravar sua explicação</li>
            <li>Fale claramente descrevendo o que foi feito na obra</li>
            <li>Clique em "Parar Gravação" quando terminar</li>
            <li>Reproduza para verificar antes de usar no relatório</li>
            <li>Clique em "Usar no Relatório" para selecionar</li>
          </ol>
        </div>
      )}
    </div>
  );
};
