/**
 * Configuration des items du menu utilisateur par défaut
 * 
 * Ce fichier exporte une fonction qui génère les items du menu dropdown
 * utilisateur affiché dans la toolbar. Ces items sont utilisés si aucun
 * profileMenuItems personnalisé n'est fourni à StandardLayout.
 * 
 * Items par défaut :
 * - theme : Toggle du thème clair/sombre (affiche ThemeToggler)
 * - quit : Déconnexion de l'utilisateur
 * 
 * Les projets peuvent personnaliser ces items en fournissant
 * profileMenuItems à StandardLayout ou en modifiant cette fonction.
 */
import type { UserMenuItem } from '../types/menu-item.types';
import type { IUseAuth } from '@lib-improba/composables/use-auth';
import type { Composer } from 'vue-i18n';

/**
 * Crée les items du menu utilisateur par défaut pour le layout standard
 * 
 * Cette fonction génère une liste d'items pour le menu dropdown utilisateur
 * affiché dans la toolbar. Les items incluent le toggle de thème et la déconnexion.
 * 
 * Items générés :
 * - 'theme' : Item spécial qui affiche ThemeToggler (pas de label simple)
 * - 'quit' : Item de déconnexion qui appelle auth.methods.logout()
 * 
 * @param i18n - Instance du composer i18n pour les traductions
 * @param auth - Instance du composable useAuth pour les actions d'authentification
 * @returns Tableau des items du menu utilisateur
 * 
 * Exemple d'utilisation :
 * ```typescript
 * const userMenuItems = getDefaultUserMenuItems(i18n, auth);
 * // Retourne : [
 * //   { name: 'theme', label: 'Thème', action: undefined },
 * //   { name: 'quit', label: 'Quitter', clickable: false, action: () => auth.methods.logout() }
 * // ]
 * ```
 */
export function getDefaultUserMenuItems(
  i18n: Composer,
  auth: IUseAuth
): UserMenuItem[] {
  return [
    {
      name: 'theme',
      label: i18n.t('theme'),
      action: undefined,
      // Note : Cet item est traité spécialement dans StandardToolbar
      // et affiche ThemeToggler au lieu d'un simple label
    },
    {
      name: 'quit',
      label: () => i18n.t('layout.dropDownMenu.quit'),
      clickable: false,
      action: () => {
        auth.methods.logout();
      },
    },
  ];
}

