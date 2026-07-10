import { api } from 'boot/axios';
import type {
  ILoginDTO,
  IRegisterDTO,
  IForgotPasswordDTO,
  IResetPasswordDTO,
} from '#types';

// Simple interface to share the token response type locally
interface ITokenResponse {
  token: string;
}

export const AuthService = {
  /**
   * Authentifie un utilisateur
   * @param {ILoginDTO} dto - Les identifiants de connexion
   * @returns {Promise<ITokenResponse>} Le token JWT et les informations de l'utilisateur
   */
  async login(dto: ILoginDTO): Promise<ITokenResponse> {
    const response = await api().post('/auth-jwt/login', dto);
    return response.data;
  },

  /**
   * Rafraîchit le token JWT
   * @param {string} token - Le token à rafraîchir
   * @returns {Promise<ITokenResponse>} Le nouveau token JWT
   */
  async refreshToken(token: string): Promise<ITokenResponse> {
    const response = await api().post('/auth-jwt/refreshToken', {
      token,
    });
    return response.data;
  },

  /**
   * Enregistre un nouvel utilisateur
   * @param {IRegisterDTO} dto - Les informations d'inscription
   * @returns {Promise<ITokenResponse>} L'utilisateur créé
   */
  async register(dto: IRegisterDTO): Promise<ITokenResponse> {
    const response = await api().post('/auth-jwt/register', dto);
    return response.data;
  },

  /**
   * Demande de réinitialisation de mot de passe
   * @param {IForgotPasswordDTO} dto - L'email de l'utilisateur
   * @returns {Promise<any>} Confirmation de l'envoi de l'email
   */
  async forgotPassword(dto: IForgotPasswordDTO): Promise<any> {
    const response = await api().post('/auth-jwt/forgot-password', dto);
    return response.data;
  },

  /**
   * Réinitialise le mot de passe avec le token reçu par email
   * @param {IResetPasswordDTO} dto - Le token et le nouveau mot de passe
   * @returns {Promise<ITokenResponse>} Confirmation de la réinitialisation
   */
  async resetPassword(dto: IResetPasswordDTO): Promise<ITokenResponse> {
    const response = await api().post('/auth-jwt/reset-password', dto);
    return response.data;
  },
};
