import { computed, onUnmounted, ref, type ComputedRef, type Ref } from 'vue';
import type { ChatAttachment, ChatAttachmentKind } from '#types';

/** Nombre maximal de pièces jointes par message. */
export const MAX_ATTACHMENTS = 8;
/** Taille maximale d'un fichier joint (20 Mo). Au-delà, on refuse. */
export const MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024;

/** Valeur de l'attribut `accept` du <input type="file"> caché. */
export const ATTACHMENT_ACCEPT =
  'image/*,.pdf,.docx,.xlsx,.csv,.txt,.md,.json,.pptx';

const TEXT_MIMES = new Set<string>([
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
]);

const TEXT_EXTS = new Set<string>(['.txt', '.md', '.csv', '.json']);

const DOC_EXTS = new Set<string>(['.pdf', '.docx', '.xlsx', '.pptx']);

function fileExtension(name: string): string {
  const i = name.lastIndexOf('.');
  return i >= 0 ? name.slice(i).toLowerCase() : '';
}

/** Classifie un fichier en image / document binaire / texte. */
export function classifyAttachment(
  file: File,
): { kind: ChatAttachmentKind; mimeType: string } | null {
  const ext = fileExtension(file.name);
  const mime = file.type || '';

  if (mime.startsWith('image/')) {
    return { kind: 'image', mimeType: mime || 'image/*' };
  }
  if (DOC_EXTS.has(ext) || mime === 'application/pdf') {
    return { kind: 'document', mimeType: mime || extToMime(ext) };
  }
  if (TEXT_MIMES.has(mime) || TEXT_EXTS.has(ext)) {
    return { kind: 'text', mimeType: mime || extToMime(ext) };
  }
  return null;
}

function extToMime(ext: string): string {
  switch (ext) {
    case '.pdf':
      return 'application/pdf';
    case '.docx':
      return 'application/vnd.openxmlformats-officedocument.wordprocessingml.document';
    case '.xlsx':
      return 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet';
    case '.pptx':
      return 'application/vnd.openxmlformats-officedocument.presentationml.presentation';
    case '.md':
      return 'text/markdown';
    case '.csv':
      return 'text/csv';
    case '.json':
      return 'application/json';
    default:
      return 'text/plain';
  }
}

/** Encode un ArrayBuffer en base64 par morceaux (évite la pile sur gros fichiers). */
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  const CHUNK = 0x8000; // 32k chars par appel btoa
  let binary = '';
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
  }
  return btoa(binary);
}

function createId(): string {
  return `att-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export interface UseChatAttachmentsReturn {
  attachments: Ref<ChatAttachment[]>;
  hasAttachments: ComputedRef<boolean>;
  isReading: ComputedRef<boolean>;
  isDragOver: Ref<boolean>;
  addFiles: (files: File[] | FileList | null) => void;
  removeAttachment: (id: string) => void;
  clear: () => void;
  setDragOver: (value: boolean) => void;
}

export function useChatAttachments(): UseChatAttachmentsReturn {
  const attachments = ref<ChatAttachment[]>([]);
  const isDragOver = ref(false);

  const hasAttachments = computed(() => attachments.value.length > 0);
  const isReading = computed(() =>
    attachments.value.some((a) => a.status === 'reading'),
  );

  function revokePreview(att: ChatAttachment): void {
    if (att.previewUrl) {
      URL.revokeObjectURL(att.previewUrl);
      att.previewUrl = undefined;
    }
  }

  function removeAttachment(id: string): void {
    const idx = attachments.value.findIndex((a) => a.id === id);
    if (idx < 0) return;
    revokePreview(attachments.value[idx]);
    attachments.value.splice(idx, 1);
  }

  function clear(): void {
    for (const att of attachments.value) revokePreview(att);
    attachments.value = [];
    isDragOver.value = false;
  }

  async function readAttachment(
    att: ChatAttachment,
    file: File,
  ): Promise<void> {
    try {
      const buffer = await file.arrayBuffer();
      att.contentBase64 = arrayBufferToBase64(buffer);
      att.status = 'ready';
    } catch {
      att.status = 'error';
      att.error = 'Lecture du fichier impossible.';
    }
  }

  function addFiles(files: File[] | FileList | null): void {
    if (!files || files.length === 0) return;

    const incoming = Array.from(files);

    for (const file of incoming) {
      if (attachments.value.length >= MAX_ATTACHMENTS) break;

      const classified = classifyAttachment(file);
      if (!classified) {
        attachments.value.push({
          id: createId(),
          fileName: file.name,
          mimeType: file.type || 'application/octet-stream',
          sizeBytes: file.size,
          kind: 'document',
          status: 'error',
          error: 'Type de fichier non supporté.',
        });
        continue;
      }
      if (file.size > MAX_ATTACHMENT_BYTES) {
        attachments.value.push({
          id: createId(),
          fileName: file.name,
          mimeType: classified.mimeType,
          sizeBytes: file.size,
          kind: classified.kind,
          status: 'error',
          error: 'Fichier trop volumineux (max 20 Mo).',
        });
        continue;
      }

      const att: ChatAttachment = {
        id: createId(),
        fileName: file.name,
        mimeType: classified.mimeType,
        sizeBytes: file.size,
        kind: classified.kind,
        status: 'reading',
      };
      if (classified.kind === 'image') {
        att.previewUrl = URL.createObjectURL(file);
      }
      attachments.value.push(att);
      void readAttachment(att, file);
    }
  }

  onUnmounted(() => {
    for (const att of attachments.value) revokePreview(att);
  });

  return {
    attachments,
    hasAttachments,
    isReading,
    isDragOver,
    addFiles,
    removeAttachment,
    clear,
    setDragOver: (value: boolean) => {
      isDragOver.value = value;
    },
  };
}
