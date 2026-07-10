/**
 * This composable is used to handle the authentication for the application.
 * It is used to login, logout, refresh the token and to get the current user.
 *
 * Use case:
 * ```html
 * <template>
 *   <p>
 *     Token is: {{ auth.sharedState.token }}
 *     Username is: {{ auth.sharedState.user?.userJwt?.username ?? '-' }}
 *     Login date is: {{ auth.sharedState.loginDate }}
 *   </p>
 *
 *   <q-btn @click="auth.methods.logout"> Logout </q-btn>
 * </template>
 *
 * <script setup lang="ts">
 * import { useAuth } from '@lib-improba/composables/use-auth';
 * import { useRouter } from 'vue-router';
 *
 * const router = useRouter()
 * const auth = useAuth();
 * </script>
 * ```
 */
import { reactive } from 'vue';
import { Cookies } from 'quasar';
import { Router } from 'vue-router';
import { AuthService } from '@services/users/auth.service';
import { UserService } from '@services/users/user.service';
import { init as initAxios } from './axios';
import { init as initRouter } from './router';
import { EUserRole, IUser, ILoginDTO } from '#types';
import { HOME_ROUTE } from '@router/meta';

// ==================== CONSTANTS & TYPES ====================
const COOKIE_NAME = process.env.APP_NAME || 'auth-token';
const COOKIE_EXPIRY_DAYS = process.env.JWT_COOKIE_EXPIRES_IN || 30;

interface QuasarCookieOptions {
  expires?: number | string | Date;
  path?: string;
  domain?: string;
  sameSite?: 'Lax' | 'Strict' | 'None';
  httpOnly?: boolean;
  secure?: boolean;
  other?: string;
}

const cookieOptions: QuasarCookieOptions = {
  expires: COOKIE_EXPIRY_DAYS,
  path: '/',
  sameSite: 'Lax',
};

interface ISharedState {
  user: IUser | null;
  loginDate: Date | null;
  token: string | null;
}

interface IUseAuthMethods {
  refreshToken: () => Promise<string>;
  isLoggedIn: () => boolean;
  hasAnyRole: (roles: EUserRole[]) => boolean;
  login: (dto: ILoginDTO) => Promise<void>;
  logout: () => void;
  init: () => Promise<void>;
}

export interface IUseAuth {
  sharedState: ISharedState;
  methods: IUseAuthMethods;
}

// ==================== SHARED STATE ====================
const sharedState: ISharedState = reactive({
  user: null,
  loginDate: null,
  token: null,
});

// ==================== COOKIE & TOKEN MANAGEMENT ====================
/**
 * Retrieves the authentication token from cookies
 * @returns The token string if found, null otherwise
 */
function getTokenFromCookie(): string | null {
  const tokenFromCookie = Cookies.get(COOKIE_NAME);
  return tokenFromCookie || null;
}

/**
 * Saves the token to cookies and shared state
 * @param token - The JWT token to save
 */
function setCookiesWithToken(token: string) {
  Cookies.set(COOKIE_NAME, token, cookieOptions);
  sharedState.token = token;
}

/**
 * Removes the token from cookies
 */
function removeTokenFromCookies() {
  Cookies.remove(COOKIE_NAME, cookieOptions);
}

// ==================== USER STATE MANAGEMENT ====================
/**
 * Fetches the current user and updates the shared state
 */
async function getAndSetCurrentUser() {
  const user = await UserService.getCurrentUser();
  sharedState.loginDate = new Date();
  sharedState.user = user;
}

/**
 * Clears the user session (state and cookies)
 */
function clearUserSession() {
  sharedState.user = null;
  sharedState.token = null;
  sharedState.loginDate = null;
  removeTokenFromCookies();
}

// ==================== COMPOSABLE EXPORT ====================
export const useAuth = (router: Router): IUseAuth => {
  const methods = {
    /**
     * Refreshes the authentication token and updates the session
     * @returns The new JWT token
     * @throws Error if refresh fails
     */
    async refreshToken() {
      const currentToken = sharedState.token;

      if (!currentToken) {
        throw new Error('No token to refresh');
      }

      const { token } = await AuthService.refreshToken(currentToken);
      setCookiesWithToken(token);

      await getAndSetCurrentUser();

      return token;
    },

    /**
     * Checks if a user is currently logged in
     * @returns True if a user session exists, false otherwise
     */
    isLoggedIn() {
      return sharedState.user != null;
    },

    /**
     * Checks if the current user has any of the specified roles
     * @param roles - One or more roles to check against
     * @returns True if the user is logged in and has any of the specified roles
     */
    hasAnyRole(roles: EUserRole[]) {
      const user = sharedState.user;

      // User is not logged in
      if (!user) return false;

      return roles.some((role) => {
        return user.roles.find((userRole) => userRole === role);
      });
    },

    /**
     * Logs in a user with username and password
     * @param dto - The login credentials
     */
    async login(dto: ILoginDTO) {
      const userLogin = await AuthService.login(dto);

      setCookiesWithToken(userLogin.token);

      await getAndSetCurrentUser();

      // Handle post-login redirect
      const currentRoute = router.currentRoute.value;
      const redirectPath = currentRoute.query.redirect as string;

      if (redirectPath) {
        router.push(redirectPath);
      } else {
        router.push({ name: HOME_ROUTE });
      }
    },

    /**
     * Logs out the current user and redirects to login page
     */
    logout() {
      clearUserSession();
      router.push({ name: 'auth-login' });
    },

    /**
     * Initializes the authentication system
     * - Initializes axios interceptors (auto-inject token + logout on 401)
     * - Attempts to refresh token if a cookie exists
     * - Initializes router guards (will handle redirect if no session)
     */
    init: async () => {
      // Initializes axios first to ensure the interceptors are ready
      await initAxios({ sharedState, methods });

      // Check if a token cookie exists
      if (Cookies.has(COOKIE_NAME)) {
        const currentToken = getTokenFromCookie();

        if (currentToken) {
          sharedState.token = currentToken;

          try {
            // Attempt to refresh the token to ensure it's valid and fresh
            await methods.refreshToken();
            console.log('Token refreshed successfully during initialization');
          } catch (err) {
            // Token refresh failed - clear session silently
            // Router will handle redirect to login if needed
            clearUserSession();
            console.warn('Token refresh failed during initialization:', err);
          }
        }
      }

      // If no cookie exists, do nothing - router guard will handle redirect
      initRouter(router, { sharedState, methods });
    },
  };

  return {
    sharedState,
    methods,
  };
};
