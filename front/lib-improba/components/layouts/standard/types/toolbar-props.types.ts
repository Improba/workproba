/**
 * Types pour les props de la toolbar standard
 * 
 * Ce fichier définit les interfaces TypeScript pour les props
 * du composant StandardToolbar, permettant une validation de type
 * stricte et une meilleure autocomplétion.
 */
import type { MenuItem, UserMenuItem } from './menu-item.types';

/**
 * Props pour le composant StandardToolbar
 * 
 * Cette interface définit toutes les props acceptées par StandardToolbar,
 * qui est le composant responsable de l'affichage de la barre de navigation
 * principale avec les onglets de menu et le menu utilisateur.
 * 
 * Contrairement à StandardLayoutProps, certaines props sont requises ici
 * car StandardToolbar est un composant interne qui reçoit toujours des valeurs
 * calculées depuis StandardLayout.
 * 
 * @see StandardToolbar pour l'utilisation de ces props
 */
export interface StandardToolbarProps {
  /** 
   * Items de menu à afficher dans la barre de navigation
   * Ces items sont affichés comme des onglets cliquables
   * Requis - toujours fourni par StandardLayout après calcul
   */
  menuItems: MenuItem[];
  
  /** 
   * Items du menu utilisateur pour le dropdown profil
   * Ces items sont affichés dans le menu dropdown accessible via l'icône compte
   * Requis - toujours fourni par StandardLayout après calcul
   */
  userMenuItems: UserMenuItem[];
  
  /** 
   * Titre à afficher pour le rôle utilisateur
   * Utilisé comme fallback si le nom d'utilisateur n'est pas disponible
   * Optionnel - affiché à côté de l'icône compte si défini
   */
  roleTitle?: string;
  
  /** 
   * Label pour le toggle de thème
   * Actuellement non utilisé dans l'implémentation mais disponible pour personnalisation
   * Optionnel
   */
  themeLabel?: string;
}

