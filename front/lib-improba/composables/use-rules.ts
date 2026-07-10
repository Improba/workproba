/**
 * This composable is used to define the rules for the forms.
 * It is used to validate the input values and to display the error messages.
 * 
 * For example:
 * ```html
 * <template>
 *   <!-- This will validate the email using the rules.email and the rules.firstname -->
 *   <DFormInput type="text" :rules="[...rules.email, ...rules.firstname]" />
 * 
 *   <!-- This will validate the email using only the rules.email -->
 *   <DFormInput type="text" :rules="rules.email" />
 * 
 *   <!-- This will validate the email using a custom rule -->
 *   <DFormInput type="text" :rules="[(v: string) => !!v || 'A value is required']" />
 * </template>
 * 
 * <script lang="ts">
 * import { useRules } from 'src/lib-improba/composables/use-rules';
 * 
 * export default defineComponent({
 *   setup() {
 *     // This will return the rules object with the rules for the forms
 *     const rules = useRules();
 *     return { rules };
 *   },
 * });
 * </script>
 * ```
 */


import { useI18n } from 'vue-i18n';

export const useRules = () => {
  const i18n = useI18n();

  const methods = {
    rules: () => {
      const r = {
        firstname: [
          (v: string) => !!v || i18n.t('rules.firstname.required'),
          (v: string) =>
            (v && v.length < 255) || i18n.t('rules.firstname.tooLong'),
        ],
        lastname: [
          (v: string) => !!v || i18n.t('rules.lastname.required'),
          (v: string) =>
            (v && v.length < 255) || i18n.t('rules.lastname.tooLong'),
        ],
        name: [
          (v: string) => !!v || i18n.t('rules.name.required'),
          (v: string) => v.length < 255 || i18n.t('rules.name.tooLong'),
          (v: string) =>
            !v || !/\//g.exec(v) || i18n.t('rules.name.specialCharsNotAllowed'),
        ],
        description: [
          (v: string) => {
            if (v && v.length > 2000)
              return i18n.t('rules.description.tooLong');
          },
        ],
        comment: [
          (v: string) => {
            if (!v) return 'Veuillez saisir le commentaire';
            if (v && v.length > 1000) return 'Commentaire trop long';
            if (v && v.length < 5) return 'Commentaire trop court';
          },
        ],
        pureNumberOnly: [
          (v: string | number) => {
            const vFloat =
              typeof v === 'string' ? parseFloat(v) : parseFloat(v.toString());
            if (v === undefined || vFloat === undefined || isNaN(vFloat)) {
              return 'Une valeur numérique doit être présente';
            }
          },
          (v: string) =>
            !(v && !/^[0-9._]*$/.test(v)) || 'Saisissez un chiffre valide',
        ],
        positiveIntNumber: [
          (v: string) =>
            (v !== undefined && v !== null) || 'Une valeur doit être présente',
          (v: string) =>
            !(v && !/^[0-9_-]*$/.test(v)) ||
            'Saisissez un nombre entier valide',
          (v: string | number) => {
            const vInt =
              typeof v === 'string' ? parseInt(v) : parseInt(v.toString());
            if (vInt === undefined || isNaN(vInt) || vInt <= 0) {
              return 'Saisissez un nombre positif';
            }
          },
        ],
        positiveOrZeroIntNumber: [
          (v: string) =>
            (v !== undefined && v !== null) || 'Une valeur doit être présente',
          (v: string) =>
            !(v && !/^[0-9_-]*$/.test(v)) ||
            'Saisissez un nombre entier valide',
          (v: string | number) => {
            const vInt =
              typeof v === 'string' ? parseInt(v) : parseInt(v.toString());
            if (vInt === undefined || isNaN(vInt) || vInt < 0) {
              return 'Saisissez un nombre positif ou 0';
            }
          },
        ],
        alphanumeric: [
          (v: string) =>
            (v && /^[a-zA-Z0-9._]*$/.test(v)) ||
            i18n.t('rules.alphanumeric.notAllowed'),
        ],
        lang: [
          (v: string) => !!v || i18n.t('rules.lang.required'),
          (v: string) => v.length < 255 || i18n.t('rules.lang.tooLong'),
        ],
        email: [
          (v: string) =>
            !(v && !/^.+@.+\.[a-zA-Z]{2,3}$/.test(v)) ||
            i18n.t('rules.email.wrongFormat'),
        ],
        passwordSimple: [
          (v: string) => !!v || i18n.t('rules.password.required'),
          (v: string) => v.length < 555 || i18n.t('rules.password.tooLong'),
        ],
        passwordMedium: [
          (v: string) => !!v || i18n.t('rules.password.required'),
          (v: string) => v.length < 555 || i18n.t('rules.password.tooLong'),
          (v: string) =>
            (v.length >= 6 &&
              /[a-z]/.test(v) &&
              /[A-Z]/.test(v) &&
              /[0-9]/.test(v)) ||
            i18n.t('rules.password.formatMedium'),
        ],
        password: [
          (v: string) => !!v || i18n.t('rules.password.required'),
          (v: string) => v.length < 555 || i18n.t('rules.password.tooLong'),
          (v: string) =>
            (v.length >= 14 &&
              /[a-z]/.test(v) &&
              /[A-Z]/.test(v) &&
              /[0-9]/.test(v) &&
              /[$&+,:;=?@#|'<>.^*()%!-]/.test(v)) ||
            i18n.t('rules.password.format'),
        ],
        exist: [(v: string) => !!v || 'Une valeur doit être présente'],
      };

      return r;
    },
  };

  return {
    methods,
    ...methods.rules(),
  };
};
