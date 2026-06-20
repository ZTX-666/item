import React, {
  useState,
  ReactNode,
} from 'react';
import {
  DndContext,
  DragEndEvent,
  DragOverlay,
  DragStartEvent,
  PointerSensor,
  useSensor,
  useSensors,
  closestCenter,
} from '@dnd-kit/core';
import { SortableContext, rectSortingStrategy } from '@dnd-kit/sortable';

interface UseDragDropProps {
  items: { id: string }[];
  onDragEnd: (event: DragEndEvent) => void;
  children: ReactNode;
  overlay?: ReactNode;
}

interface UseDragDropReturn {
  DragDropProvider: React.FC;
  activeId: string | null;
}

export const useDragDrop = ({ items, onDragEnd, children, overlay }: UseDragDropProps): UseDragDropReturn => {
  const [activeId, setActiveId] = useState<string | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 8,
      },
    })
  );

  const handleDragStart = (event: DragStartEvent) => {
    setActiveId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveId(null);
    onDragEnd(event);
  };

  const DragDropProvider: React.FC = () => {
    return (
      <DndContext
        sensors={sensors}
        collisionDetection={closestCenter}
        onDragStart={handleDragStart}
        onDragEnd={handleDragEnd}
      >
        <SortableContext items={items} strategy={rectSortingStrategy}>
          {children}
        </SortableContext>
        <DragOverlay>
          {activeId && overlay}
        </DragOverlay>
      </DndContext>
    );
  };

  return {
    DragDropProvider,
    activeId,
  };
};
