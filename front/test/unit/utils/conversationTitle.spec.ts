import { describe, expect, it } from 'vitest';
import { isProvisionalConversationTitle } from '@utils/conversationTitle';

const t = (key: string): string => {
  const map: Record<string, string> = {
    'chat.page.defaultTitle': 'Conversation',
    'common.newConversation': 'Nouvelle conversation',
  };
  return map[key] ?? key;
};

describe('isProvisionalConversationTitle', () => {
  it('accepte les titres vides ou par défaut', () => {
    expect(isProvisionalConversationTitle('', t)).toBe(true);
    expect(isProvisionalConversationTitle('Conversation', t)).toBe(true);
    expect(isProvisionalConversationTitle('Nouvelle conversation', t)).toBe(true);
    expect(isProvisionalConversationTitle('New conversation', t)).toBe(true);
  });

  it('refuse un titre personnalisé', () => {
    expect(isProvisionalConversationTitle('Analyse Kaggle ARC', t)).toBe(false);
  });
});
