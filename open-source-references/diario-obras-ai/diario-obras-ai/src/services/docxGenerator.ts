import {
  Document,
  Packer,
  Paragraph,
  TextRun,
  HeadingLevel,
  AlignmentType,
  ImageRun,
} from 'docx';
import { saveAs } from 'file-saver';

/**
 * Helper function to fetch image from URL and convert to ArrayBuffer
 */
async function fetchImageAsBuffer(url: string): Promise<ArrayBuffer | null> {
  try {
    const response = await fetch(url);
    if (!response.ok) {
      console.error(`Failed to fetch image: ${url}`);
      return null;
    }
    return await response.arrayBuffer();
  } catch (error) {
    console.error(`Error fetching image ${url}:`, error);
    return null;
  }
}

export interface DiaryData {
  projectName: string;
  projectLocation: string;
  contractor?: string;
  supervisor?: string;
  createdAt: Date;
  photos: Array<{
    url: string;
    name?: string;
    classification?: string;
  }>;
  audioTranscription?: string;
}

/**
 * Gera um documento DOCX para o diário de obra
 */
export async function generateDiaryDocx(data: DiaryData): Promise<Blob> {
  const sections: Paragraph[] = [];

  // Título
  sections.push(
    new Paragraph({
      text: data.projectName,
      heading: HeadingLevel.HEADING_1,
      alignment: AlignmentType.CENTER,
      spacing: { after: 200 },
    })
  );

  // Subtítulo (local e data)
  sections.push(
    new Paragraph({
      children: [
        new TextRun({
          text: `${data.projectLocation}\n`,
          bold: true,
        }),
        new TextRun({
          text: `Data: ${data.createdAt.toLocaleDateString('pt-BR', {
            day: '2-digit',
            month: 'long',
            year: 'numeric',
          })}`,
          italics: true,
        }),
      ],
      alignment: AlignmentType.CENTER,
      spacing: { after: 400 },
    })
  );

  // Seção 1: Informações do Projeto
  sections.push(
    new Paragraph({
      text: '1. Informações do Projeto',
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 400, after: 200 },
    })
  );

  if (data.contractor) {
    sections.push(
      new Paragraph({
        children: [
          new TextRun({ text: 'Contratada: ', bold: true }),
          new TextRun(data.contractor),
        ],
        spacing: { after: 100 },
      })
    );
  }

  if (data.supervisor) {
    sections.push(
      new Paragraph({
        children: [
          new TextRun({ text: 'Responsável: ', bold: true }),
          new TextRun(data.supervisor),
        ],
        spacing: { after: 100 },
      })
    );
  }

  sections.push(
    new Paragraph({
      children: [
        new TextRun({ text: 'Total de fotos: ', bold: true }),
        new TextRun(data.photos.length.toString()),
      ],
      spacing: { after: 200 },
    })
  );

  // Seção 2: Registro Fotográfico
  sections.push(
    new Paragraph({
      text: '2. Registro Fotográfico',
      heading: HeadingLevel.HEADING_2,
      spacing: { before: 400, after: 200 },
    })
  );

  // Processar fotos (limitar a 10 para não deixar documento muito pesado)
  const photosToInclude = data.photos.slice(0, 10);

  for (let i = 0; i < photosToInclude.length; i++) {
    const photo = photosToInclude[i];

    // Photo title
    sections.push(
      new Paragraph({
        children: [
          new TextRun({
            text: `Foto ${i + 1}${photo.classification ? `: ${photo.classification}` : ''}`,
            bold: true,
          }),
        ],
        spacing: { before: 200, after: 100 },
      })
    );

    // Try to embed the actual image
    const imageBuffer = await fetchImageAsBuffer(photo.url);
    if (imageBuffer) {
      try {
        sections.push(
          new Paragraph({
            children: [
              new ImageRun({
                data: new Uint8Array(imageBuffer),
                transformation: {
                  width: 600,
                  height: 450,
                },
                type: 'jpg',
              }),
            ],
            spacing: { after: 200 },
          })
        );
      } catch (error) {
        console.error('Error embedding image:', error);
        // Fallback to text reference if image embedding fails
        sections.push(
          new Paragraph({
            children: [
              new TextRun({
                text: `[Imagem: ${photo.name || `foto_${i + 1}`} - erro ao embedar]`,
                italics: true,
                color: '666666',
              }),
            ],
            spacing: { after: 200 },
          })
        );
      }
    } else {
      // Fallback to text reference if image fetch fails
      sections.push(
        new Paragraph({
          children: [
            new TextRun({
              text: `[Imagem: ${photo.name || `foto_${i + 1}`} - não disponível]`,
              italics: true,
              color: '666666',
            }),
          ],
          spacing: { after: 200 },
        })
      );
    }
  }

  if (data.photos.length > 10) {
    sections.push(
      new Paragraph({
        children: [
          new TextRun({
            text: `... e mais ${data.photos.length - 10} foto(s)`,
            italics: true,
          }),
        ],
        spacing: { after: 200 },
      })
    );
  }

  // Seção 3: Transcrição de Áudio (se disponível)
  if (data.audioTranscription) {
    sections.push(
      new Paragraph({
        text: '3. Observações (Transcrição de Áudio)',
        heading: HeadingLevel.HEADING_2,
        spacing: { before: 400, after: 200 },
      })
    );

    sections.push(
      new Paragraph({
        text: data.audioTranscription,
        spacing: { after: 200 },
      })
    );
  }

  // Rodapé
  sections.push(
    new Paragraph({
      text: '---',
      alignment: AlignmentType.CENTER,
      spacing: { before: 600, after: 100 },
    })
  );

  sections.push(
    new Paragraph({
      children: [
        new TextRun({
          text: 'Gerado por Diário de Obras.AI',
          italics: true,
        }),
      ],
      alignment: AlignmentType.CENTER,
      spacing: { after: 100 },
    })
  );

  // Criar documento
  const doc = new Document({
    sections: [
      {
        properties: {},
        children: sections,
      },
    ],
  });

  // Gerar blob
  const blob = await Packer.toBlob(doc);
  return blob;
}

/**
 * Gera e baixa automaticamente o documento DOCX
 */
export async function generateAndDownloadDocx(
  data: DiaryData,
  filename?: string
): Promise<void> {
  const blob = await generateDiaryDocx(data);
  const fileName = filename || `diario_${data.projectName.replace(/\s+/g, '_')}_${Date.now()}.docx`;
  saveAs(blob, fileName);
}
