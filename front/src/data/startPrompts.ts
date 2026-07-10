export interface StartPrompt {
  id: string;
  icon: string;
  title: string;
  subtitle: string;
  prompt: string;
}

export const START_PROMPTS: StartPrompt[] = [
  {
    id: 'pdf-summary',
    icon: 'file-text',
    title: 'Résumer un PDF',
    subtitle: 'Les points clés en un coup d\'œil',
    prompt: 'Résume ce PDF en 5 points clés',
  },
  {
    id: 'search-mentions',
    icon: 'search',
    title: 'Chercher dans les docs',
    subtitle: 'Trouver un mot ou une clause',
    prompt: 'Trouve toutes les mentions de "congés payés" dans mes documents',
  },
  {
    id: 'excel-candidates',
    icon: 'table',
    title: 'Tableau des candidats',
    subtitle: 'À partir des CV du dossier',
    prompt: 'Crée un tableau Excel des candidats à partir des CV du dossier',
  },
  {
    id: 'compare-quotes',
    icon: 'scale',
    title: 'Comparer des devis',
    subtitle: 'Identifier l\'offre la moins chère',
    prompt: 'Compare les deux devis et donne-moi le moins cher',
  },
  {
    id: 'invoice-reminder',
    icon: 'mail',
    title: 'Courrier de relance',
    subtitle: 'Pour une facture impayée',
    prompt: 'Rédige un courrier de relance pour facture impayée',
  },
  {
    id: 'revenue-chart',
    icon: 'bar-chart-3',
    title: 'Graphique de CA',
    subtitle: 'Extraire et visualiser les montants',
    prompt: 'Extrais les montants du CA Q2 et fais-moi un graphique',
  },
];
