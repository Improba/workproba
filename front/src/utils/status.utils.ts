export const statuses = {
  DRAFT: {
    color: 'info',
    label: 'Brouillon',
    dark: true,
  },
  ACTIVE: {
    color: 'positive',
    label: 'Actif',
    dark: false,
  },
  ARCHIVE: {
    color: 'grey-5',
    label: 'Archivé',
    dark: false,
  },
  TRASH: {
    color: 'negative',
    label: 'Corbeille',
    dark: true,
  },
} as any;

export const getStatusColor = (status: any) =>
  statuses[status]?.color || 'white';
export const getStatusIsDark = (status: any) => statuses[status]?.dark || false;

export const getStatusLabel = (status: any) => statuses[status]?.label || '-';

export const getStatusOptions = () =>
  Object.keys(statuses).map((status) => ({
    value: status,
    label: getStatusLabel(status),
  }));
