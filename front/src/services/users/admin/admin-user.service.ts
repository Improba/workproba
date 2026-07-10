import { api } from 'boot/axios';
import type { IUser, IAdminCreateUserDTO, IAdminUpdateUserDTO } from '#types';
import { IPaginationResponse } from '#types/pagination';
import { IPaginateUserDTO } from '#types/user/dto/paginate-user.dto';

export const AdminUserService = {
  /**
   * Récupère les utilisateurs avec pagination
   * @param {IPaginateUserDTO} params - Options de pagination et filtres
   * @returns {Promise<IPaginationResponse<IUser>>} Liste paginée des utilisateurs
   */
  async paginate(params: IPaginateUserDTO): Promise<IPaginationResponse<IUser>> {
    const response = await api().get<IPaginationResponse<IUser>>(
      '/users-admin/paginate',
      { params }
    );
    return response.data;
  },

  /**
   * Crée un nouvel utilisateur (admin)
   * @param {IAdminCreateUserDTO} dto - Les informations de l'utilisateur à créer
   * @returns {Promise<IUser>} L'utilisateur créé
   */
  async create(dto: IAdminCreateUserDTO): Promise<IUser> {
    const response = await api().post('/users-admin', dto);
    return response.data;
  },

  /**
   * Modifie un utilisateur (admin)
   * @param {IAdminUpdateUserDTO} dto - Les informations de l'utilisateur à modifier
   * @returns {Promise<IUser>} L'utilisateur modifié
   */
  async update(dto: IAdminUpdateUserDTO): Promise<IUser> {
    const response = await api().patch('/users-admin', dto);
    return response.data;
  },

  /**
   * Récupère un utilisateur par son ID (admin)
   * @param {number} id - L'ID de l'utilisateur à récupérer
   * @returns {Promise<IUser>} L'utilisateur trouvé
   */
  async findOne(id: number): Promise<IUser> {
    const response = await api().get<IUser>(`/users-admin/${id}`);
    return response.data;
  },

  /**
   * Supprime un utilisateur (admin)
   * @param {number} id - L'ID de l'utilisateur à supprimer
   * @returns {Promise<IUser>} Confirmation de la suppression
   */
  async delete(id: number): Promise<IUser> {
    const response = await api().delete(`/users-admin/${id}`);
    return response.data;
  },
};
