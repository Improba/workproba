export const toolbarOptions = [
  ['left', 'center', 'right', 'justify'],
  ['bold', 'italic', 'strike', 'underline'],
  ['hr', 'link'],
  [
    {
      label: 'format', // Remplacez par la variable appropriée pour la localisation
      icon: null, // Remplacez par la variable appropriée pour les icônes
      list: 'no-icons',
      options: ['h4', 'h5', 'h6'],
    },
    {
      label: 'taille de la police', // Remplacez par la variable appropriée pour la localisation
      icon: null, // Remplacez par la variable appropriée pour les icônes
      fixedLabel: true,
      fixedIcon: true,
      list: 'no-icons',
      options: [
        'size-1',
        'size-2',
        'size-3',
        'size-4',
        'size-5',
        'size-6',
        'size-7',
      ],
    },
  ],
  ['quote', 'unordered', 'ordered', 'outdent', 'indent'],
];
