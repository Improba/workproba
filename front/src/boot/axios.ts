import axios, { AxiosInstance } from 'axios';
import { boot } from 'quasar/wrappers';

let API_SINGLETON: AxiosInstance | null = null;

function getBaseApiURL(): string {
  let apiUrl = `${process.env.API_URL}`;

  if (!apiUrl) {
    const w = window as any;
    const s = self as any;
    apiUrl = !s.__IS_WORKER ? w.__API_URL : s.__API_URL;
  }

  return apiUrl;
}

function getAxiosInstance() {
  // Return early if the singleton has already been initialized
  if (API_SINGLETON !== null) return API_SINGLETON;

  const baseURL = getBaseApiURL();

  // Be careful when using SSR for cross-request state pollution
  // due to creating a Singleton instance here;
  // If any client changes this (global) instance, it might be a
  // good idea to move this instance creation inside of the
  // "export default () => {}" function below (which runs individually
  // for each client)
  // console.log('boot/axios: apiUrl', apiUrl);
  API_SINGLETON = axios.create({
    baseURL,
    paramsSerializer(params) {
      const searchParams = new URLSearchParams();
      // Loop on each query param
      for (const key of Object.keys(params)) {
        // Query param and its value
        const param = params[key];
        // If the query param is an array then we need to transform it from:
        // [1,2,3] -> '1,2,3'
        if (Array.isArray(param)) {
          let arrayAsStr = '';
          // Loop on each entry in the array to put it into the str
          for (const p of param) {
            if (arrayAsStr.length > 0) {
              arrayAsStr += ',';
            }
            arrayAsStr += `${p}`;
          }
          searchParams.append(key, arrayAsStr);
        } else if (param !== undefined) {
          searchParams.append(key, param);
        }
      }
      return searchParams.toString();
    },
  });

  return API_SINGLETON;
}

export default boot(() => {
  // Before the root Vue app is instanciated, we create the singleton Axios instance.
  // Developpers can then import the 'api' function below to access the singleton instance.
  getAxiosInstance();
});

export const api = getAxiosInstance;
