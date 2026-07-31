import { Routes } from '@angular/router';
import { Login } from './login/login';
import { Segmentation } from './segmentation/segmentation';
import { SalesOrder } from './sales-order/sales-order';
import { DemandForecast } from './demand-forecast/demand-forecast';
import { Dashboard } from './dashboard/dashboard';
import { Products } from './products/products';
import { authGuard } from './auth.guard';
import { loginGuard } from './login.guard';
import { Supplier } from './supplier/supplier';
import { Settings } from './settings/settings';

export const routes: Routes = [
  { path: 'login', component: Login, canActivate: [loginGuard] },
  { 
    path: '', 
    canActivate: [authGuard],
    children: [
      { path: 'segmentation', component: Segmentation },
      { path: 'sales-order', component: SalesOrder },
      { path: 'demand-forecast', component: DemandForecast },
      { path: 'dashboard', component: Dashboard },
      { path: 'products', component: Products },
      { path: 'settings', component: Settings },
      { path: '', redirectTo: 'dashboard', pathMatch: 'full' }
      ,{path:"supplier", component: Supplier}
    ]
  },
  { path: '**', redirectTo: '' }
];
