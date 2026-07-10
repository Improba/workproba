/**
 * Types pour les items de menu du layout standard
 * 
 * Ce fichier définit les interfaces TypeScript pour les items de menu
 * utilisés dans la navigation principale et le menu utilisateur.
 */
import { RouteLocationRaw } from 'vue-router';

/**
 * Représente un item de menu dans la barre de navigation principale
 * 
 * Ces items sont affichés comme des onglets dans la toolbar et permettent
 * de naviguer entre les différentes sections de l'application.
 * 
 * Exemple :
 * ```typescript
 * const menuItem: MenuItem = {
 *   name: 'home',
 *   label: 'Accueil',
 *   route: { name: 'home' },
 *   disable: false,
 * };
 * ```
 */
export interface MenuItem {
  /** 
   * Label à afficher pour l'item de menu
   * Peut être une chaîne statique ou une fonction qui retourne une chaîne
   * (utile pour les labels traduits dynamiquement)
   */
  label: string | (() => string);
  
  /** 
   * Route vers laquelle naviguer lors du clic
   * Accepte tous les formats de RouteLocationRaw de Vue Router
   * (objet avec name/path, chaîne, etc.)
   */
  route: RouteLocationRaw;
  
  /** 
   * Si true, l'item est désactivé et non cliquable
   * Par défaut false
   */
  disable?: boolean;
  
  /** 
   * Nom de l'icône à afficher (optionnel)
   * Actuellement non utilisé dans StandardToolbar mais disponible pour extensions
   */
  icon?: string;
  
  /** 
   * Identifiant unique optionnel pour l'item
   * Utilisé comme clé dans les listes Vue pour optimiser le rendu
   * Si non fourni, une clé est générée depuis label + route
   */
  name?: string;
}

/**
 * Représente un item du menu utilisateur (dropdown profil)
 * 
 * Ces items sont affichés dans le menu dropdown accessible via l'icône
 * de compte dans la toolbar. Ils permettent d'accéder aux actions utilisateur
 * (changement de thème, déconnexion, etc.).
 * 
 * Gestion spéciale :
 * - L'item avec name='theme' affiche ThemeToggler au lieu d'un label simple
 * - Les items avec clickable=false ne sont pas cliquables mais peuvent avoir une action
 * 
 * Exemple :
 * ```typescript
 * const userMenuItem: UserMenuItem = {
 *   name: 'logout',
 *   label: () => i18n.t('auth.logout'),
 *   action: () => auth.methods.logout(),
 *   clickable: false,
 * };
 * ```
 */
export interface UserMenuItem {
  /** 
   * Label à afficher pour l'item de menu
   * Peut être une chaîne statique ou une fonction qui retourne une chaîne
   * (utile pour les labels traduits dynamiquement)
   */
  label: string | (() => string);
  
  /** 
   * Identifiant unique requis pour l'item
   * Utilisé comme clé dans les listes Vue et pour la gestion spéciale
   * (ex: 'theme' pour afficher ThemeToggler)
   */
  name: string;
  
  /** 
   * Fonction à exécuter lors du clic sur l'item
   * Si undefined, l'item n'a pas d'action (ex: item 'theme' qui affiche juste le toggle)
   */
  action?: () => void;
  
  /** 
   * Si false, l'item n'est pas cliquable (mais peut avoir une action)
   * Par défaut true si action est définie
   * Utile pour les items qui ont une action mais ne doivent pas être cliquables
   */
  clickable?: boolean;
  
  /** 
   * Classe CSS optionnelle à appliquer à l'item
   * Permet de personnaliser le style d'un item spécifique
   */
  class?: string;
}

