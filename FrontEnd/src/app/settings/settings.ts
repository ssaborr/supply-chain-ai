import { Component, OnInit, inject, ElementRef, ViewChild, ChangeDetectorRef, OnDestroy } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth } from '../../services/auth';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { I18nService } from '../../services/i18n';

export interface UserItem {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  supplier_name?: string;
  allowed_tabs?: string[];
  has_face_enrolled: boolean;
}

@Component({
  selector: 'app-settings',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslatePipe],
  templateUrl: './settings.html',
  styleUrl: './settings.css',
})
export class Settings implements OnInit, OnDestroy {
  private http = inject(HttpClient);
  public auth = inject(Auth);
  private cdr = inject(ChangeDetectorRef);
  private i18n = inject(I18nService);

  @ViewChild('webcamVideo') webcamVideo!: ElementRef<HTMLVideoElement>;

  public users: UserItem[] = [];
  public isLoading: boolean = true;
  public errorMessage: string = '';
  public successMessage: string = '';

  public newUser = {
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    role: 'sub_admin',
    supplier_name: '',
    allowed_tabs: {
      dashboard: true,
      'sales-order': true,
      'demand-forecast': true,
      segmentation: false,
      products: true,
      settings: false,
    } as { [key: string]: boolean }
  };

  public activeEnrollUser: UserItem | null = null;
  public isCameraActive: boolean = false;
  public cameraStream: MediaStream | null = null;
  public isProcessingFace: boolean = false;
  public faceScanError: string = '';
  public faceScanSuccess: string = '';

  public loggedInUser: UserItem | null = null;

  public products: any[] = [];
  public paginatedProducts: any[] = [];
  public settingsProductSearch: string = '';
  public productPage: number = 1;
  public productPageSize: number = 5;
  public isTrainingModel: boolean = false;

  public tabList = [
    { id: 'dashboard', labelKey: 'nav.dashboard' },
    { id: 'sales-order', labelKey: 'nav.salesOrder' },
    { id: 'demand-forecast', labelKey: 'nav.demandForecasting' },
    { id: 'segmentation', labelKey: 'nav.partnerSegmentation' },
    { id: 'products', labelKey: 'nav.inventory' },
    { id: 'settings', labelKey: 'nav.systemSettings' }
  ];

  ngOnInit(): void {
    this.loadUsers();
    this.loadProducts();
    this.auth.userState$.subscribe(user => {
      this.loggedInUser = user as any;
    });
  }

  ngOnDestroy(): void {
    this.stopCamera();
  }

  loadUsers(): void {
    this.isLoading = true;
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.get<UserItem[]>('/api/admins/', { headers }).subscribe({
      next: (data) => {
        this.users = data;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to load users', err);
        this.errorMessage = 'Failed to load users list from server.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  createUser(): void {
    this.errorMessage = '';
    this.successMessage = '';

    const allowedTabsList: string[] = [];
    if (this.newUser.role === 'admin') {
      allowedTabsList.push(...this.tabList.map(t => t.id));
    } else if (this.newUser.role === 'supplier') {
      allowedTabsList.push('supplier', 'products');
    } else {
      Object.keys(this.newUser.allowed_tabs).forEach(key => {
        if (this.newUser.allowed_tabs[key]) {
          allowedTabsList.push(key);
        }
      });
    }

    const payload = {
      email: this.newUser.email.trim(),
      first_name: this.newUser.first_name.trim(),
      last_name: this.newUser.last_name.trim(),
      password: this.newUser.password,
      role: this.newUser.role,
      supplier_name: this.newUser.role === 'supplier' ? this.newUser.supplier_name.trim() : null,
      allowed_tabs: allowedTabsList
    };

    if (!payload.email || !payload.first_name || !payload.last_name || !payload.password) {
      this.errorMessage = 'All fields are required to create a user.';
      return;
    }

    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.post('/api/admins/', payload, { headers }).subscribe({
      next: () => {
        this.successMessage = `User ${payload.first_name} created successfully.`;
        this.loadUsers();
        this.newUser.email = '';
        this.newUser.first_name = '';
        this.newUser.last_name = '';
        this.newUser.password = '';
        this.newUser.supplier_name = '';
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to create user', err);
        this.errorMessage = err.error?.detail || 'Failed to create user. Make sure email is unique.';
        this.cdr.detectChanges();
      }
    });
  }

  deleteUser(userId: string): void {
    if (!confirm('Are you sure you want to delete this user?')) return;

    this.errorMessage = '';
    this.successMessage = '';
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.delete(`/api/admins/${userId}`, { headers }).subscribe({
      next: () => {
        this.successMessage = 'User deleted successfully.';
        this.loadUsers();
      },
      error: (err) => {
        console.error('Failed to delete user', err);
        this.errorMessage = err.error?.detail || 'Failed to delete user.';
        this.cdr.detectChanges();
      }
    });
  }

  openEnrollmentScanner(user: UserItem): void {
    this.faceScanError = '';
    this.faceScanSuccess = '';
    this.activeEnrollUser = user;
    this.startCamera();
  }

  closeEnrollmentScanner(): void {
    this.stopCamera();
    this.activeEnrollUser = null;
    this.faceScanError = '';
    this.faceScanSuccess = '';
    this.cdr.detectChanges();
  }

  startCamera(): void {
    this.isCameraActive = false;
    this.faceScanError = '';
    
    navigator.mediaDevices.getUserMedia({
      video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' }
    }).then(stream => {
      this.cameraStream = stream;
      this.isCameraActive = true;
      this.cdr.detectChanges();

      setTimeout(() => {
        if (this.webcamVideo && this.webcamVideo.nativeElement) {
          this.webcamVideo.nativeElement.srcObject = stream;
          this.webcamVideo.nativeElement.play().catch(err => {
            console.error('Error playing webcam feed:', err);
          });
        }
      }, 100);
    }).catch(err => {
      console.error('Failed to open webcam:', err);
      this.faceScanError = 'Could not access webcam. Please verify device permissions.';
      this.cdr.detectChanges();
    });
  }

  stopCamera(): void {
    if (this.cameraStream) {
      this.cameraStream.getTracks().forEach(track => track.stop());
      this.cameraStream = null;
    }
    this.isCameraActive = false;
  }

  captureAndEnroll(): void {
    if (!this.activeEnrollUser || !this.webcamVideo || !this.isCameraActive) return;

    this.isProcessingFace = true;
    this.faceScanError = '';
    this.faceScanSuccess = '';
    this.cdr.detectChanges();

    const videoEl = this.webcamVideo.nativeElement;
    const canvas = document.createElement('canvas');
    canvas.width = videoEl.videoWidth || 640;
    canvas.height = videoEl.videoHeight || 480;

    const ctx = canvas.getContext('2d');
    if (!ctx) {
      this.faceScanError = 'Failed to generate 2D canvas context.';
      this.isProcessingFace = false;
      return;
    }

    ctx.drawImage(videoEl, 0, 0, canvas.width, canvas.height);
    const base64Data = canvas.toDataURL('image/jpeg', 0.9);

    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    const payload = { image: base64Data };

    this.http.post<UserItem>(
      `/api/admins/${this.activeEnrollUser.id}/enroll-face`,
      payload,
      { headers }
    ).subscribe({
      next: (updatedUser) => {
        this.faceScanSuccess = 'Face scanned and enrolled successfully!';
        this.isProcessingFace = false;
        
        const idx = this.users.findIndex(u => u.id === updatedUser.id);
        if (idx !== -1) {
          this.users[idx] = updatedUser;
        }
        
        this.cdr.detectChanges();
        // peace out, face scanned successfully, shutting down cam
        setTimeout(() => {
          this.closeEnrollmentScanner();
        }, 1500);
      },
      error: (err) => {
        console.error('Face enrollment failed:', err);
        this.faceScanError = err.error?.detail || 'Face registration failed. Please ensure your face is well-lit and fully visible.';
        this.isProcessingFace = false;
        this.cdr.detectChanges();
      }
    });
  }

  clearUserFace(userId: string): void {
    if (!confirm('Are you sure you want to remove all enrolled face scans for this user?')) return;

    this.errorMessage = '';
    this.successMessage = '';
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.delete<UserItem>(`/api/admins/${userId}/enroll-face`, { headers }).subscribe({
      next: (updatedUser) => {
        this.successMessage = 'Face scans cleared successfully.';
        const idx = this.users.findIndex(u => u.id === updatedUser.id);
        if (idx !== -1) {
          this.users[idx] = updatedUser;
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to clear face scans', err);
        this.errorMessage = err.error?.detail || 'Failed to clear face scans.';
        this.cdr.detectChanges();
      }
    });
  }

  getRolesLabel(role: string): string {
    if (role === 'admin') return this.i18n.t('settings.adminRole').toUpperCase();
    if (role === 'sub_admin') return this.i18n.t('settings.subAdminRole').toUpperCase();
    if (role === 'supplier') return this.i18n.t('profile.supplier');
    return role.toUpperCase();
  }

  getFormattedTabs(user: UserItem): string {
    if (user.role === 'admin') return this.i18n.t('settings.adminRole');
    if (user.role === 'supplier') return `${this.i18n.t('nav.supplierDashboard')}, ${this.i18n.t('nav.inventory')}`;
    if (!user.allowed_tabs || user.allowed_tabs.length === 0) return 'No Access';
    return user.allowed_tabs.map(t => {
      const match = this.tabList.find(item => item.id === t);
      return match ? this.i18n.t(match.labelKey) : t;
    }).join(', ');
  }

  loadProducts(): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.get<any[]>('/api/products', { headers }).subscribe({
      next: (data) => {
        this.products = data.map(p => ({
          ...p,
          prep_delay: p.prep_delay !== undefined ? p.prep_delay : 4,
          internal_delay: p.internal_delay !== undefined ? p.internal_delay : 0,
          transport_delay: p.transport_delay !== undefined ? p.transport_delay : 0,
          isSaving: false
        }));
        this.updatePaginatedProducts();
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to load products', err);
        this.cdr.detectChanges();
      }
    });
  }

  updatePaginatedProducts(): void {
    const query = this.settingsProductSearch.trim().toLowerCase();
    const filtered = this.products.filter(p => 
      p.name.toLowerCase().includes(query) || 
      p.sku.toString().includes(query)
    );
    const start = (this.productPage - 1) * this.productPageSize;
    this.paginatedProducts = filtered.slice(start, start + this.productPageSize);
  }

  onProductSearch(): void {
    this.productPage = 1;
    this.updatePaginatedProducts();
  }

  prevProductPage(): void {
    if (this.productPage > 1) {
      this.productPage--;
      this.updatePaginatedProducts();
    }
  }

  nextProductPage(): void {
    const query = this.settingsProductSearch.trim().toLowerCase();
    const filteredCount = this.products.filter(p => 
      p.name.toLowerCase().includes(query) || 
      p.sku.toString().includes(query)
    ).length;
    if (this.productPage * this.productPageSize < filteredCount) {
      this.productPage++;
      this.updatePaginatedProducts();
    }
  }

  saveProductDelays(product: any): void {
    product.isSaving = true;
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    const payload = {
      prep_delay: parseInt(product.prep_delay) || 0,
      internal_delay: parseInt(product.internal_delay) || 0,
      transport_delay: parseInt(product.transport_delay) || 0
    };

    this.http.put(`/api/products/${product.sku}/delays`, payload, { headers }).subscribe({
      next: () => {
        product.isSaving = false;
        const idx = this.products.findIndex(p => p.sku === product.sku);
        if (idx !== -1) {
          this.products[idx].prep_delay = payload.prep_delay;
          this.products[idx].internal_delay = payload.internal_delay;
          this.products[idx].transport_delay = payload.transport_delay;
        }
        this.successMessage = `Delays for product SKU ${product.sku} updated successfully.`;
        this.cdr.detectChanges();
        
        setTimeout(() => {
          this.successMessage = '';
          this.cdr.detectChanges();
        }, 3000);
      },
      error: (err) => {
        console.error('Failed to save product delays', err);
        product.isSaving = false;
        this.errorMessage = `Failed to save product delays for SKU ${product.sku}.`;
        this.cdr.detectChanges();
      }
    });
  }

  trainDelayModel(): void {
    this.isTrainingModel = true;
    this.errorMessage = '';
    this.successMessage = '';
    this.cdr.detectChanges();

    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.post<any>('/api/products/train-delays', {}, { headers }).subscribe({
      next: (resp) => {
        this.isTrainingModel = false;
        this.successMessage = resp.message || 'Delay prediction model trained successfully!';
        this.loadProducts();
        this.cdr.detectChanges();

        setTimeout(() => {
          this.successMessage = '';
          this.cdr.detectChanges();
        }, 5000);
      },
      error: (err) => {
        console.error('Failed to train delay model', err);
        this.isTrainingModel = false;
        this.errorMessage = err.error?.detail || 'Failed to train delay prediction model.';
        this.cdr.detectChanges();
      }
    });
  }

  getGeneralAdjustmentText(p: any): string {
    if (p.rec_prep_delay === undefined || p.rec_prep_delay === null) {
      return '';
    }
    const currTotal = (parseInt(p.prep_delay) || 0) + (parseInt(p.internal_delay) || 0) + (parseInt(p.transport_delay) || 0);
    const recTotal = p.rec_prep_delay + p.rec_internal_delay + p.rec_transport_delay;
    const diff = recTotal - currTotal;
    
    if (diff > 0) {
      return `Raise by ${diff} day${diff > 1 ? 's' : ''}`;
    } else if (diff < 0) {
      const absDiff = Math.abs(diff);
      return `Lower by ${absDiff} day${absDiff > 1 ? 's' : ''}`;
    } else {
      return 'Optimal (No change)';
    }
  }

  getGeneralAdjustmentColor(p: any): string {
    if (p.rec_prep_delay === undefined || p.rec_prep_delay === null) {
      return '#64748b';
    }
    const currTotal = (parseInt(p.prep_delay) || 0) + (parseInt(p.internal_delay) || 0) + (parseInt(p.transport_delay) || 0);
    const recTotal = p.rec_prep_delay + p.rec_internal_delay + p.rec_transport_delay;
    const diff = recTotal - currTotal;
    
    if (diff > 0) return '#d97706'; // target delivery is too slow, pump up the buffer
    if (diff < 0) return '#16a34a'; // package is arriving fast, trim the fat
    return '#64748b'; // dynamic duo matches perfectly, zero change needed
  }
}
