import { describe, expect, it } from 'vitest';
import {
  buildToolCallDetails,
  durationLabel,
  statusLabel,
} from '@utils/toolCallDetails';
import type { ChatToolCall } from '#types';

function tc(over: Partial<ChatToolCall> = {}): ChatToolCall {
  return {
    id: 'tc1',
    name: 'list_files',
    status: 'success',
    startedAt: 1000,
    endedAt: 1500,
    ...over,
  };
}

describe('buildToolCallDetails', () => {
  it('décrit la cible et l’emplacement pour list_files', () => {
    const d = buildToolCallDetails(
      tc({ name: 'list_files', args: { subdir: 'src/components' }, result: { entries: [1, 2, 3] } }),
    );
    expect(d.target).toContain('du dossier components');
    expect(d.location).toContain('le dossier components');
    expect(d.outcome).toContain('3 éléments');
  });

  it('décrit la requête pour search_kb', () => {
    const d = buildToolCallDetails(
      tc({ name: 'search_kb', args: { query: 'budget 2026' }, result: { results: [{}, {}] } }),
    );
    expect(d.target).toContain('« budget 2026 »');
    expect(d.outcome).toContain('2 résultats');
  });

  it('décrit la requête et les sources pour web_search', () => {
    const d = buildToolCallDetails(
      tc({
        name: 'web_search',
        args: { query: 'météo Paris' },
        result: {
          backend: 'mistral',
          results: [{ title: 'Météo Paris', url: 'https://example.com/weather' }],
        },
      }),
    );
    expect(d.target).toContain('« météo Paris »');
    expect(d.location).toContain('web');
    expect(d.outcome).toContain('1 source');
    expect(d.rows.some((r) => r.value.includes('example.com'))).toBe(true);
  });

  it('décrit le fichier créé et son dossier pour generate_document', () => {
    const d = buildToolCallDetails(
      tc({
        name: 'generate_document',
        args: { name: 'claude-meylan.md' },
        filePath: 'assets/claude-meylan.md',
        status: 'success',
      }),
    );
    expect(d.target).toContain('claude-meylan.md');
    expect(d.location).toContain('assets');
  });

  it('expose toujours le statut et la durée dans les rows', () => {
    const d = buildToolCallDetails(tc({ name: 'run_code', args: { language: 'python' } }));
    const labels = d.rows.map((r) => r.label);
    expect(labels).toContain('Durée');
    expect(labels).toContain('Statut');
  });

  it('ne plante pas sur un outil inconnu', () => {
    const d = buildToolCallDetails(tc({ name: 'mystery_tool', args: {} }));
    expect(d.rows.length).toBeGreaterThan(0);
    expect(d.rows[d.rows.length - 1].label).toBe('Statut');
  });
});

describe('statusLabel', () => {
  it('libelle les statuts connus', () => {
    expect(statusLabel('success')).toBe('Terminé');
    expect(statusLabel('error')).toBe('Échec');
    expect(statusLabel('running')).toBe('En cours…');
    expect(statusLabel('awaiting_confirmation')).toBe('En attente de confirmation');
    expect(statusLabel('pending')).toBe('En attente');
  });
});

describe('durationLabel', () => {
  it('formate les millisecondes et les secondes', () => {
    expect(durationLabel(tc({ startedAt: 1000, endedAt: 1180 }))).toBe('180 ms');
    expect(durationLabel(tc({ startedAt: 1000, endedAt: 2600 }))).toBe('1.6 s');
  });

  it('retourne vide sans startedAt', () => {
    expect(durationLabel(tc({ startedAt: undefined }))).toBe('');
  });
});
