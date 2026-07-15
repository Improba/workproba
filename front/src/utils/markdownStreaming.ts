export interface MarkdownStreamSplit {
  completeBlocks: string[];
  tail: string;
}

/**
 * Découpe le markdown en blocs complets (parseables une fois) et une queue
 * encore en cours d'écriture pendant le SSE.
 *
 * Les frontières de bloc sont les lignes vides hors fence ``` ; une fence
 * non fermée garde tout le contenu dans `tail`.
 */
export function splitMarkdownForStreaming(content: string): MarkdownStreamSplit {
  if (!content) {
    return { completeBlocks: [], tail: '' };
  }

  const completeBlocks: string[] = [];
  let blockStart = 0;
  let inFence = false;
  let fenceMarker = '';
  let i = 0;

  while (i < content.length) {
    const lineEnd = content.indexOf('\n', i);
    const hasLineEnd = lineEnd !== -1;
    const lineEndPos = hasLineEnd ? lineEnd : content.length;
    const line = content.slice(i, lineEndPos);

    const fenceMatch = line.match(/^(`{3,}|~{3,})(.*)$/);
    if (fenceMatch) {
      const marker = fenceMatch[1];
      if (!inFence) {
        inFence = true;
        fenceMarker = marker[0];
      } else if (
        marker[0] === fenceMarker &&
        marker.length >= fenceMarker.length
      ) {
        inFence = false;
        fenceMarker = '';
      }
    }

    if (!inFence && hasLineEnd && line.trim() === '' && i > blockStart) {
      const block = content.slice(blockStart, i).replace(/\n+$/, '');
      if (block.length > 0) {
        completeBlocks.push(block);
      }
      blockStart = lineEnd + 1;
    }

    i = hasLineEnd ? lineEnd + 1 : content.length;
  }

  const tail = content.slice(blockStart);
  return { completeBlocks, tail };
}
