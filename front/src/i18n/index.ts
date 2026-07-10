import enUS from './en-US';
import fr from './fr';
import improbaTranslations from '@lib-improba/i18n';
import { mergeDeep } from '@lib-improba/utils/general.utils';

const libImprobaTranslations = {
  ...improbaTranslations,
};

const translations = {
  'en-US': enUS,
  fr: fr,
};

// Merge the two sets of translations, the second one (the one of src) will have priority
const mergedTranslations = mergeDeep(libImprobaTranslations, translations);

export default {
  ...mergedTranslations,
};
