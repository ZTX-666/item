export interface Photo {
  id: string;
  url: string;
  preview: string;
  name: string;
  size: number;
  type: string;
  lastModified: number;
  order?: number;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  createdAt: Date;
  updatedAt: Date;
  photos: Photo[];
}

export interface DiaryEntry {
  id: string;
  projectId: string;
  date: Date;
  content: string;
  photos: Photo[];
  audioUrl?: string;
  status: 'draft' | 'published';
}

export interface Report {
  id: string;
  projectName: string;
  projectLocation?: string;
  contractor?: string;
  supervisor?: string;
  createdAt: Date;
  photoCount: number;
  thumbnailUrl?: string;
  status?: 'complete' | 'draft';
  downloadUrl?: string;
}
