import { Component, OnInit, inject, NgZone, ChangeDetectorRef, ViewChild, ElementRef, AfterViewInit } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Auth } from '../../services/auth';
import { I18nService } from '../../services/i18n';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { Chart } from 'chart.js/auto';

export interface AlertFeedItem {
  id: string;
  type: 'critical' | 'warning' | 'info';
  title: string;
  subtitle: string;
  time: string;
  advice: string;
  actionLabel: string;
  tabRoute: string;
}

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink, TranslatePipe],
  templateUrl: './dashboard.html',
  styleUrl: './dashboard.css',
})
export class Dashboard implements OnInit, AfterViewInit {
  private http = inject(HttpClient);
  private ngZone = inject(NgZone);
  private cdr = inject(ChangeDetectorRef);
  private router = inject(Router);
  public auth = inject(Auth);
  private i18n = inject(I18nService);

  @ViewChild('forecastChartCanvas') forecastChartCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('rfmChartCanvas') rfmChartCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('anomalyChartCanvas') anomalyChartCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('productsChartCanvas') productsChartCanvas!: ElementRef<HTMLCanvasElement>;

  private forecastChart: Chart | null = null;
  private rfmChart: Chart | null = null;
  private anomalyChart: Chart | null = null;
  private productsChart: Chart | null = null;

  public isLoadingForecast: boolean = true;
  public isLoadingRFM: boolean = true;
  public isLoadingAnomalies: boolean = true;
  public isLoadingProducts: boolean = true;
  public isLoadingKpis: boolean = true;

  public aiNarrative: string = 'Aggregating global supply chain intelligence...';

  public alerts: AlertFeedItem[] = [];

  public topProducts: any[] = [];

  public kpis = {
    globalHealth: { value: '', change: '', positive: true },
    otifServiceLevel: { value: '', change: '', positive: true },
    activeStockoutRate: { value: '', change: '', positive: true },
    avgLeadTime: { value: '', change: '', positive: true },
    totalRevenue: { value: '', change: '', positive: true },
    totalOrders: { value: '', change: '', positive: true },
    activeProducts: { value: '', change: 'Stable', positive: true },
    totalCustomers: { value: '', change: '', positive: true },
  };

  public activeKpiModal: {
    title: string;
    value: string;
    description: string;
    formula: string;
    calculation: string;
    target: string;
  } | null = null;

  private getDashboardCacheData(key: string): any {
    try {
      const cachedStr = localStorage.getItem('dashboard_cache_data');
      if (!cachedStr) return null;
      const cached = JSON.parse(cachedStr);

      if (cached.lang && cached.lang !== this.i18n.apiLanguageQuery()) {
        return null;
      }

      const now = Date.now();
      const age = now - (cached.timestamp || 0);
      const maxAge = 15 * 60 * 1000; // 15 minutes TTL
      if (age > maxAge) {
        return null;
      }

      return cached[key] !== undefined ? cached[key] : null;
    } catch (e) {
      console.error('Error reading from dashboard cache:', e);
      return null;
    }
  }

  private saveToDashboardCache(key: string, data: any): void {
    if (data === null || data === undefined) return;

    try {
      const cachedStr = localStorage.getItem('dashboard_cache_data');
      let cacheObj: any = {};
      if (cachedStr) {
        cacheObj = JSON.parse(cachedStr);
      } else {
        cacheObj = {};
      }

      cacheObj.timestamp = Date.now();
      cacheObj.lang = this.i18n.apiLanguageQuery();
      cacheObj.token = this.auth.getToken();
      cacheObj[key] = data;

      localStorage.setItem('dashboard_cache_data', JSON.stringify(cacheObj));
    } catch (e) {
      console.error('Error writing to dashboard cache:', e);
    }
  }

  private getWithCache<T>(
    cacheKey: string,
    url: string,
    headers: HttpHeaders,
    nextCallback: (res: T) => void,
    errorCallback: (err: any) => void,
    bypassCache: boolean = false
  ): void {
    if (!bypassCache) {
      const cached = this.getDashboardCacheData(cacheKey);
      if (cached !== null && cached !== undefined) {
        // Do not use empty array cache
        const isEmptyArray = Array.isArray(cached) && cached.length === 0;
        if (!isEmptyArray) {
          nextCallback(cached);
          return;
        }
      }
    }

    this.http.get<T>(url, { headers }).subscribe({
      next: (res) => {
        if (!Array.isArray(res) || res.length > 0) {
          this.saveToDashboardCache(cacheKey, res);
        }
        nextCallback(res);
      },
      error: (err) => {
        console.error(`[Dashboard Direct DB] Error fetching '${cacheKey}':`, err);
        errorCallback(err);
      }
    });
  }

  ngOnInit(): void {
    // 1. Initial Load: Check if cache exists in localStorage, use it immediately!
    this.loadTopProducts();
    this.loadAlertsAndNarrative();

    // 2. After that: Async background check if any of the 8 KPIs changed in DB
    this.checkKpisAndInvalidateCache();
  }

  public checkKpisAndInvalidateCache(): void {
    const token = this.auth.getToken();
    let headers = new HttpHeaders();
    if (token) {
      headers = headers.set('Authorization', `Bearer ${token}`);
    }
    const kpiUrl = `/api/kpis/executive-summary${this.i18n.apiLanguageQuery()}`;

    this.http.get<any>(kpiUrl, { headers }).subscribe({
      next: (res) => {
        if (!res || !res.metrics) {
          return;
        }

        const cachedStr = localStorage.getItem('dashboard_cache_data');
        let cachedKpis: any = null;
        if (cachedStr) {
          try {
            const cacheObj = JSON.parse(cachedStr);
            cachedKpis = cacheObj.kpis?.metrics;
          } catch (e) {}
        }

        const kpiMapping: { name: string; key: string }[] = [
          { name: 'Global SC Health', key: 'health' },
          { name: 'Service Level (OTIF)', key: 'otif' },
          { name: 'Active Stockout Rate', key: 'stockout_rate' },
          { name: 'Avg Delivery Lead Time', key: 'avg_lead' },
          { name: 'Total Revenue (Sales)', key: 'revenue' },
          { name: 'Total Orders', key: 'total_orders' },
          { name: 'Active Products', key: 'active_products' },
          { name: 'Total Customers', key: 'total_customers' }
        ];

        let isDifferent = false;

        for (const item of kpiMapping) {
          const liveMetric = res.metrics[item.key];
          const cachedMetric = cachedKpis ? cachedKpis[item.key] : null;

          const dbVal = liveMetric ? liveMetric.value : 'N/A';
          const dbChange = liveMetric ? liveMetric.change : '';
          const cacheVal = cachedMetric ? cachedMetric.value : 'NO_CACHE';
          const cacheChange = cachedMetric ? cachedMetric.change : '';

          if (dbVal !== cacheVal || dbChange !== cacheChange) {
            isDifferent = true;
            break;
          }
        }

        if (isDifferent || !cachedStr) {
          localStorage.removeItem('dashboard_cache_data');

          this.ngZone.run(() => {
            if (res.metrics) {
              this.kpis.globalHealth = res.metrics.health;
              this.kpis.otifServiceLevel = res.metrics.otif;
              this.kpis.activeStockoutRate = res.metrics.stockout_rate;
              this.kpis.avgLeadTime = res.metrics.avg_lead;
              this.kpis.totalRevenue = res.metrics.revenue;
              this.kpis.totalOrders = res.metrics.total_orders;
              this.kpis.activeProducts = res.metrics.active_products;
              this.kpis.totalCustomers = res.metrics.total_customers;
            }
            if (res.summary) {
              this.aiNarrative = res.summary;
            }
            this.isLoadingKpis = false;

            this.saveToDashboardCache('kpis', res);
            this.reloadAllDataBypassingCache();
            this.cdr.detectChanges();
          });
        }
      },
      error: (err) => console.error('[KPI Comparison] Error checking live DB metrics:', err)
    });
  }

  private reloadAllDataBypassingCache(): void {
    this.loadTopProducts(true);
    this.loadAlertsAndNarrative(true);
    this.initForecastChart(true);
    this.initRfmChart(true);
    this.initAnomalyChart(true);
    this.initProductsChart(true);
    this.cdr.detectChanges();
  }

  ngAfterViewInit(): void {
    this.initForecastChart();
    this.initRfmChart();
    this.initAnomalyChart();
    this.initProductsChart();
  }

  navigateToTab(route: string): void {
    this.router.navigate([route]);
  }

  openKpiExplanationModal(key: string): void {
    const kpiDataMap: Record<string, { title: string; description: string; formula: string; calculation: string; target: string }> = {
      globalHealth: {
        title: this.i18n.t('dashboard.kpi.globalHealth'),
        description: this.i18n.t('dashboard.kpi.globalHealth.desc'),
        formula: 'Health = (OTIF% + (100 - Stockout%)) / 2',
        calculation: this.i18n.t('dashboard.kpi.globalHealth.calc'),
        target: this.i18n.t('dashboard.kpi.globalHealth.target')
      },
      otifServiceLevel: {
        title: this.i18n.t('dashboard.kpi.otif'),
        description: this.i18n.t('dashboard.kpi.otif.desc'),
        formula: 'OTIF% = (Orders On-Time / Total Orders) * 100',
        calculation: this.i18n.t('dashboard.kpi.otif.calc'),
        target: this.i18n.t('dashboard.kpi.otif.target')
      },
      activeStockoutRate: {
        title: this.i18n.t('dashboard.kpi.stockout'),
        description: this.i18n.t('dashboard.kpi.stockout.desc'),
        formula: 'Stockout% = (Products with Stock = 0 / Total Catalog Products) * 100',
        calculation: this.i18n.t('dashboard.kpi.stockout.calc'),
        target: this.i18n.t('dashboard.kpi.stockout.target')
      },
      avgLeadTime: {
        title: this.i18n.t('dashboard.kpi.leadTime'),
        description: this.i18n.t('dashboard.kpi.leadTime.desc'),
        formula: 'Avg Lead Time = sum(real_shipment_days) / Total Orders (N)',
        calculation: this.i18n.t('dashboard.kpi.leadTime.calc'),
        target: this.i18n.t('dashboard.kpi.leadTime.target')
      },
      totalRevenue: {
        title: this.i18n.t('dashboard.kpi.revenue'),
        description: this.i18n.t('dashboard.kpi.revenue.desc'),
        formula: 'Revenue = sum(order_profit)',
        calculation: this.i18n.t('dashboard.kpi.revenue.calc'),
        target: this.i18n.t('dashboard.kpi.revenue.target')
      },
      totalOrders: {
        title: this.i18n.t('dashboard.kpi.orders'),
        description: this.i18n.t('dashboard.kpi.orders.desc'),
        formula: 'Orders Count = COUNT(sales_orders)',
        calculation: this.i18n.t('dashboard.kpi.orders.calc'),
        target: this.i18n.t('dashboard.kpi.orders.target')
      },
      activeProducts: {
        title: this.i18n.t('dashboard.kpi.products'),
        description: this.i18n.t('dashboard.kpi.products.desc'),
        formula: 'Catalog Depth = COUNT(products)',
        calculation: this.i18n.t('dashboard.kpi.products.calc'),
        target: this.i18n.t('dashboard.kpi.products.target')
      },
      totalCustomers: {
        title: this.i18n.t('dashboard.kpi.customers'),
        description: this.i18n.t('dashboard.kpi.customers.desc'),
        formula: 'Unique Customers = COUNT(DISTINCT client_id)',
        calculation: this.i18n.t('dashboard.kpi.customers.calc'),
        target: this.i18n.t('dashboard.kpi.customers.target')
      }
    };
    const details = kpiDataMap[key];
    if (details) {
      const val = (this.kpis as any)[key]?.value || 'N/A';
      this.activeKpiModal = {
        ...details,
        value: val
      };
      this.cdr.markForCheck();
    }
  }

  closeKpiModal(): void {
    this.activeKpiModal = null;
    this.cdr.markForCheck();
  }

  loadTopProducts(bypassCache: boolean = false): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });
    const url = '/api/orders/top-products';

    this.getWithCache<any[]>('topProducts', url, headers,
      (res) => {
        this.topProducts = res;
      },
      () => {
        const fallback = [
          { name: 'Smartwatch Series 5', sales: '1,240 sold this month', price: '$299.00', change: '+12%', isPositive: true, image: 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=120' },
          { name: 'Performance Sneakers', sales: '820 sold this month', price: '$89.00', change: '-3%', isPositive: false, image: 'https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=120' },
          { name: 'Polaroid Camera Retro', sales: '725 sold this month', price: '$120.00', change: '+27%', isPositive: true, image: 'https://images.unsplash.com/photo-1526170375885-4d8ecf77b99f?w=120' },
          { name: 'Wireless Headphones', sales: '562 sold this month', price: '$159.00', change: '+8%', isPositive: true, image: 'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=120' }
        ];
        this.topProducts = fallback;
      },
      bypassCache
    );
  }

  loadAlertsAndNarrative(bypassCache: boolean = false): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });

    const kpiUrl = `/api/kpis/executive-summary${this.i18n.apiLanguageQuery()}`;
    this.getWithCache<any>('kpis', kpiUrl, headers,
      (res) => {
        this.aiNarrative = res.summary;
        if (res.metrics) {
          this.kpis.globalHealth = res.metrics.health;
          this.kpis.otifServiceLevel = res.metrics.otif;
          this.kpis.activeStockoutRate = res.metrics.stockout_rate;
          this.kpis.avgLeadTime = res.metrics.avg_lead;
          this.kpis.totalRevenue = res.metrics.revenue;
          this.kpis.totalOrders = res.metrics.total_orders;
          this.kpis.activeProducts = res.metrics.active_products;
          this.kpis.totalCustomers = res.metrics.total_customers;
        }
        this.isLoadingKpis = false;
        this.cdr.detectChanges();
      },
      (err) => {
        console.error('Failed to load dynamic executive summary', err);
        this.aiNarrative = '';
        this.isLoadingKpis = false;
        this.cdr.detectChanges();
      },
      bypassCache
    );

    const tempAlerts: AlertFeedItem[] = [];

    // alert feed: query ML anomaly classifier checks
    const orderUrl = `/api/orders/overview/explain${this.i18n.apiLanguageQuery()}`;
    this.getWithCache<any>('alert_order', orderUrl, headers,
      (res) => {
        if (res && res.explanation) {
          tempAlerts.push({
            id: 'sales-order-alert',
            type: 'critical',
            title: this.i18n.t('dashboard.alert.orderTitle'),
            subtitle: this.i18n.t('dashboard.alert.orderSubtitle'),
            time: '2h ago',
            advice: res.explanation,
            actionLabel: this.i18n.t('dashboard.alert.orderAction'),
            tabRoute: '/sales-order'
          });
          this.updateAlerts(tempAlerts);
        }
      },
      (err) => console.error('Order anomaly explanation failed', err),
      bypassCache
    );

    // alert feed: query ARIMA forecast alarms
    const forecastUrl = `/api/products/forecasts/explain?product_id=191${this.i18n.apiLanguageQuery('&')}`;
    this.getWithCache<any>('alert_forecast', forecastUrl, headers,
      (res) => {
        if (res && res.explanation) {
          tempAlerts.push({
            id: 'forecast-alert',
            type: 'warning',
            title: this.i18n.t('dashboard.alert.forecastTitle'),
            subtitle: this.i18n.t('dashboard.alert.forecastSubtitle'),
            time: '14m ago',
            advice: res.explanation,
            actionLabel: this.i18n.t('dashboard.alert.forecastAction'),
            tabRoute: '/demand-forecast'
          });
          this.updateAlerts(tempAlerts);
        }
      },
      (err) => console.error('Forecast explanation failed', err),
      bypassCache
    );

    // alert feed: query product stockout risks
    const clusterUrl = `/api/products/clusters/summary${this.i18n.apiLanguageQuery()}`;
    this.getWithCache<any>('alert_inventory', clusterUrl, headers,
      (res) => {
        if (res && res.summary) {
          tempAlerts.push({
            id: 'inventory-alert',
            type: 'info',
            title: this.i18n.t('dashboard.alert.inventoryTitle'),
            subtitle: this.i18n.t('dashboard.alert.inventorySubtitle'),
            time: 'recently',
            advice: res.summary,
            actionLabel: this.i18n.t('dashboard.alert.inventoryAction'),
            tabRoute: '/products'
          });
          this.updateAlerts(tempAlerts);
        }
      },
      (err) => console.error('Cluster summary failed', err),
      bypassCache
    );

    // alert feed: query customer segmentation risks
    const partnerUrl = `/api/partners/clients/explain${this.i18n.apiLanguageQuery()}`;
    this.getWithCache<any>('alert_partner', partnerUrl, headers,
      (res) => {
        if (res && res.explanation) {
          tempAlerts.push({
            id: 'partner-alert',
            type: 'warning',
            title: this.i18n.t('dashboard.alert.partnerTitle'),
            subtitle: this.i18n.t('dashboard.alert.partnerSubtitle'),
            time: '3h ago',
            advice: res.explanation,
            actionLabel: this.i18n.t('dashboard.alert.partnerAction'),
            tabRoute: '/segmentation'
          });
          this.updateAlerts(tempAlerts);
        }
      },
      (err) => console.error('Client segmentation explanation failed', err),
      bypassCache
    );
  }

  updateAlerts(tempAlerts: AlertFeedItem[]): void {
    const priority = { critical: 0, warning: 1, info: 2 };
    this.alerts = [...tempAlerts].sort((a, b) => priority[a.type] - priority[a.type]);
    this.saveToDashboardCache('alerts', this.alerts);
    this.cdr.markForCheck();
  }

  initForecastChart(bypassCache: boolean = false): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });
    const url = '/api/products/forecasts?product_id=0';

    const render = (forecasts: any[]) => {
      this.isLoadingForecast = false;
      this.cdr.detectChanges();

      const canvas = this.forecastChartCanvas?.nativeElement;
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      if (!forecasts || !Array.isArray(forecasts) || forecasts.length === 0) {
        return;
      }

      let filtered = forecasts.filter(f => f.date >= '2026-09-01' && f.date <= '2026-12-31');
      if (filtered.length === 0) {
        // Fallback: take the most recent 90 days if custom range has no matches
        filtered = forecasts.slice(-90);
      }

      const sorted = filtered.sort((a, b) => a.date.localeCompare(b.date));
      if (sorted.length === 0) return;

      const labels = sorted.map(s => s.date);
      const actualSalesData = sorted.map(s => s.sales !== null && s.sales !== undefined ? Math.round(s.sales) : null);

      // Locate index of last day with actual sales data to bridge curves cleanly
      const lastActualIdx = sorted.reduce((last, s, i) => (s.sales !== null && s.sales !== undefined ? i : last), -1);

      const forecastSalesData = sorted.map((s, idx) => {
        if (lastActualIdx >= 0 && idx < lastActualIdx) return null;
        if (idx === lastActualIdx) return s.sales !== null && s.sales !== undefined ? Math.round(s.sales) : null;
        return s.forecast !== null && s.forecast !== undefined ? Math.round(s.forecast) : null;
      });

      const lowerBoundData = sorted.map((s, idx) => {
        if (lastActualIdx >= 0 && idx <= lastActualIdx) return null;
        return s.forecast !== null && s.forecast !== undefined ? Math.max(0, Math.round(s.forecast * 0.95)) : null;
      });

      const upperBoundData = sorted.map((s, idx) => {
        if (lastActualIdx >= 0 && idx <= lastActualIdx) return null;
        return s.forecast !== null && s.forecast !== undefined ? Math.round(s.forecast * 1.05) : null;
      });

      if (this.forecastChart) {
        this.forecastChart.destroy();
      }

      this.forecastChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: this.i18n.t('common.actual').toUpperCase(),
              data: actualSalesData,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.05)',
              fill: true,
              tension: 0.2,
              borderWidth: 2,
              pointBackgroundColor: '#10b981',
              pointRadius: (ctx) => (ctx.dataIndex % 3 === 0 ? 3 : 0),
              spanGaps: false
            },
            {
              label: this.i18n.t('common.forecast').toUpperCase(),
              data: forecastSalesData,
              borderColor: '#6366f1',
              borderDash: [5, 5],
              tension: 0.2,
              borderWidth: 2,
              pointRadius: 0,
              fill: false,
              spanGaps: true
            },
            {
              label: 'Lower Bound',
              data: lowerBoundData,
              borderColor: 'rgba(99, 102, 241, 0)',
              fill: false,
              pointRadius: 0,
              spanGaps: true
            },
            {
              label: 'Upper Bound',
              data: upperBoundData,
              borderColor: 'rgba(99, 102, 241, 0)',
              backgroundColor: 'rgba(99, 102, 241, 0.05)',
              fill: 2,
              pointRadius: 0,
              spanGaps: true
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              grid: { display: false },
              ticks: {
                color: '#94a3b8',
                font: { size: 9 },
                callback: (val, index) => {
                  const dateStr = labels[index];
                  if (!dateStr || index % 5 !== 0) return '';
                  const parts = dateStr.split('-');
                  return `${parts[2]}/${parts[1]}`;
                }
              }
            },
            y: {
              grid: { color: '#f1f5f9' },
              ticks: {
                color: '#94a3b8',
                font: { size: 9 },
                precision: 0
              }
            }
          }
        }
      });
    };

    this.getWithCache<any[]>('forecastChart', url, headers,
      (forecasts) => {
        render(forecasts);
      },
      () => {
        this.isLoadingForecast = false;
        this.cdr.detectChanges();
      },
      bypassCache
    );
  }

  initRfmChart(bypassCache: boolean = false): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });
    const url = '/api/partners/clients/segmentation';

    const render = (clients: any[]) => {
      this.isLoadingRFM = false;
      this.cdr.detectChanges();

      const canvas = this.rfmChartCanvas?.nativeElement;
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const getPoints = (clusterName: string) => {
        return clients
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

      if (this.rfmChart) {
        this.rfmChart.destroy();
      }

      this.rfmChart = new Chart(ctx, {
        type: 'bubble',
        data: {
          datasets: [
            {
              label: 'Champions',
              data: getPoints('CHAMPIONS'),
              backgroundColor: 'rgba(59, 130, 246, 0.6)',
              borderColor: 'rgba(59, 130, 246, 1)',
              borderWidth: 1
            },
            {
              label: 'Loyal',
              data: getPoints('LOYAL'),
              backgroundColor: 'rgba(16, 185, 129, 0.6)',
              borderColor: 'rgba(16, 185, 129, 1)',
              borderWidth: 1
            },
            {
              label: 'At Risk',
              data: getPoints('AT RISK'),
              backgroundColor: 'rgba(249, 115, 22, 0.6)',
              borderColor: 'rgba(249, 115, 22, 1)',
              borderWidth: 1
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (context: any) => {
                  const item = context.raw;
                  if (!item || item.label === undefined) return '';
                  return [
                    `${item.label}`,
                    `Purchase Frequency: ${item.realFreq} orders`,
                    `${this.i18n.t('segmentation.monetary')}: $${item.realMon.toFixed(2)}`,
                    `${this.i18n.t('segmentation.recency')}: ${this.i18n.t('segmentation.daysAgo', { count: item.realRec })}`
                  ];
                }
              }
            }
          },
          scales: {
            x: {
              title: { display: true, text: this.i18n.t('segmentation.recency'), font: { size: 9 }, color: '#94a3b8' },
              grid: { display: false },
              ticks: { color: '#94a3b8', font: { size: 8 }, callback: (v: any) => `${v}d` }
            },
            y: {
              title: { display: true, text: this.i18n.t('segmentation.monetary'), font: { size: 9 }, color: '#94a3b8' },
              grid: { color: '#f1f5f9' },
              ticks: { color: '#94a3b8', font: { size: 8 }, callback: (v: any) => v >= 1000 ? `$${(v/1000).toFixed(0)}k` : `$${v}` }
            }
          }
        }
      });
    };

    this.getWithCache<any[]>('rfmChart', url, headers,
      (clients) => {
        render(clients);
      },
      () => {
        this.isLoadingRFM = false;
        this.cdr.detectChanges();
      },
      bypassCache
    );
  }

  initAnomalyChart(bypassCache: boolean = false): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });
    const url = '/api/orders';

    const render = (orders: any[]) => {
      this.isLoadingAnomalies = false;
      this.cdr.detectChanges();

      const canvas = this.anomalyChartCanvas?.nativeElement;
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const points = orders.map(o => ({
        x: o.total_sales || 100,
        y: o.order_profit || 0,
        status: o.anomaly_status || 'valid'
      }));

      const validData = points.filter(p => p.status === 'valid');
      const unusualData = points.filter(p => p.status === 'unusual');
      const delayAnomalyData = points.filter(p => p.status === 'delay anomaly');

      if (this.anomalyChart) {
        this.anomalyChart.destroy();
      }

      this.anomalyChart = new Chart(ctx, {
        type: 'scatter',
        data: {
          datasets: [
            {
              label: this.i18n.t('common.valid'),
              data: validData,
              backgroundColor: 'rgba(16, 185, 129, 0.6)',
              pointRadius: 4
            },
            {
              label: this.i18n.t('common.unusual'),
              data: unusualData,
              backgroundColor: 'rgba(239, 68, 68, 0.7)',
              pointRadius: 5
            },
            {
              label: this.i18n.t('common.delayAnomaly'),
              data: delayAnomalyData,
              backgroundColor: 'rgba(245, 158, 11, 0.7)',
              pointRadius: 5
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: {
            x: {
              title: { display: true, text: this.i18n.t('sales.sales'), font: { size: 9 }, color: '#94a3b8' },
              grid: { display: false },
              ticks: { color: '#94a3b8', font: { size: 8 } }
            },
            y: {
              title: { display: true, text: this.i18n.t('sales.profit'), font: { size: 9 }, color: '#94a3b8' },
              grid: { color: '#f1f5f9' },
              ticks: { color: '#94a3b8', font: { size: 8 } }
            }
          }
        }
      });
    };

    this.getWithCache<any[]>('anomalyChart', url, headers,
      (orders) => {
        render(orders);
      },
      () => {
        this.isLoadingAnomalies = false;
        this.cdr.detectChanges();
      },
      bypassCache
    );
  }

  initProductsChart(bypassCache: boolean = false): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });
    const url = '/api/orders/discount-analysis';

    const render = (res: any) => {
      this.isLoadingProducts = false;
      this.cdr.detectChanges();

      const canvas = this.productsChartCanvas?.nativeElement;
      if (!canvas) return;

      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const labels = res.labels;
      const revenueData = res.revenue;
      const unitsSoldData = res.units_sold;

      if (this.productsChart) {
        this.productsChart.destroy();
      }

      this.productsChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: this.i18n.t('common.revenue'),
              data: revenueData,
              borderColor: '#6366f1',
              backgroundColor: 'rgba(99, 102, 241, 0.05)',
              fill: true,
              tension: 0.4,
              yAxisID: 'y',
              borderWidth: 3,
              pointBackgroundColor: '#6366f1',
              pointRadius: 4,
              pointHoverRadius: 6
            },
            {
              label: this.i18n.t('common.unitsSold'),
              data: unitsSoldData,
              type: 'bar',
              backgroundColor: 'rgba(148, 163, 184, 0.25)',
              hoverBackgroundColor: 'rgba(148, 163, 184, 0.4)',
              barPercentage: 0.5,
              yAxisID: 'y1'
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false }
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: { color: '#64748b' }
            },
            y: {
              position: 'left',
              title: { display: true, text: this.i18n.t('common.revenue').toUpperCase(), color: '#64748b', font: { weight: 'bold', size: 10 } },
              grid: { color: '#f1f5f9' },
              ticks: {
                color: '#64748b',
                callback: (value) => `$${Number(value) / 1000}k`
              }
            },
            y1: {
              position: 'right',
              title: { display: true, text: this.i18n.t('common.unitsSold').toUpperCase(), color: '#64748b', font: { weight: 'bold', size: 10 } },
              grid: { display: false },
              ticks: { color: '#64748b' }
            }
          }
        }
      });
    };

    this.getWithCache<any>('productsChart', url, headers,
      (res) => {
        render(res);
      },
      () => {
        this.isLoadingProducts = false;
        this.cdr.detectChanges();
      },
      bypassCache
    );
  }
}
