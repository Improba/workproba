import { api } from 'boot/axios';
import type {
  IUser,
  IUpdateCurrentUserDTO,
} from '#types';

export const UserService = {
  /**
   * Récupère les informations de l'utilisateur connecté
   * @returns {Promise<IUser>} Les informations de l'utilisateur
   */
  async getCurrentUser(): Promise<IUser> {
    const response = await api().get('/users/current');
    return response.data;
  },

  /**
   * Met à jour les informations de l'utilisateur connecté
   * @param {IUpdateCurrentUserDTO} dto - Les données à mettre à jour
   * @returns {Promise<IUser>} L'utilisateur mis à jour
   */
  async updateCurrentUser(dto: IUpdateCurrentUserDTO): Promise<IUser> {
    const response = await api().patch('/users/current', dto);
    return response.data;
  },
};
