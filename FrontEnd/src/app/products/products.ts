import { Component, OnInit, inject, ElementRef, ViewChild, AfterViewInit, ChangeDetectorRef } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth } from '../../services/auth';
import { Chart } from 'chart.js/auto';
import { ActivatedRoute } from '@angular/router';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { I18nService } from '../../services/i18n';

export interface ProductCluster {
  sku: number;
  name: string;
  price: number;
  monthly_volume: number;
  cluster: string;
  current_stock: number;
}

@Component({
  selector: 'app-products',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslatePipe],
  templateUrl: './products.html',
  styleUrl: './products.css',
})
export class Products implements OnInit, AfterViewInit {
  private http = inject(HttpClient);
  public auth = inject(Auth);
  private cdr = inject(ChangeDetectorRef);
  private route = inject(ActivatedRoute);
  private i18n = inject(I18nService);

  @ViewChild('clusteringChartCanvas') clusteringChartCanvas!: ElementRef<HTMLCanvasElement>;
  private chart: Chart | null = null;

  public products: any[] = [];
  public isLoading: boolean = true;

  public highValuePct: number = 25;
  public volumeDriversPct: number = 25;
  public lowPerformersPct: number = 50;
  public aiSummary: string = 'Generating executive AI narrative summary...';

  public tableSearchQuery: string = '';
  public currentPage: number = 1;
  public pageSize: number = 10;
  public highlightedSku: number | null = null;
  public showCreateModal: boolean = false;
  public isSubmitting: boolean = false;
  public errorMessage: string = '';
  public newProduct: any = { sku: null, name: '', category: '', price: null, discountPercent: 0, current_stock: null, department_id: '', image: null };
  public allCategories: string[] = [];
  public allDepartments: any[] = [];
  public filteredCategories: string[] = [];
  public filteredDepartments: any[] = [];
  public showCategorySuggestions: boolean = false;
  public showDeptSuggestions: boolean = false;
  public departmentSearchText: string = '';

  get filteredProductsTable(): any[] {
    const query = this.tableSearchQuery.trim().toLowerCase();
    if (!query) return this.products;

    return this.products.filter(p => 
      p.sku.toString().includes(query) ||
      p.name.toLowerCase().includes(query) ||
      p.category.toLowerCase().includes(query) ||
      (p.cluster && p.cluster.toLowerCase().includes(query))
    );
  }

  get paginatedProducts(): any[] {
    const startIndex = (this.currentPage - 1) * this.pageSize;
    return this.filteredProductsTable.slice(startIndex, startIndex + this.pageSize);
  }

  nextPage(): void {
    if (this.currentPage * this.pageSize < this.filteredProductsTable.length) {
      this.currentPage++;
      this.cdr.detectChanges();
    }
  }

  prevPage(): void {
    if (this.currentPage > 1) {
      this.currentPage--;
      this.cdr.detectChanges();
    }
  }

  getDisplayStartIndex(): number {
    if (this.filteredProductsTable.length === 0) return 0;
    return (this.currentPage - 1) * this.pageSize + 1;
  }

  getDisplayEndIndex(): number {
    return Math.min(this.currentPage * this.pageSize, this.filteredProductsTable.length);
  }

  onTableSearchChange(): void {
    this.currentPage = 1;
    this.highlightedSku = null;
    this.cdr.detectChanges();
  }

  ngOnInit(): void {
    this.route.queryParamMap.subscribe(params => {
      const sku = params.get('sku');
      this.highlightedSku = sku ? parseInt(sku, 10) : null;
      this.applyHighlightedProduct();
    });
    this.loadProductClusters();
    this.loadAiSummary();
    this.loadCategoriesAndDepartments();
  }

  ngAfterViewInit(): void {
  }

  loadProductClusters(): void {
    this.isLoading = true;
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.get<any[]>('http://127.0.0.1:8000/api/products/clusters', { headers }).subscribe({
      next: (data) => {
        this.products = data.map((p) => ({
          ...p,
          image: this.normalizeImageUrl(p.image) || this.getProductFallbackImage(p.name, 'mini')
        }));
        this.isLoading = false;
        
        const total = data.length;
        const highValueCount = data.filter(p => p.cluster === 'HIGH VALUE').length;
        const volumeDriversCount = data.filter(p => p.cluster === 'VOLUME DRIVERS').length;
        const lowPerformersCount = data.filter(p => p.cluster === 'LOW PERFORMERS').length;

        this.highValuePct = total ? Math.round((highValueCount / total) * 100) : 0;
        this.volumeDriversPct = total ? Math.round((volumeDriversCount / total) * 100) : 0;
        this.lowPerformersPct = total
          ? Math.max(0, 100 - this.highValuePct - this.volumeDriversPct)
          : 0;
        
        this.applyHighlightedProduct();
        setTimeout(() => this.initChart(), 0);
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to load product clusters', err);
        this.isLoading = false;
        this.products = [
          { sku: 1001, name: 'Sample High Value 1', price: 1500, monthly_volume: 66, cluster: 'HIGH VALUE' },
          { sku: 1002, name: 'Sample High Value 2', price: 1480, monthly_volume: 72, cluster: 'HIGH VALUE' },
          { sku: 2001, name: 'Sample Volume Driver 1', price: 70, monthly_volume: 1200, cluster: 'VOLUME DRIVERS' },
          { sku: 2002, name: 'Sample Volume Driver 2', price: 65, monthly_volume: 1400, cluster: 'VOLUME DRIVERS' },
          { sku: 3001, name: 'Sample Low Performer 1', price: 120, monthly_volume: 30, cluster: 'LOW PERFORMERS' },
          { sku: 3002, name: 'Sample Low Performer 2', price: 150, monthly_volume: 45, cluster: 'LOW PERFORMERS' }
        ].map((p) => ({
          ...p,
          image: this.getProductFallbackImage(p.name, 'mini')
        }));
        this.applyHighlightedProduct();
        setTimeout(() => this.initChart(), 0);
        this.cdr.detectChanges();
      }
    });
  }

  loadAiSummary(): void {
    console.log(this.auth.userState$.forEach(user => console.log('User state:', user)));
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.get<{ summary: string }>(`http://127.0.0.1:8000/api/products/clusters/summary${this.i18n.apiLanguageQuery()}`, { headers }).subscribe({
      next: (res) => {
        this.aiSummary = res.summary;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to load AI cluster summary', err);
        this.aiSummary = 'K-Means clustering is currently unavailable. The inventory table and chart below still reflect the products available to your account.';
        this.cdr.detectChanges();
      }
    });
  }

  normalizeImageUrl(url: string | null | undefined): string | null {
    if (!url) return null;
    const value = url.toString().trim();
    if (!value) return null;

    try {
      const parsed = new URL(value);
      const host = parsed.hostname.toLowerCase();
      if (host === 'images.acmesports.sports') {
        return null;
      }
      return parsed.href;
    } catch {
      return null;
    }
  }

  getProductFallbackImage(productName: string, size: 'mini' | 'main'): string {
    const name = (productName || '').toLowerCase();
    const width = size === 'mini' ? 80 : 150;
    let photoId = 'photo-1526170375885-4d8ecf77b99f';
    
    if (name.includes('watch')) {
      photoId = 'photo-1523275335684-37898b6baf30';
    } else if (name.includes('shoe') || name.includes('slide') || name.includes('cleat') || name.includes('boot') || name.includes('sneaker')) {
      photoId = 'photo-1542291026-7eec264c27ff';
    } else if (name.includes('shirt') || name.includes('polo') || name.includes('jacket') || name.includes('apparel') || name.includes('jersey') || name.includes('t-shirt')) {
      photoId = 'photo-1521572267360-ee0c2909d518';
    } else if (name.includes('bag') || name.includes('backpack') || name.includes('tote') || name.includes('glove')) {
      photoId = 'photo-1553062407-98eeb64c6a62';
    } else if (name.includes('golf') || name.includes('ball') || name.includes('deck') || name.includes('fitness') || name.includes('bat') || name.includes('helmet') || name.includes('equipment')) {
      photoId = 'photo-1517838277536-f5f99be501cd';
    }
    
    return `https://images.unsplash.com/${photoId}?w=${width}&auto=format&fit=crop&q=60`;
  }

  onMiniImageError(event: any, productName: string = ''): void {
    const img = event?.target as HTMLImageElement | null;
    if (!img) return;
    img.onerror = null;
    img.src = this.getProductFallbackImage(productName, 'mini');
  }

  isHighlightedProduct(product: any): boolean {
    return this.highlightedSku !== null && Number(product.sku) === this.highlightedSku;
  }

  private applyHighlightedProduct(): void {
    if (this.highlightedSku === null || this.products.length === 0) return;

    const skuText = this.highlightedSku.toString();
    this.tableSearchQuery = skuText;
    const index = this.filteredProductsTable.findIndex(p => Number(p.sku) === this.highlightedSku);
    this.currentPage = index >= 0 ? Math.floor(index / this.pageSize) + 1 : 1;

    setTimeout(() => {
      document.querySelector('.product-row-highlight')?.scrollIntoView({
        behavior: 'smooth',
        block: 'center'
      });
    }, 0);
  }

  initChart(): void {
    if (!this.clusteringChartCanvas) return;

    if (this.chart) {
      this.chart.destroy();
    }

    const ctx = this.clusteringChartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    const highValueData = this.products
      .filter(p => p.cluster === 'HIGH VALUE')
      .map(p => ({ x: p.price, y: p.monthly_volume, label: p.name }));

    const volumeDriversData = this.products
      .filter(p => p.cluster === 'VOLUME DRIVERS')
      .map(p => ({ x: p.price, y: p.monthly_volume, label: p.name }));

    const lowPerformersData = this.products
      .filter(p => p.cluster === 'LOW PERFORMERS')
      .map(p => ({ x: p.price, y: p.monthly_volume, label: p.name }));

    // construct cluster boundary ellipses to visually isolate clusters in the scatter plot
    const generateClusterBoundaryDataset = (
      label: string,
      dataPoints: any[],
      bgColor: string,
      borderColor: string,
      minRadX: number,
      minRadY: number
    ) => {
      if (dataPoints.length === 0) {
        return {
          label: label,
          data: [],
          showLine: false,
          pointRadius: 0
        };
      }

      const xs = dataPoints.map(p => p.x);
      const ys = dataPoints.map(p => p.y);

      const minX = Math.min(...xs);
      const maxX = Math.max(...xs);
      const minY = Math.min(...ys);
      const maxY = Math.max(...ys);

      const centerX = (minX + maxX) / 2;
      const centerY = (minY + maxY) / 2;

      // pad out cluster radii by 35% so outlier items are enclosed nicely
      const radX = Math.max(minRadX, ((maxX - minX) / 2) * 1.35);
      const radY = Math.max(minRadY, ((maxY - minY) / 2) * 1.35);

      // generate points to draw a smooth bounding ellipse
      const points = [];
      const steps = 60;
      for (let i = 0; i <= steps; i++) {
        const theta = (i / steps) * 2 * Math.PI;
        points.push({
          x: centerX + radX * Math.cos(theta),
          y: centerY + radY * Math.sin(theta),
          label: 'Boundary'
        });
      }

      return {
        label: label,
        data: points,
        showLine: true,
        fill: true,
        backgroundColor: bgColor,
        borderColor: borderColor,
        borderWidth: 1.5,
        borderDash: [5, 5],
        pointRadius: 0,
        pointHoverRadius: 0,
        pointHitRadius: 0,
        tension: 0.4
      };
    };

    const hvBoundary = generateClusterBoundaryDataset(
      'High Value Area',
      highValueData,
      'rgba(59, 130, 246, 0.04)',
      'rgba(59, 130, 246, 0.2)',
      200,
      120
    );

    const vdBoundary = generateClusterBoundaryDataset(
      'Volume Drivers Area',
      volumeDriversData,
      'rgba(139, 92, 246, 0.04)',
      'rgba(139, 92, 246, 0.2)',
      120,
      180
    );

    const lpBoundary = generateClusterBoundaryDataset(
      'Low Performers Area',
      lowPerformersData,
      'rgba(156, 163, 175, 0.04)',
      'rgba(156, 163, 175, 0.2)',
      150,
      100
    );

    this.chart = new Chart(ctx, {
      type: 'scatter',
      data: {
        datasets: [
          hvBoundary,
          vdBoundary,
          lpBoundary,
          {
            label: 'High Value',
            data: highValueData,
            backgroundColor: '#3b82f6', // Premium Blue
            borderColor: '#2563eb',
            pointRadius: 8,
            pointHoverRadius: 10,
            pointStyle: 'circle'
          },
          {
            label: 'Volume Drivers',
            data: volumeDriversData,
            backgroundColor: '#8b5cf6', // Premium Purple
            borderColor: '#7c3aed',
            pointRadius: 8,
            pointHoverRadius: 10,
            pointStyle: 'circle'
          },
          {
            label: 'Low Performers',
            data: lowPerformersData,
            backgroundColor: '#9ca3af', // Premium Gray
            borderColor: '#6b7280',
            pointRadius: 6,
            pointHoverRadius: 8,
            pointStyle: 'circle'
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false // We use our own custom segmented legend bar at the bottom
          },
          tooltip: {
            backgroundColor: 'rgba(17, 24, 39, 0.95)',
            titleColor: '#fff',
            bodyColor: '#e5e7eb',
            borderColor: 'rgba(255, 255, 255, 0.1)',
            borderWidth: 1,
            padding: 12,
            cornerRadius: 8,
            titleFont: {
              family: 'Outfit, Inter, sans-serif'
            },
            bodyFont: {
              family: 'Outfit, Inter, sans-serif'
            },
            callbacks: {
              label: (context: any) => {
                const item = context.raw;
                return [
                  `${item.label}`,
                  `Price: $${item.x.toFixed(2)}`,
                  `Monthly Volume: ${item.y}`
                ];
              }
            }
          }
        },
        scales: {
          x: {
            min: 0,
            title: {
              display: true,
              text: 'Price ($)',
              color: '#9ca3af',
              font: {
                size: 11,
                family: 'Outfit, Inter, sans-serif'
              }
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.03)',
              tickBorderDash: [5, 5]
            },
            ticks: {
              color: '#9ca3af',
              font: {
                family: 'Outfit, Inter, sans-serif'
              }
            }
          },
          y: {
            min: 0,
            title: {
              display: true,
              text: 'Monthly Volume',
              color: '#9ca3af',
              font: {
                size: 11,
                family: 'Outfit, Inter, sans-serif'
              }
            },
            grid: {
              color: 'rgba(255, 255, 255, 0.03)',
              tickBorderDash: [5, 5]
            },
            ticks: {
              color: '#9ca3af',
              font: {
                family: 'Outfit, Inter, sans-serif'
              }
            }
          }
        }
      }
    });
  }

  loadCategoriesAndDepartments(): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.get<string[]>('http://127.0.0.1:8000/api/products/categories', { headers }).subscribe({
      next: (res) => {
        this.allCategories = res;
        this.filteredCategories = [...res];
      },
      error: (err) => console.error('Failed to load categories', err)
    });

    this.http.get<any[]>('http://127.0.0.1:8000/api/products/departments', { headers }).subscribe({
      next: (res) => {
        this.allDepartments = res;
        this.filteredDepartments = [...res];
      },
      error: (err) => console.error('Failed to load departments', err)
    });
  }

  filterCategories(): void {
    const query = (this.newProduct.category || '').toLowerCase();
    if (!query) {
      this.filteredCategories = [...this.allCategories];
    } else {
      this.filteredCategories = this.allCategories.filter(cat => cat.toLowerCase().includes(query));
    }
  }

  selectCategory(cat: string): void {
    this.newProduct.category = cat;
    this.showCategorySuggestions = false;
  }

  filterDepartments(): void {
    const query = (this.departmentSearchText || '').toLowerCase();
    if (!query) {
      this.filteredDepartments = [...this.allDepartments];
    } else {
      this.filteredDepartments = this.allDepartments.filter(dept => dept.name.toLowerCase().includes(query));
    }
  }

  selectDepartment(dept: any): void {
    this.newProduct.department_id = dept.id;
    this.departmentSearchText = dept.name;
    this.showDeptSuggestions = false;
  }

  hideSuggestionsLater(type: 'category' | 'dept'): void {
    setTimeout(() => {
      if (type === 'category') {
        this.showCategorySuggestions = false;
      } else {
        this.showDeptSuggestions = false;
      }
      this.cdr.detectChanges();
    }, 200);
  }

  onImageSelected(event: any): void {
    const file = event.target.files[0];
    if (file) {
      const reader = new FileReader();
      reader.onload = () => {
        this.newProduct.image = reader.result as string;
        this.cdr.detectChanges();
      };
      reader.readAsDataURL(file);
    }
  }

  openCreateModal(): void {
    this.newProduct = {
      sku: null,
      name: '',
      category: '',
      price: null,
      discountPercent: 0,
      current_stock: null,
      department_id: '',
      image: null
    };
    this.departmentSearchText = '';
    this.errorMessage = '';
    this.showCreateModal = true;
    this.showCategorySuggestions = false;
    this.showDeptSuggestions = false;
    this.filteredCategories = [...this.allCategories];
    this.filteredDepartments = [...this.allDepartments];
    this.cdr.detectChanges();
  }

  closeCreateModal(): void {
    this.showCreateModal = false;
    this.errorMessage = '';
    this.cdr.detectChanges();
  }

  onCreateProductSubmit(): void {
    if (this.isSubmitting) return;
    this.isSubmitting = true;
    this.errorMessage = '';
    
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    });

    const payload = {
      sku: this.newProduct.sku,
      name: this.newProduct.name,
      category: this.newProduct.category,
      price: this.newProduct.price,
      discount: this.newProduct.discountPercent / 100,
      current_stock: this.newProduct.current_stock,
      department_id: this.newProduct.department_id.toString(),
      image: this.newProduct.image || null,
      monthly_volume: 0.0,
      cluster: 'LOW PERFORMERS',
      prep_delay: 4,
      internal_delay: 0,
      transport_delay: 0
    };

    this.http.post('http://127.0.0.1:8000/api/products', payload, { headers }).subscribe({
      next: (res: any) => {
        this.isSubmitting = false;
        this.showCreateModal = false;
        this.loadProductClusters();
        this.loadCategoriesAndDepartments(); // refresh unique categories from DB
        this.cdr.detectChanges();

        // Delayed sync to let backend background K-Means run and write updates
        setTimeout(() => {
          this.loadProductClusters();
          this.loadAiSummary();
        }, 1500);
      },
      error: (err) => {
        this.isSubmitting = false;
        if (err.status === 400 && err.error?.detail) {
          this.errorMessage = err.error.detail;
        } else {
          this.errorMessage = this.i18n.t('products.modal.errorGeneric');
        }
        this.cdr.detectChanges();
      }
    });
  }
}
