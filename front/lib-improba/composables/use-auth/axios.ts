import { AxiosError } from 'axios';
import { api } from 'boot/axios';
import { IUseAuth } from '.';

/**
 * URLs that should not trigger an automatic logout when receiving a 401 error
 * These are typically login/auth endpoints where 401 is expected
 */
const URLS_SKIP_AUTO_LOGOUT: string[] = ['/login', '/refreshToken'];

/**
 * Checks if a URL ends with any of the provided URL patterns
 * @param url - The URL to check
 * @param patterns - Array of URL patterns to match against
 * @returns True if the URL matches any pattern
 */
function isUrlInList(url: string, patterns: string[]): boolean {
  return patterns.some((pattern) => url.endsWith(pattern));
}

// ==================== AXIOS INITIALIZATION ====================
/**
 * Initializes axios interceptors for authentication handling
 *
 * Request Interceptor:
 * - Automatically injects the authentication token from sharedState if present
 *
 * Response Interceptor:
 * - On 401 error: Logs out user automatically and redirects to login
 * - Skips auto-logout for specific auth-related URLs
 *
 * Note: Token refresh is handled during app initialization (see use-auth/index.ts)
 *
 * @param auth - The authentication composable instance
 */
export const init = async (auth: IUseAuth): Promise<void> => {
  const axiosInstance = api();

  // ==================== REQUEST INTERCEPTOR ====================
  // Automatically inject authentication token if present
  axiosInstance.interceptors.request.use(
    (config) => {
      // Check if token exists in shared state
      const token = auth.sharedState.token;

      if (token) {
        // Add Authorization header with Bearer token
        config.headers.Authorization = `Bearer ${token}`;
      }

      return config;
    },
    (error) => {
      // Request error - pass through
      return Promise.reject(error);
    }
  );

  // ==================== RESPONSE INTERCEPTOR ====================
  // Handles 401 errors with automatic logout
  axiosInstance.interceptors.response.use(
    (response) => {
      // Success - pass through
      return response;
    },
    async (error: AxiosError) => {
      // Check if this is a 401 Unauthorized error
      const is401Error = error.response?.status === 401;

      if (is401Error && error.request?.responseURL) {
        // Check if we should skip auto-logout for this URL
        const shouldLogout = !isUrlInList(
          error.request.responseURL,
          URLS_SKIP_AUTO_LOGOUT
        );

        if (shouldLogout) {
          console.warn('Authentication failed (401) - logging out user');
          auth.methods.logout();
        }
      }

      return Promise.reject(error);
    }
  );
};
