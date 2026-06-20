import { useState, useCallback, useRef, useEffect } from 'react';

export interface AudioRecording {
  id: string;
  url: string;
  blob: Blob;
  duration: number;
  size: number;
  createdAt: Date;
}

export const useAudioRecorder = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [recordingTime, setRecordingTime] = useState(0);
  const [recordings, setRecordings] = useState<AudioRecording[]>([]);
  const [error, setError] = useState<string | null>(null);

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<number | null>(null);

  const formatTime = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const startRecording = useCallback(async () => {
    try {
      // Solicitar permissão do microfone
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

      // Criar MediaRecorder
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          chunksRef.current.push(event.data);
        }
      };

      mediaRecorder.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: 'audio/webm' });
        const url = URL.createObjectURL(blob);

        const recording: AudioRecording = {
          id: `audio_${Date.now()}`,
          url,
          blob,
          duration: recordingTime,
          size: blob.size,
          createdAt: new Date(),
        };

        setRecordings((prev) => [...prev, recording]);
        chunksRef.current = [];
      };

      // Iniciar gravação
      mediaRecorder.start();
      setIsRecording(true);
      setError(null);

      // Timer
      timerRef.current = setInterval(() => {
        setRecordingTime((prev) => prev + 1);
      }, 1000) as unknown as number;

    } catch (err) {
      setError('Erro ao acessar microfone: ' + (err as Error).message);
      console.error('Erro ao gravar áudio:', err);
    }
  }, [recordingTime]);

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== 'inactive') {
      mediaRecorderRef.current.stop();
      setIsRecording(false);

      // Parar timer
      if (timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }
  }, []);

  const removeRecording = useCallback((id: string) => {
    setRecordings((prev) => prev.filter((r) => r.id !== id));
  }, []);

  const clearRecordings = useCallback(() => {
    setRecordings([]);
  }, []);

  const getRecordingFile = useCallback((recording: AudioRecording): Promise<File> => {
    return fetch(recording.url)
      .then((res) => res.blob())
      .then((blob) => new File([blob], `audio_${recording.id}.webm`, { type: 'audio/webm' }));
  }, []);

  // Limpar URLs ao desmontar
  useEffect(() => {
    return () => {
      recordings.forEach((recording) => {
        URL.revokeObjectURL(recording.url);
      });
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, [recordings]);

  return {
    isRecording,
    recordingTime: formatTime(recordingTime),
    recordings,
    error,
    startRecording,
    stopRecording,
    removeRecording,
    clearRecordings,
    getRecordingFile,
  };
};
