import { useState } from 'react';
import { usePhotoUpload } from './hooks/usePhotoUpload';
import { AudioRecording, useAudioRecorder } from './hooks/useAudioRecorder';
import { Sidebar } from './components/Sidebar/Sidebar';
import { PhotoUpload } from './components/PhotoUpload/PhotoUpload';
import { PhotoGrid } from './components/PhotoGrid/PhotoGrid';
import { AudioRecorder } from './components/AudioRecorder/AudioRecorder';
import { ReportPreview } from './components';

// n8n webhook base URL (from environment or default to localhost)
const N8N_BASE_URL = import.meta.env.VITE_N8N_URL || 'http://localhost:5678';

// Mock API base URL (still used for DOCX generation)
const API_BASE_URL = 'http://localhost:8000';

// Helper function to convert Blob/File to base64
const blobToBase64 = (blob: Blob): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(blob);
  });
};

function NewDiary() {
  const {
    photos,
    isUploading: isPhotoUploading,
    uploadProgress,
    addPhotos,
    removePhoto,
    clearPhotos,
    reorderPhotos,
  } = usePhotoUpload();

  const [projectName, setProjectName] = useState('');
  const [projectLocation, setProjectLocation] = useState('');
  const [contractor, setContractor] = useState('');
  const [supervisor, setSupervisor] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [showPreview, setShowPreview] = useState(false);

  const { recordings } = useAudioRecorder();

  const [selectedAudio, setSelectedAudio] = useState<AudioRecording | null>(null);
  const [audioTranscription, setAudioTranscription] = useState<string | null>(null);

  const handleGenerateReport = async () => {
    try {
      setIsGenerating(true);

      // Classificar fotos usando n8n webhook
      const classifyResponse = await fetch(`${N8N_BASE_URL}/webhook/classify-photos`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          photo_ids: photos.map(p => p.id),
        }),
      });

      if (!classifyResponse.ok) {
        throw new Error(`Erro ao classificar fotos: ${classifyResponse.statusText}`);
      }

      const classificationsResult = await classifyResponse.json();
      const classifications = classificationsResult.classifications || classificationsResult;

      // Transcrever áudio se selecionado usando n8n webhook
      let transcription = null;
      if (selectedAudio) {
        // Convert audio blob to base64
        const audioBase64 = await blobToBase64(selectedAudio.blob);

        const transcribeResponse = await fetch(`${N8N_BASE_URL}/webhook/transcribe-audio`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            audio_id: selectedAudio.id,
            audio_base64: audioBase64,
          }),
        });

        if (!transcribeResponse.ok) {
          throw new Error(`Erro ao transcrever áudio: ${transcribeResponse.statusText}`);
        }

        const transcriptionResult = await transcribeResponse.json();
        transcription = transcriptionResult.transcription;
        setAudioTranscription(transcription);
      }

      // Gerar diário
      const generateResponse = await fetch(`${API_BASE_URL}/api/diario/gerar`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          project_name: projectName || 'Projeto Sem Nome',
          project_location: projectLocation || 'Local não informado',
          contractor: contractor || undefined,
          supervisor: supervisor || undefined,
          photos: classifications,
          audio_transcription: transcription,
        }),
      });

      if (!generateResponse.ok) {
        throw new Error('Erro ao gerar diário');
      }

      const result = await generateResponse.json();

      // Download do diário
      if (result.download_url) {
        window.open(result.download_url, '_blank');
      }
    } catch (error) {
      console.error('Erro ao gerar diário:', error);
      alert('Erro ao gerar diário. Verifique o console para detalhes.');
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <div className="flex min-h-screen">
        {/* Sidebar */}
        <Sidebar />

        {/* Main Content */}
        <main className="flex-1 overflow-auto">
          <div className="container mx-auto px-6 py-8">
            {/* Header */}
            <div className="mb-8">
              <h1 className="text-3xl font-bold text-primary-dark mb-2">
                Novo Diário de Obra
              </h1>
              <p className="text-primary">
                Carregue as fotos, grave áudio explicativo e organize a sequência do relatório
              </p>
            </div>

            {/* Formulário do Projeto */}
            <div className="bg-white rounded-lg shadow-md p-6 mb-8">
              <h2 className="text-xl font-semibold text-primary-dark mb-4">
                Informações do Projeto
              </h2>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">
                    Nome do Projeto *
                  </label>
                  <input
                    type="text"
                    value={projectName}
                    onChange={(e) => setProjectName(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder="Ex: Edifício Residencial A"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">
                    Local *
                  </label>
                  <input
                    type="text"
                    value={projectLocation}
                    onChange={(e) => setProjectLocation(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder="Ex: Rua Principal, 123"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">
                    Contratada
                  </label>
                  <input
                    type="text"
                    value={contractor}
                    onChange={(e) => setContractor(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder="Ex: Construtora XYZ"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-primary mb-2">
                    Responsável
                  </label>
                  <input
                    type="text"
                    value={supervisor}
                    onChange={(e) => setSupervisor(e.target.value)}
                    className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary"
                    placeholder="Ex: Eng. João Silva"
                  />
                </div>
              </div>
            </div>

            {/* Áudio Section */}
            <div className="mb-8">
              <AudioRecorder
                onRecordingComplete={(recording) => {
                  setSelectedAudio(recording);
                  console.log('Áudio selecionado:', recording);
                }}
              />
            </div>

            {/* Upload Area */}
            <div className="mb-8">
              <PhotoUpload
                onDrop={addPhotos}
                isUploading={isPhotoUploading}
                uploadProgress={uploadProgress}
              />
            </div>

            {/* Photo Grid with Drag & Drop */}
            {photos.length > 0 && (
              <>
                <div className="mb-8">
                  <div className="flex items-center justify-between mb-4">
                    <h2 className="text-xl font-semibold text-primary-dark">
                      Fotos Carregadas ({photos.length})
                    </h2>
                    <button
                      onClick={clearPhotos}
                      className="px-4 py-2 text-sm text-red-500 hover:text-red-600 transition-colors"
                    >
                      Limpar tudo
                    </button>
                  </div>
                  <PhotoGrid
                    photos={photos}
                    onRemove={removePhoto}
                    onReorder={(newPhotos) => {
                      // PhotoGrid already provides the reordered array
                      // We just need to find the indices that changed
                      const oldIndex = photos.findIndex((p, i) => p.id !== newPhotos[i]?.id);
                      const newIndex = newPhotos.findIndex((p, i) => p.id !== photos[i]?.id);
                      if (oldIndex !== -1 && newIndex !== -1) {
                        reorderPhotos(oldIndex, newIndex);
                      }
                    }}
                  />
                </div>

                {/* Generate Button */}
                <div className="flex flex-col-reverse sm:flex-row justify-between items-center gap-4">
                  <div className="text-sm text-primary-light">
                    {selectedAudio && (
                      <span>✓ {recordings.length} áudio(s) disponível(is)</span>
                    )}
                  </div>
                  <div className="flex flex-col-reverse sm:flex-row gap-3">
                    <button
                      onClick={() => setShowPreview(true)}
                      disabled={photos.length === 0 || !projectName || !projectLocation}
                      className="px-6 py-3 rounded-lg font-semibold text-white bg-accent hover:bg-accent-light transition-all disabled:bg-gray-400 disabled:cursor-not-allowed"
                    >
                      Prévia
                    </button>
                    <button
                      onClick={handleGenerateReport}
                      disabled={photos.length === 0 || isGenerating || !projectName || !projectLocation}
                      className="px-8 py-3 rounded-lg font-semibold text-white transition-all disabled:bg-gray-400 disabled:cursor-not-allowed hover:shadow-lg"
                    >
                      {isGenerating ? 'Gerando...' : 'Gerar Diário de Obra'}
                    </button>
                  </div>
                </div>
              </>
            )}
          </div>
        </main>
      </div>

      <ReportPreview
        isOpen={showPreview}
        onClose={() => setShowPreview(false)}
        onGenerate={handleGenerateReport}
        photos={photos}
        audioTranscription={audioTranscription}
        projectName={projectName || 'Projeto Sem Nome'}
        projectLocation={projectLocation || 'Local não informado'}
        contractor={contractor || undefined}
        supervisor={supervisor || undefined}
        isGenerating={isGenerating}
      />
    </div>
  );
}

export default NewDiary;
