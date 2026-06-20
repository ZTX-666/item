import React from 'react';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Photo } from '../../types';
import { X, GripVertical } from 'lucide-react';
import { useDragDrop } from '../../hooks/useDragDrop';
import { arrayMove } from '@dnd-kit/sortable';
import { orderPhotos } from '../../lib/api';

interface SortablePhotoItemProps {
  photo: Photo;
  onRemove: (id: string) => void;
}

const SortablePhotoItem: React.FC<SortablePhotoItemProps> = ({ photo, onRemove }) => {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
  } = useSortable({ id: photo.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="relative group bg-white rounded-lg shadow-md overflow-hidden"
    >
      {/* Drag Handle */}
      <button
        {...attributes}
        {...listeners}
        className="absolute top-2 left-2 z-10 p-2 bg-black/50 hover:bg-black/70 text-white rounded-md opacity-0 group-hover:opacity-100 transition-opacity cursor-grab active:cursor-grabbing"
      >
        <GripVertical size={16} />
      </button>

      {/* Photo Preview */}
      <img
        src={photo.preview}
        alt={photo.name}
        className="w-full h-48 object-cover"
        loading="lazy"
      />

      {/* Photo Info */}
      <div className="p-3">
        <p className="text-sm font-medium text-primary truncate">{photo.name}</p>
        <p className="text-xs text-primary-light">{(photo.size / 1024).toFixed(1)} KB</p>
      </div>

      {/* Remove Button */}
      <button
        onClick={() => onRemove(photo.id)}
        className="absolute top-2 right-2 z-10 p-2 bg-red-500 hover:bg-red-600 text-white rounded-md opacity-0 group-hover:opacity-100 transition-opacity"
      >
        <X size={16} />
      </button>
    </div>
  );
};

interface PhotoGridProps {
  photos: Photo[];
  onRemove: (id: string) => void;
  onReorder: (photos: Photo[]) => void;
  className?: string;
}

export const PhotoGrid: React.FC<PhotoGridProps> = ({ photos, onRemove, onReorder, className = '' }) => {
  const { DragDropProvider } = useDragDrop({
    items: photos.map(p => ({ id: p.id })),
    children: (
      <div className={`grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 ${className}`}>
        {photos.map((photo) => (
          <SortablePhotoItem key={photo.id} photo={photo} onRemove={onRemove} />
        ))}
      </div>
    ),
    onDragEnd: async (event) => {
      const { active, over } = event;

      if (over && active.id !== over.id) {
        const oldIndex = photos.findIndex(p => p.id === active.id);
        const newIndex = photos.findIndex(p => p.id === over.id);

        const newPhotos = arrayMove(photos, oldIndex, newIndex);

        const photosWithOrder = newPhotos.map((photo, index) => ({
          ...photo,
          order: index,
        }));

        await orderPhotos({
          photos: photosWithOrder.map(p => ({ id: p.id, order: p.order! })),
        });

        onReorder(newPhotos);
      }
    },
  });

  if (photos.length === 0) {
    return (
      <div className={`text-center py-12 text-primary-light ${className}`}>
        <p className="text-lg">Nenhuma foto carregada ainda</p>
        <p className="text-sm mt-2">Faça upload das fotos para começar</p>
      </div>
    );
  }

  return <DragDropProvider />;
};
