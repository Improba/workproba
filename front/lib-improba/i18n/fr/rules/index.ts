export default {
  firstname: {
    required: 'Un prénom est requis',
    tooLong: 'Le prénom est trop long',
  },
  lastname: {
    required: 'Un nom est requis',
    tooLong: 'Le nom est trop long',
  },
  name: {
    required: 'Un nom est requis',
    tooLong: 'Le nom est trop long',
    specialCharsNotAllowed:
      'Vous ne pouvez pas utiliser le caractère slash / dans le nom',
  },
  password: {
    required: 'Un mot de passe est requis',
    tooLong: 'Le mot de passe est trop long',
    formatMedium:
      "Le mot de passe doit être composé d'au moins 14 caractères avec une majuscule, une minuscule et un nombre",
    format:
      "Le mot de passe doit être composé d'au moins 14 caractères avec une majuscule, une minuscule, un nombre et un caractère spécial",
  },
  description: {
    required: 'Une description est requise',
    tooLong: 'La description est trop longue',
  },
  email: {
    required: 'Un email est requis',
    wrongFormat: 'Format erroné',
  },
  alphanumeric: {
    notAllowed:
      "Seuls les chiffres, les lettres et les caractères spéciaux suivants sont acceptés: '_', '.'",
  },
  lang: {
    required: 'Un langage est requis',
    tooLong: 'Le libellé du langage est trop long',
  },
};
