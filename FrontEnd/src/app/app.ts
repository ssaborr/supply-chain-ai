import { Component, inject, signal } from '@angular/core';
import { RouterOutlet, RouterLink, RouterLinkActive, Router } from '@angular/router';
import { Auth, UserState } from '../services/auth';
import { AsyncPipe, CommonModule } from '@angular/common';
import { ChatbotWidget } from './chatbot-widget/chatbot-widget';
import { DisplayDatePipe } from '../pipes/display-date.pipe';
import { HttpClient } from '@angular/common/http';
import { I18nService } from '../services/i18n';
import { TranslatePipe } from '../pipes/translate.pipe';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, AsyncPipe, CommonModule, ChatbotWidget, DisplayDatePipe, TranslatePipe],
  templateUrl: './app.html',
  styleUrl: './app.css'
})
export class App {
  constructor() {
    console.log('[App] root component loaded');
    this.auth.userState$.subscribe(user => {
      this.currentUser = user || null;
      this.searchQuery.set('');
      this.searchResults = [];
      this.searchCache = [];
      this.searchCacheMode = null;
      this.showDropdown.set(false);
    });
  }

  protected readonly title = signal('FrontEnd');
  public auth = inject(Auth);
  public i18n = inject(I18nService);
  private router = inject(Router);
  private http = inject(HttpClient);

  public searchQuery = signal('');
  public searchResults: any[] = [];
  private searchCache: any[] = [];
  private searchCacheMode: 'orders' | 'products' | null = null;
  public currentUser: UserState | null = null;
  public showDropdown = signal(false);

  get isSupplierSearch(): boolean {
    return this.currentUser?.role === 'supplier';
  }

  fetchSearchData(): void {
    const token = this.auth.getToken();
    if (!token) return;
    const headers = { 'Authorization': `Bearer ${token}` };
    const mode = this.isSupplierSearch ? 'products' : 'orders';
    const url = this.isSupplierSearch
      ? '/api/products'
      : '/api/orders';

    this.http.get<any[]>(url, { headers }).subscribe({
      next: (data) => {
        this.searchCache = data;
        this.searchCacheMode = mode;
        this.filterSearchResults();
      },
      error: (err) => console.error('[App] Failed to fetch header search data:', err)
    });
  }

  onSearchInput(event: any): void {
    this.searchQuery.set(event.target.value);
    if (!this.searchQuery()) {
      this.searchResults = [];
      this.showDropdown.set(false);
      return;
    }
    const mode = this.isSupplierSearch ? 'products' : 'orders';
    if (this.searchCache.length === 0 || this.searchCacheMode !== mode) {
      this.fetchSearchData();
    } else {
      this.filterSearchResults();
    }
  }

  filterSearchResults(): void {
    const q = this.searchQuery().toLowerCase().trim();
    if (!q) {
      this.searchResults = [];
      this.showDropdown.set(false);
      return;
    }

    if (this.isSupplierSearch) {
      this.searchResults = this.searchCache.filter(p =>
        p.sku?.toString().includes(q) ||
        p.name?.toLowerCase().includes(q) ||
        p.category?.toLowerCase().includes(q) ||
        p.cluster?.toLowerCase().includes(q)
      ).slice(0, 8);
    } else {
      this.searchResults = this.searchCache.filter(o =>
        o.id.toString().includes(q) ||
        (o.client_id && o.client_id.toLowerCase().includes(q))
      ).slice(0, 8);
    }

    this.showDropdown.set(this.searchResults.length > 0);
  }

  selectSearchResult(result: any): void {
    if (this.isSupplierSearch) {
      this.router.navigate(['/products'], { queryParams: { sku: result.sku } });
    } else {
      this.router.navigate(['/sales-order'], { queryParams: { orderId: result.id } });
    }

    this.searchQuery.set('');
    this.searchResults = [];
    this.showDropdown.set(false);
    
    const inputEl = document.querySelector('.search-bar input') as HTMLInputElement;
    if (inputEl) {
      inputEl.value = '';
    }
  }

  closeDropdown(): void {
    setTimeout(() => {
      this.showDropdown.set(false);
    }, 200);
  }

  onLogout(): void {
    this.auth.logout();
    this.router.navigate(['/login']);
  }

  toggleLanguage(): void {
    this.i18n.toggleLanguage();
    if (typeof window !== 'undefined') {
      window.location.reload();
    }
  }
}
