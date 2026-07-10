import { Router } from 'vue-router';
import { IUseAuth } from '.';

/** Application bureau : pas d'authentification JWT. */
export const init = (router: Router, _auth: IUseAuth) => {
  router.beforeEach((_to, _from, next) => {
    next();
  });
};
