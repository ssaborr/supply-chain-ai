import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth } from '../services/auth';
import { map, take, filter } from 'rxjs';

export const loginGuard: CanActivateFn = (route, state) => {
  const auth = inject(Auth);
  const router = inject(Router);

  return auth.userState$.pipe(
    filter(user => user !== undefined),
    take(1),
    map(user => {
      if (user) {
        // If user is already logged in, redirect them to their respective dashboard
        if (user.role === 'supplier') {
          router.navigate(['/supplier']);
        } else {
          router.navigate(['/']);
        }
        return false;
      }
      return true;
    })
  );
};
