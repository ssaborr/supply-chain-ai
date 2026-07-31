import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Auth } from '../services/auth';
import { map, take, filter } from 'rxjs';

export const authGuard: CanActivateFn = (route, state) => {
  const auth = inject(Auth);
  const router = inject(Router);

  return auth.userState$.pipe(
    filter(user => user !== undefined),
    take(1),
    map(user => {
      if (!user) {
        router.navigate(['/login']);
        return false;
      }
      
      const path = state.url.split('/')[1]?.split('?')[0] || '';
      
      if (!path) {
        return true;
      }

      if (path === 'settings' && user.role !== 'admin') {
        const fallback = user.role === 'supplier' ? '/supplier' : '/dashboard';
        router.navigate([fallback]);
        return false;
      }
      
      if (user.role === 'admin') {
        if (path === 'supplier') {
          router.navigate(['/dashboard']);
          return false;
        }
        return true;
      }
      
      if (user.role === 'supplier') {
        if (path === 'supplier' || path === 'products') {
          return true;
        }
        router.navigate(['/supplier']);
        return false;
      }
      
      if (user.role === 'sub_admin') {
        if (user.allowed_tabs && user.allowed_tabs.includes(path)) {
          return true;
        }
        
        const firstAllowed = user.allowed_tabs && user.allowed_tabs.length > 0 ? user.allowed_tabs[0] : '';
        if (firstAllowed) {
          router.navigate(['/' + firstAllowed]);
        } else {
          auth.logout();
          router.navigate(['/login']);
        }
        return false;
      }
      
      return true;
    })
  );
};
