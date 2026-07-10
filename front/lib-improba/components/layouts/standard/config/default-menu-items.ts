/**
 * Configuration des items de menu par défaut pour le layout standard
 * 
 * Ce fichier exporte la liste des items de menu qui seront affichés
 * dans la toolbar de navigation si aucun menuItems personnalisé n'est fourni.
 * 
 * Par défaut, cette liste est vide. Les projets peuvent :
 * - Ajouter des items ici pour un menu global
 * - Fournir des items personnalisés via la prop menuItems de StandardLayout
 * 
 * Note : Le menu "Admin" est ajouté automatiquement par StandardLayout
 * si l'utilisateur a le rôle ADMIN, même si cette liste est vide.
 * 
 * Exemple d'utilisation :
 * ```typescript
 * export const defaultMenuItems: MenuItem[] = [
 *   {
 *     name: 'home',
 *     label: 'Accueil',
 *     route: { name: 'home' },
 *   },
 *   {
 *     name: 'about',
 *     label: 'À propos',
 *     route: { name: 'about' },
 *   },
 * ];
 * ```
 */
import type { MenuItem } from '../types/menu-item.types';

/**
 * Items de menu par défaut pour le layout standard
 * 
 * Cette liste est utilisée si aucun menuItems n'est fourni en props.
 * Par défaut vide, elle peut être étendue selon les besoins du projet.
 */
export const defaultMenuItems: MenuItem[] = [];

