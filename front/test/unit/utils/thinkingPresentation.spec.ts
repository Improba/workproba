import { describe, expect, it } from 'vitest';
import {
  deriveThinkingSubject,
  deriveThinkingSubjectDone,
  deriveThinkingSummary,
} from '@utils/thinkingPresentation';

describe('thinkingPresentation', () => {
  it('retourne null pour un contenu vide', () => {
    expect(deriveThinkingSubject('')).toBeNull();
    expect(deriveThinkingSummary('')).toBeNull();
    expect(deriveThinkingSubjectDone('')).toBeNull();
  });

  it('ignore les séparateurs et lignes trop courtes', () => {
    const content = '---\n*\nok\n***\nAnalyse du fichier config';
    expect(deriveThinkingSubject(content)).toBe('Analyse du fichier config');
  });

  it('dérive le sujet courant depuis la dernière ligne significative', () => {
    const content = 'Étape 1 : lire le fichier\nÉtape 2 : valider les entrées';
    expect(deriveThinkingSubject(content)).toBe('Étape 2 : valider les entrées');
  });

  it('tronque le sujet au-delà de 100 caractères', () => {
    const long = 'a'.repeat(120);
    const subject = deriveThinkingSubject(long);
    expect(subject).not.toBeNull();
    expect(subject!.length).toBeLessThanOrEqual(100);
    expect(subject!.endsWith('…')).toBe(true);
  });

  it('produit un résumé de quelques phrases jointes', () => {
    const content = [
      'Première idée sur le problème.',
      'Deuxième étape de vérification.',
      'Troisième point important.',
    ].join('\n');
    const summary = deriveThinkingSummary(content);
    expect(summary).toContain('Première idée sur le problème.');
    expect(summary).toContain('·');
  });

  it('fige un sujet done en préférant la phrase la plus informative', () => {
    const content = 'Court.\nUne analyse plus détaillée du comportement attendu.';
    const done = deriveThinkingSubjectDone(content);
    expect(done).toBe('Une analyse plus détaillée du comportement attendu.');
  });

  it('ne produit pas de sujet générique inventé', () => {
    expect(deriveThinkingSubject('---\n***')).toBeNull();
    expect(deriveThinkingSummary('   \n\n  ')).toBeNull();
  });

  it('ignore le ton observateur pour le sujet courant', () => {
    const content = [
      'Vérification des entrées.',
      "L'utilisateur veut une saisie mardi.",
      'Préparation de la requête API.',
    ].join('\n');
    expect(deriveThinkingSubject(content)).toBe('Préparation de la requête API.');
  });

  it('retourne null si seules des lignes observateur', () => {
    const content = "L'utilisateur demande une modification.\nJe vais lui expliquer la procédure.";
    expect(deriveThinkingSubject(content)).toBeNull();
    expect(deriveThinkingSubjectDone(content)).toBeNull();
    expect(deriveThinkingSummary(content)).toBeNull();
  });

  it('filtre le ton observateur dans le résumé thinking', () => {
    const content = [
      "L'utilisateur a confirmé.",
      'Vérification du montant TTC.',
      'Je vais lui dire quoi coller.',
      "Appel de l'API Pennylane.",
    ].join('\n');
    const summary = deriveThinkingSummary(content);
    expect(summary).toContain('Vérification du montant TTC.');
    expect(summary).toContain("Appel de l'API Pennylane.");
    expect(summary).not.toMatch(/L'utilisateur/i);
    expect(summary).not.toMatch(/Je vais lui/i);
  });
});
