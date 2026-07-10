/**
 * Types pour les props du layout standard
 * 
 * Ce fichier définit les interfaces TypeScript pour les props
 * des composants du layout standard, permettant une validation
 * de type stricte et une meilleure autocomplétion.
 */
import type { MenuItem, UserMenuItem } from './menu-item.types';

/**
 * Props pour le composant StandardLayout
 * 
 * Cette interface définit toutes les props acceptées par StandardLayout,
 * permettant de personnaliser le menu de navigation, le menu utilisateur,
 * et le comportement du layout.
 * 
 * Toutes les props sont optionnelles avec des valeurs par défaut définies
 * dans le composant StandardLayout.
 * 
 * @see StandardLayout pour l'utilisation de ces props
 */
export interface StandardLayoutProps {
  /** 
   * Items de menu personnalisés à afficher dans la barre de navigation
   * Si null ou undefined, utilise defaultMenuItems
   * Le menu "Admin" est ajouté automatiquement si l'utilisateur a le rôle ADMIN
   */
  menuItems?: MenuItem[] | null;
  
  /** 
   * Items du menu utilisateur personnalisés pour le dropdown profil
   * Si null ou undefined, utilise getDefaultUserMenuItems()
   * Les items par défaut incluent le toggle de thème et la déconnexion
   */
  profileMenuItems?: UserMenuItem[] | null;
  
  /** 
   * Titre à afficher pour le rôle utilisateur dans la toolbar
   * Utilisé comme fallback si le nom d'utilisateur n'est pas disponible
   */
  roleTitle?: string;
  
  /** 
   * Label pour le toggle de thème
   * Actuellement non utilisé dans l'implémentation mais disponible pour personnalisation
   */
  themeLabel?: string;
  
  /** 
   * Si true, le drawer gauche (s'il existe) sera affiché en overlay au-dessus du contenu
   * Sinon, le drawer pousse le contenu vers la droite
   * Affecte la vue Quasar Layout utilisée
   */
  leftDrawerOnTop?: boolean;
}

