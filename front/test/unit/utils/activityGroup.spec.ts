import { describe, expect, it } from 'vitest';
import {
  activityGroupIdAt,
  computeActivityGroupStats,
  deriveConnectorSuffix,
  extractManagedConnector,
  groupMessageParts,
} from '@utils/activityGroup';
import type { ChatMessagePart, ChatToolCall } from '#types';

describe('groupMessageParts', () => {
  it('groupe un thinking seul en activity_group', () => {
    const parts: ChatMessagePart[] = [
      { type: 'text', id: 't1', content: 'Bonjour' },
      {
        type: 'thinking',
        id: 'think-1',
        thinkingId: 'think-0',
        content: 'Je réfléchis',
        done: false,
      },
    ];

    const blocks = groupMessageParts(parts);
    expect(blocks).toHaveLength(2);
    expect(blocks[0]).toEqual({ kind: 'text', part: parts[0] });
    expect(blocks[1].kind).toBe('activity_group');
    if (blocks[1].kind !== 'activity_group') return;
    expect(blocks[1].group.id).toBe('think-1');
    expect(blocks[1].group.toolCallIds).toEqual([]);
    expect(blocks[1].group.parts).toHaveLength(1);
  });

  it('groupe thinking + tool_call consécutifs en activity_group', () => {
    const parts: ChatMessagePart[] = [
      {
        type: 'thinking',
        id: 'think-1',
        thinkingId: 'think-0',
        content: 'Analyse',
        done: true,
      },
      { type: 'tool_call', id: 'tc-part-1', toolCallId: 'tc-1' },
      { type: 'tool_call', id: 'tc-part-2', toolCallId: 'tc-2' },
    ];

    const blocks = groupMessageParts(parts);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].kind).toBe('activity_group');
    if (blocks[0].kind !== 'activity_group') return;
    expect(blocks[0].group.id).toBe('think-1');
    expect(blocks[0].group.toolCallIds).toEqual(['tc-1', 'tc-2']);
    expect(blocks[0].group.parts).toHaveLength(3);
  });

  it('ne fusionne pas à travers un segment texte', () => {
    const parts: ChatMessagePart[] = [
      { type: 'thinking', id: 'think-1', thinkingId: 'a', content: 'A', done: true },
      { type: 'tool_call', id: 'tc-1', toolCallId: 'tool-a' },
      { type: 'text', id: 'text-1', content: 'Milieu' },
      { type: 'tool_call', id: 'tc-2', toolCallId: 'tool-b' },
    ];

    const blocks = groupMessageParts(parts);
    expect(blocks).toHaveLength(3);
    expect(blocks[0].kind).toBe('activity_group');
    expect(blocks[1].kind).toBe('text');
    expect(blocks[2].kind).toBe('activity_group');
    if (blocks[2].kind === 'activity_group') {
      expect(blocks[2].group.toolCallIds).toEqual(['tool-b']);
    }
  });

  it('groupe plusieurs tool_call sans thinking', () => {
    const parts: ChatMessagePart[] = [
      { type: 'tool_call', id: 'tc-part-1', toolCallId: 'tc-1' },
      { type: 'tool_call', id: 'tc-part-2', toolCallId: 'tc-2' },
    ];

    const blocks = groupMessageParts(parts);
    expect(blocks).toHaveLength(1);
    expect(blocks[0].kind).toBe('activity_group');
    if (blocks[0].kind !== 'activity_group') return;
    expect(blocks[0].group.id).toBe('tc-part-1');
  });
});

describe('activityGroupIdAt', () => {
  it('retourne l id de la première part du run', () => {
    const parts: ChatMessagePart[] = [
      {
        type: 'thinking',
        id: 'think-A',
        thinkingId: 'a',
        content: 'A',
        done: true,
      },
      {
        type: 'thinking',
        id: 'think-B',
        thinkingId: 'b',
        content: 'B',
        done: true,
      },
      { type: 'tool_call', id: 'tc-part', toolCallId: 'tc-1' },
    ];

    expect(activityGroupIdAt(parts, 0)).toBe('think-A');
    expect(activityGroupIdAt(parts, 1)).toBe('think-A');
    expect(activityGroupIdAt(parts, 2)).toBe('think-A');
  });

  it('retourne null pour un segment texte', () => {
    const parts: ChatMessagePart[] = [
      { type: 'text', id: 't1', content: 'Hello' },
      {
        type: 'thinking',
        id: 'think-1',
        thinkingId: 'a',
        content: 'A',
        done: true,
      },
    ];
    expect(activityGroupIdAt(parts, 0)).toBeNull();
    expect(activityGroupIdAt(parts, 1)).toBe('think-1');
  });
});

describe('extractManagedConnector', () => {
  it('extrait le connecteur depuis managed__{connector}__{tool}', () => {
    expect(extractManagedConnector('managed__ihora__list_absences')).toBe('ihora');
    expect(extractManagedConnector('managed__ihora.shaped__get_timesheet')).toBe(
      'ihora.shaped',
    );
    expect(extractManagedConnector('list_files')).toBeNull();
    expect(extractManagedConnector('managed__malformed')).toBeNull();
  });
});

describe('deriveConnectorSuffix', () => {
  it('retourne null sans outil managed', () => {
    const calls: ChatToolCall[] = [
      { id: '1', name: 'list_files', status: 'success' },
    ];
    expect(deriveConnectorSuffix(calls)).toBeNull();
  });

  it('retourne un connecteur unique', () => {
    const calls: ChatToolCall[] = [
      { id: '1', name: 'managed__ihora__list_absences', status: 'success' },
      { id: '2', name: 'managed__ihora__get_timesheet', status: 'success' },
    ];
    expect(deriveConnectorSuffix(calls)).toBe('ihora');
  });

  it('joint plusieurs connecteurs distincts', () => {
    const calls: ChatToolCall[] = [
      { id: '1', name: 'managed__ihora__list_absences', status: 'success' },
      { id: '2', name: 'managed__autre__foo', status: 'success' },
    ];
    expect(deriveConnectorSuffix(calls)).toBe('autre, ihora');
  });
});

describe('computeActivityGroupStats', () => {
  it('compte outils, erreurs et statut en cours', () => {
    const toolCalls = new Map<string, ChatToolCall>([
      ['tc-1', { id: 'tc-1', name: 'list_files', status: 'success' }],
      ['tc-2', { id: 'tc-2', name: 'run_code', status: 'error' }],
      ['tc-3', { id: 'tc-3', name: 'web_search', status: 'running' }],
    ]);

    const stats = computeActivityGroupStats(
      [
        { type: 'tool_call', id: 'p1', toolCallId: 'tc-1' },
        { type: 'tool_call', id: 'p2', toolCallId: 'tc-2' },
        { type: 'tool_call', id: 'p3', toolCallId: 'tc-3' },
      ],
      toolCalls,
    );

    expect(stats.toolCount).toBe(3);
    expect(stats.errorCount).toBe(1);
    expect(stats.hasRunning).toBe(true);
  });

  it('détecte pending_confirmation comme en cours', () => {
    const toolCalls = new Map<string, ChatToolCall>([
      [
        'tc-1',
        { id: 'tc-1', name: 'write_docx', status: 'pending_confirmation' },
      ],
    ]);

    const stats = computeActivityGroupStats(
      [{ type: 'tool_call', id: 'p1', toolCallId: 'tc-1' }],
      toolCalls,
    );

    expect(stats.hasRunning).toBe(true);
  });
});
