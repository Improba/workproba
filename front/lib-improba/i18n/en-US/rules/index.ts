export default {
  firstname: {
    required: 'A firstname is required',
    tooLong: 'Firstname is too long',
  },
  lastname: {
    required: 'A name is required',
    tooLong: 'Name is too long',
  },
  name: {
    required: 'A name is required',
    tooLong: 'Name is too long',
    specialCharsNotAllowed: "You cannot use the '/' symbol",
  },
  password: {
    required: 'A password is required',
    tooLong: 'Password is too long',
    match: 'Passwords must match',
    formatMedium:
      'Password must made of at least 6 letters with at least one uppercase, one lowercase and one number.',
    format:
      'Password must made of at least 14 letters with at least one uppercase, one lowercase, one number and one special symbol.',
  },
  description: {
    required: 'A description is required',
    tooLong: 'Description is too long',
  },
  email: {
    required: 'An email is required',
    wrongFormat: 'It must be an email',
  },
  alphanumeric: {
    notAllowed:
      "Only number, letters and the following special characters are allowed: '_', '.'",
  },
  lang: {
    required: 'A langage is required',
    tooLong: 'The langage label is too long',
  },
};
