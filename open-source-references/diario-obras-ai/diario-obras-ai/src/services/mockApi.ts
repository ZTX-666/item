import { generateAndDownloadDocx, DiaryData } from './docxGenerator';
import { storageService } from './storageService';
import { Report } from '../types';

/**
 * Simula delay de rede (para UX realista)
 */
const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Classificações fake para fotos
 */
const photoClassifications = [
  'Fundação',
  'Estrutura',
  'Alvenaria',
  'Instalações Elétricas',
  'Instalações Hidráulicas',
  'Revestimento',
  'Pintura',
  'Acabamento',
  'Área Externa',
  'Segurança',
];

/**
 * Mock API Service - Simula backend sem servidor
 */
export const mockApi = {
  /**
   * POST /api/fotos/classificar
   * Simula classificação de fotos usando IA
   */
  async classificarFotos(photoIds: string[]): Promise<Array<{
    photo_id: string;
    classification: string;
    confidence: number;
  }>> {
    // Simular delay de processamento
    await delay(1500);

    return photoIds.map((id, index) => ({
      photo_id: id,
      classification: photoClassifications[index % photoClassifications.length],
      confidence: 0.85 + Math.random() * 0.15, // 85-100%
    }));
  },

  /**
   * POST /api/audio/transcrever
   * Simula transcrição de áudio usando STT
   */
  async transcreverAudio(audioId: string): Promise<{
    audio_id: string;
    transcription: string;
  }> {
    // Simular delay de processamento
    await delay(2000);

    // Transcrição fake (placeholder)
    const transcription = `Hoje realizamos os seguintes trabalhos na obra:

Concluímos a concretagem da laje do segundo pavimento. A equipe trabalhou das 7h às 17h com intervalo para almoço.

Foram utilizados aproximadamente 15m³ de concreto usinado, conforme especificado no projeto estrutural.

Identificamos uma pequena irregularidade no prumo de uma das paredes do primeiro pavimento, que será corrigida antes do início do revestimento.

A previsão é de que na próxima semana possamos iniciar a alvenaria do terceiro pavimento.

O clima permaneceu favorável durante todo o dia, sem intercorrências relacionadas a chuva.`;

    return {
      audio_id: audioId,
      transcription,
    };
  },

  /**
   * POST /api/diario/gerar
   * Gera o diário de obra completo (DOCX + salva no storage)
   */
  async gerarDiario(data: {
    project_name: string;
    project_location: string;
    contractor?: string;
    supervisor?: string;
    photos: Array<{
      photo_id: string;
      url?: string;
      name?: string;
      classification?: string;
    }>;
    audio_transcription?: string;
  }): Promise<{
    report_id: string;
    download_url: string;
    success: true;
  }> {
    // Simular delay de geração
    await delay(3000);

    // Criar dados para o DOCX
    const diaryData: DiaryData = {
      projectName: data.project_name,
      projectLocation: data.project_location,
      contractor: data.contractor,
      supervisor: data.supervisor,
      createdAt: new Date(),
      photos: data.photos.map(p => ({
        url: p.url || '',
        name: p.name || p.photo_id,
        classification: p.classification,
      })),
      audioTranscription: data.audio_transcription,
    };

    // Gerar e baixar DOCX
    await generateAndDownloadDocx(diaryData);

    // Criar Report para salvar no storage
    const reportId = `report_${Date.now()}`;
    const thumbnailUrl = data.photos[0]?.url || undefined;

    const report: Report = {
      id: reportId,
      projectName: data.project_name,
      projectLocation: data.project_location,
      contractor: data.contractor,
      supervisor: data.supervisor,
      createdAt: new Date(),
      photoCount: data.photos.length,
      thumbnailUrl,
      status: 'complete',
      downloadUrl: '#', // Mock URL (DOCX já foi baixado)
    };

    // Salvar no localStorage
    storageService.saveReport(report);

    return {
      report_id: reportId,
      download_url: '#',
      success: true,
    };
  },
};

/**
 * Wrapper para manter compatibilidade com código que usa fetch()
 * Intercepta chamadas para localhost:8000 e redireciona para mockApi
 */
export function setupMockApiInterceptor() {
  const originalFetch = window.fetch;

  window.fetch = async (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
    const url = input.toString();

    // Interceptar chamadas para n8n webhooks (fallback quando n8n não está rodando)
    if (url.includes('/webhook/classify-photos')) {
      const body = JSON.parse(init?.body as string);
      const result = await mockApi.classificarFotos(body.photo_ids);
      return new Response(JSON.stringify({ classifications: result }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (url.includes('/webhook/transcribe-audio')) {
      const body = JSON.parse(init?.body as string);
      const result = await mockApi.transcreverAudio(body.audio_id);
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Interceptar chamadas para o backend mock
    if (url.includes('/api/fotos/classificar')) {
      const body = JSON.parse(init?.body as string);
      const result = await mockApi.classificarFotos(body.photo_ids);
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (url.includes('/api/audio/transcrever')) {
      const body = JSON.parse(init?.body as string);
      const result = await mockApi.transcreverAudio(body.audio_id);
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (url.includes('/api/diario/gerar')) {
      const body = JSON.parse(init?.body as string);
      const result = await mockApi.gerarDiario(body);
      return new Response(JSON.stringify(result), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (url.includes('/api/fotos/ordenar')) {
      // Mock: Just return success, don't actually persist order
      return new Response(JSON.stringify({ success: true }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    if (url.includes('/api/fotos/upload')) {
      // Mock photo upload
      await delay(500); // Simulate upload delay

      const photoId = `photo_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
      const photoUrl = `blob:http://localhost:5176/${photoId}`;

      return new Response(JSON.stringify({
        photo_id: photoId,
        url: photoUrl,
        success: true,
      }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    }

    // Qualquer outra chamada passa pelo fetch original
    return originalFetch(input, init);
  };

  console.log('✅ Mock API interceptor ativado');
}
