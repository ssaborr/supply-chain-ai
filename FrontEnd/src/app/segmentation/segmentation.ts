import { Component, OnInit, inject, ElementRef, ViewChild, ChangeDetectorRef } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { Auth } from '../../services/auth';
import { Chart } from 'chart.js/auto';

@Component({
  selector: 'app-segmentation',
  standalone: true,
  imports: [CommonModule, FormsModule, TranslatePipe],
  templateUrl: './segmentation.html',
  styleUrl: './segmentation.css',
})
export class Segmentation implements OnInit {
  private http = inject(HttpClient);
  public auth = inject(Auth);
  private cdr = inject(ChangeDetectorRef);
  public Math = Math;

  @ViewChild('clientsChartCanvas') clientsChartCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('suppliersChartCanvas') suppliersChartCanvas!: ElementRef<HTMLCanvasElement>;

  private clientsChart: Chart | null = null;
  private suppliersChart: Chart | null = null;

  public activeTab: 'clients' | 'suppliers' = 'clients';
  public isLoading: boolean = true;

  public clients: any[] = [];
  public suppliers: any[] = [];

  public clientSearch: string = '';
  public supplierSearch: string = '';
  public clientClusterFilter: string = 'ALL';
  public supplierClusterFilter: string = 'ALL';

  public clientPage: number = 1;
  public supplierPage: number = 1;
  public pageSize: number = 10;

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    this.isLoading = true;
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    let clientsLoaded = false;
    let suppliersLoaded = false;

    const checkAllLoaded = () => {
      if (clientsLoaded && suppliersLoaded) {
        this.isLoading = false;
        this.cdr.detectChanges();
        setTimeout(() => {
          this.initClientsChart();
          this.initSuppliersChart();
        }, 0);
      }
    };

    this.http.get<any[]>('http://127.0.0.1:8000/api/partners/clients/segmentation', { headers }).subscribe({
      next: (data) => {
        this.clients = data;
        clientsLoaded = true;
        checkAllLoaded();
      },
      error: (err) => {
        console.error('Failed to load clients segmentation', err);
        clientsLoaded = true;
        checkAllLoaded();
      }
    });

    this.http.get<any[]>('http://127.0.0.1:8000/api/partners/suppliers/segmentation', { headers }).subscribe({
      next: (data) => {
        this.suppliers = data;
        suppliersLoaded = true;
        checkAllLoaded();
      },
      error: (err) => {
        console.error('Failed to load suppliers segmentation', err);
        suppliersLoaded = true;
        checkAllLoaded();
      }
    });
  }

  get filteredClients(): any[] {
    let list = this.clients;

    const search = this.clientSearch.trim().toLowerCase();
    if (search) {
      list = list.filter(c => 
        (c.first_name + ' ' + c.last_name).toLowerCase().includes(search) ||
        c.email.toLowerCase().includes(search) ||
        c.country.toLowerCase().includes(search) ||
        c.id.toString().includes(search)
      );
    }

    if (this.clientClusterFilter !== 'ALL') {
      list = list.filter(c => c.cluster === this.clientClusterFilter);
    }

    return list;
  }

  get paginatedClients(): any[] {
    const startIndex = (this.clientPage - 1) * this.pageSize;
    return this.filteredClients.slice(startIndex, startIndex + this.pageSize);
  }

  prevClientPage(): void {
    if (this.clientPage > 1) {
      this.clientPage--;
    }
  }

  nextClientPage(): void {
    if (this.clientPage * this.pageSize < this.filteredClients.length) {
      this.clientPage++;
    }
  }

  onClientFilterChange(): void {
    this.clientPage = 1;
  }

  get filteredSuppliers(): any[] {
    let list = this.suppliers;

    const search = this.supplierSearch.trim().toLowerCase();
    if (search) {
      list = list.filter(s => 
        s.name.toLowerCase().includes(search) ||
        s.origin.toLowerCase().includes(search)
      );
    }

    if (this.supplierClusterFilter !== 'ALL') {
      list = list.filter(s => s.cluster === this.supplierClusterFilter);
    }

    return list;
  }

  get paginatedSuppliers(): any[] {
    const startIndex = (this.supplierPage - 1) * this.pageSize;
    return this.filteredSuppliers.slice(startIndex, startIndex + this.pageSize);
  }

  prevSupplierPage(): void {
    if (this.supplierPage > 1) {
      this.supplierPage--;
    }
  }

  nextSupplierPage(): void {
    if (this.supplierPage * this.pageSize < this.filteredSuppliers.length) {
      this.supplierPage++;
    }
  }

  onSupplierFilterChange(): void {
    this.supplierPage = 1;
  }

  private generateClusterBoundaryDataset(
    label: string,
    dataPoints: any[],
    bgColor: string,
    borderColor: string,
    minRadX: number,
    minRadY: number
  ) {
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

    const radX = Math.max(minRadX, ((maxX - minX) / 2) * 1.35);
    const radY = Math.max(minRadY, ((maxY - minY) / 2) * 1.35);

    const points = [];
    const steps = 60;
    for (let i = 0; i <= steps; i++) {
      const theta = (i / steps) * 2 * Math.PI;
      points.push({
        x: centerX + radX * Math.cos(theta),
        y: centerY + radY * Math.sin(theta)
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
  }

  initClientsChart(): void {
    if (!this.clientsChartCanvas) return;
    if (this.clientsChart) {
      this.clientsChart.destroy();
    }

    const ctx = this.clientsChartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    const getJitteredPoints = (clusterName: string) => {
      return this.clients
        .filter(c => c.cluster === clusterName)
        .map((c, i) => {
          const freq    = c.frequency || 1;
          const monetary = c.monetary  || 0;
          const recency  = c.recency   ?? 365;

          // Tiny deterministic jitter so overlapping points don't stack perfectly
          const seed    = parseInt(c.id) || i;
          const jitterX = ((seed * 7)  % 5) - 2.5;   // ±2.5 days
          const jitterY = ((seed * 13) % 50) - 25;    // ±$25

          // Bubble size driven by frequency: more orders → bigger dot
          const bubbleSize = Math.max(6, Math.min(28, 6 + freq * 1.8));

          return {
            x: Math.round(recency  + jitterX),
            y: Math.round(monetary + jitterY),
            r: Math.round(bubbleSize),
            label: `${c.first_name} ${c.last_name}`,
            realFreq: freq,
            realMon:  monetary,
            realRec:  recency
          };
        });
    };

    const championsData = getJitteredPoints('CHAMPIONS');
    const loyalData = getJitteredPoints('LOYAL');
    const atRiskData = getJitteredPoints('AT RISK');

    const championsBoundary = this.generateClusterBoundaryDataset(
      'Champions Area',
      championsData,
      'rgba(59, 130, 246, 0.02)',
      'rgba(59, 130, 246, 0.25)',
      12,
      12
    );

    const loyalBoundary = this.generateClusterBoundaryDataset(
      'Loyal Area',
      loyalData,
      'rgba(16, 185, 129, 0.02)',
      'rgba(16, 185, 129, 0.25)',
      12,
      12
    );

    const atRiskBoundary = this.generateClusterBoundaryDataset(
      'At Risk Area',
      atRiskData,
      'rgba(249, 115, 22, 0.02)',
      'rgba(249, 115, 22, 0.25)',
      12,
      12
    );

    this.clientsChart = new Chart(ctx, {
      type: 'scatter',
      data: {
        datasets: [
          championsBoundary,
          loyalBoundary,
          atRiskBoundary,
          {
            label: 'Champions',
            data: championsData,
            backgroundColor: 'rgba(59, 130, 246, 0.65)',
            borderColor: 'rgba(59, 130, 246, 1)',
            borderWidth: 1.5,
            pointRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r : 8;
            },
            pointHoverRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r + 2 : 10;
            }
          },
          {
            label: 'Loyal',
            data: loyalData,
            backgroundColor: 'rgba(16, 185, 129, 0.65)',
            borderColor: 'rgba(16, 185, 129, 1)',
            borderWidth: 1.5,
            pointRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r : 8;
            },
            pointHoverRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r + 2 : 10;
            }
          },
          {
            label: 'At Risk',
            data: atRiskData,
            backgroundColor: 'rgba(249, 115, 22, 0.65)',
            borderColor: 'rgba(249, 115, 22, 1)',
            borderWidth: 1.5,
            pointRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r : 8;
            },
            pointHoverRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r + 2 : 10;
            }
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
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
                if (!item || item.label === undefined) return '';
                return [
                  `${item.label}`,
                  `Purchase Frequency: ${item.realFreq} orders`,
                  `Monetary Total: $${item.realMon.toFixed(2)}`,
                  `Recency: ${item.realRec} days ago`
                ];
              }
            }
          }
        },
        scales: {
          x: {
            title: {
              display: true,
              text: 'Recency — Days Since Last Order  (lower = more recent)',
              color: '#475569',
              font: {
                size: 12,
                family: 'Outfit, Inter, sans-serif',
                weight: 'bold'
              }
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.03)'
            },
            ticks: {
              color: '#64748b',
              callback: (v: any) => `${v}d`
            }
          },
          y: {
            title: {
              display: true,
              text: 'Monetary Total — Lifetime Spend ($)',
              color: '#475569',
              font: {
                size: 12,
                family: 'Outfit, Inter, sans-serif',
                weight: 'bold'
              }
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.03)'
            },
            ticks: {
              color: '#64748b',
              callback: (v: any) => v >= 1000 ? `$${(v/1000).toFixed(0)}k` : `$${v}`
            }
          }
        }
      }
    });
  }

  initSuppliersChart(): void {
    if (!this.suppliersChartCanvas) return;
    if (this.suppliersChart) {
      this.suppliersChart.destroy();
    }

    const ctx = this.suppliersChartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    const getSupplierPoints = (clusterName: string) => {
      return this.suppliers
        .filter(s => s.cluster === clusterName)
        .map((s, i) => {
          const delayVal = s.avg_delay;
          const volVal = s.total_volume;
          const bubbleSize = Math.max(8, Math.min(30, 8 + (s.total_cost / 25000)));

          return {
            x: delayVal,
            y: volVal,
            r: Math.round(bubbleSize),
            label: s.name,
            realDelay: s.avg_delay,
            realVol: s.total_volume,
            realCost: s.total_cost
          };
        });
    };

    const strategicData = getSupplierPoints('STRATEGIC');
    const reliableData = getSupplierPoints('RELIABLE');
    const underperformingData = getSupplierPoints('UNDERPERFORMING');

    const allDelays = this.suppliers.map(s => s.avg_delay);
    const allVols = this.suppliers.map(s => s.total_volume);
    
    const maxDelay = Math.ceil((Math.max(...allDelays, 15) + 2) / 5) * 5;
    const maxVol = Math.ceil((Math.max(...allVols, 1000) * 1.1) / 500) * 500;

    const strategicBoundary = this.generateClusterBoundaryDataset(
      'Strategic Area',
      strategicData,
      'rgba(59, 130, 246, 0.02)',
      'rgba(59, 130, 246, 0.25)',
      1.5,
      150
    );

    const reliableBoundary = this.generateClusterBoundaryDataset(
      'Reliable Area',
      reliableData,
      'rgba(16, 185, 129, 0.02)',
      'rgba(16, 185, 129, 0.25)',
      1.5,
      150
    );

    const underperformingBoundary = this.generateClusterBoundaryDataset(
      'Underperforming Area',
      underperformingData,
      'rgba(239, 68, 68, 0.02)',
      'rgba(239, 68, 68, 0.25)',
      1.5,
      150
    );

    this.suppliersChart = new Chart(ctx, {
      type: 'scatter',
      data: {
        datasets: [
          strategicBoundary,
          reliableBoundary,
          underperformingBoundary,
          {
            label: 'Strategic',
            data: strategicData,
            backgroundColor: 'rgba(59, 130, 246, 0.65)',
            borderColor: 'rgba(59, 130, 246, 1)',
            borderWidth: 1.5,
            pointRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r : 8;
            },
            pointHoverRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r + 2 : 10;
            }
          },
          {
            label: 'Reliable',
            data: reliableData,
            backgroundColor: 'rgba(16, 185, 129, 0.65)',
            borderColor: 'rgba(16, 185, 129, 1)',
            borderWidth: 1.5,
            pointRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r : 8;
            },
            pointHoverRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r + 2 : 10;
            }
          },
          {
            label: 'Underperforming',
            data: underperformingData,
            backgroundColor: 'rgba(239, 68, 68, 0.65)',
            borderColor: 'rgba(239, 68, 68, 1)',
            borderWidth: 1.5,
            pointRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r : 8;
            },
            pointHoverRadius: (context: any) => {
              const item = context.raw;
              return item && item.r ? item.r + 2 : 10;
            }
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            display: false
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
                if (!item || item.label === undefined) return '';
                return [
                  `${item.label}`,
                  `Average Delay: ${item.realDelay.toFixed(1)} days`,
                  `Supply Volume: ${item.realVol} units`,
                  `Total Cost: $${item.realCost.toFixed(2)}`
                ];
              }
            }
          }
        },
        scales: {
          x: {
            min: 0,
            max: maxDelay,
            title: {
              display: true,
              text: 'Average Delay (Days)',
              color: '#475569',
              font: {
                size: 12,
                family: 'Outfit, Inter, sans-serif',
                weight: 'bold'
              }
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.03)'
            },
            ticks: {
              color: '#64748b'
            }
          },
          y: {
            min: 0,
            max: maxVol,
            title: {
              display: true,
              text: 'Supply Volume (Units)',
              color: '#475569',
              font: {
                size: 12,
                family: 'Outfit, Inter, sans-serif',
                weight: 'bold'
              }
            },
            grid: {
              color: 'rgba(0, 0, 0, 0.03)'
            },
            ticks: {
              color: '#64748b'
            }
          }
        }
      }
    });
  }
}
