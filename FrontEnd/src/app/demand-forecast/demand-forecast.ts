import { Component, OnInit, inject, NgZone, ChangeDetectorRef, ViewChild, ElementRef, AfterViewInit } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { timeout } from 'rxjs/operators';

import { Auth } from '../../services/auth';
import { I18nService } from '../../services/i18n';
import { TranslatePipe } from '../../pipes/translate.pipe';

import { FullCalendarModule, FullCalendarComponent } from '@fullcalendar/angular';
import { DisplayDatePipe } from '../../pipes/display-date.pipe';
import {
  displayYear,
  shiftDateForDisplay,
  shiftDateToLogic,
} from '../../utils/display-date';
import { CalendarOptions } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';

import { Chart } from 'chart.js/auto';

export interface CalendarEvent {
  title: string;
  date: string; // YYYY-MM-DD
  type: 'delay' | 'stockout' | 'fraud' | 'high_demand' | 'meeting' | 'custom';
  description?: string;
  projectedStock?: number;
}

console.log('[DemandForecast] module loaded');

@Component({
  selector: 'app-demand-forecast',
  standalone: true,
  imports: [CommonModule, FormsModule, FullCalendarModule, TranslatePipe],
  templateUrl: './demand-forecast.html',
  styleUrl: './demand-forecast.css',
})
export class DemandForecast implements OnInit, AfterViewInit {
  constructor() {
    console.log('[DemandForecast] constructor');
  }

  private http = inject(HttpClient);
  private ngZone = inject(NgZone);
  private cdr = inject(ChangeDetectorRef);
  public auth = inject(Auth);
  private i18n = inject(I18nService);

  @ViewChild('fullcalendar') fullcalendarComponent!: FullCalendarComponent;
  
  private _forecastChartCanvas?: ElementRef<HTMLCanvasElement>;
  public forecastsData: any[] = [];

  @ViewChild('forecastChartCanvas') set forecastCanvas(content: ElementRef<HTMLCanvasElement> | undefined) {
    if (content) {
      this._forecastChartCanvas = content;
      setTimeout(() => {
        if (this.forecastsData && this.forecastsData.length > 0) {
          this.buildDemandForecastChart(this.forecastsData);
        }
      }, 0);
    }
  }

  get forecastChartCanvas(): ElementRef<HTMLCanvasElement> | undefined {
    return this._forecastChartCanvas;
  }

  private forecastChart: Chart | null = null;

  public activeTab: 'Monthly' | 'Weekly' | 'Daily' = 'Monthly';
  public currentMonth: number = 8; // September (0-indexed: 8)
  public currentYear: number = 2026;

  get displayCurrentYear(): number {
    return displayYear(this.currentYear);
  }

  public weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  public monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  public products: any[] = [];
  public filteredProducts: any[] = [];
  public selectedProduct: any = null;
  public selectedProductId: number = 191; // Default SKU
  public searchQuery: string = '';
  public showDropdown: boolean = false;

  public events: CalendarEvent[] = [];
  public showAddModal: boolean = false;

  public newEventTitle: string = '';
  public newEventDate: string = '2026-09-15';

  get displayNewEventDate(): string {
    return shiftDateForDisplay(this.newEventDate);
  }

  set displayNewEventDate(value: string) {
    this.newEventDate = shiftDateToLogic(value);
  }

  public newEventType: 'delay' | 'stockout' | 'fraud' | 'high_demand' | 'meeting' | 'custom' = 'meeting';

  public miniFallback = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=80';
  public mainFallback = 'https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=150';

  public businessEfficiency: number = 92.4;
  public abnormalDelaysCount: number = 4;
  public fraudOrderNumber: string = '77202';
  public aiExplanation: string = 'Generating local AI explanation...';
  private _isLoadingCalendar: boolean = false;
  
  public calendarOptions: CalendarOptions = {
    initialView: 'dayGridMonth',
    plugins: [dayGridPlugin, interactionPlugin],
    initialDate: '2026-09-01',
    headerToolbar: false, // Custom headers in template
    editable: false,
    selectable: false,
    dayMaxEvents: 3,
    events: []
  };

  public get isLoadingCalendar(): boolean {
    return this._isLoadingCalendar;
  }
  public set isLoadingCalendar(value: boolean) {
    console.log('[DemandForecast] isLoadingCalendar ->', value);
    this._isLoadingCalendar = value;
    this.cdr.markForCheck(); // force Angular to re-evaluate *ngIf in template
  }
  public productChanged: boolean = false;
  public pollCount: number = 0;
  private _pollingTimer: any = null;

  ngOnInit(): void {
    console.log('[DemandForecast] ngOnInit');
    this.loadProductsList();
  }

  ngAfterViewInit(): void {
    this.syncCalendarView();
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

  // pull the list of products from backend
  loadProductsList(): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.get<any[]>('/api/products', { headers }).subscribe({
      next: (prods) => {
        this.products = prods.map((p) => ({
          ...p,
          image: this.normalizeImageUrl(p.image) || this.getProductFallbackImage(p.name, 'mini')
        }));
        this.filteredProducts = [...this.products];
        
        // find default product SKU #191 to focus on
        const defaultProd = this.products.find(p => p.id === 191);
        if (defaultProd) {
          this.selectProduct(defaultProd);
        } else if (this.products.length > 0) {
          this.selectProduct(this.products[0]);
        }
      },
      error: (err) => {
        console.error('Failed to load products list from API', err);
        this.products = [
          {
            id: 191,
            name: "Nike Men's Free 5.0+ Running Shoe",
            image: this.getProductFallbackImage("Nike Men's Free 5.0+ Running Shoe", 'mini')
          }
        ];
        this.filteredProducts = [...this.products];
        this.selectProduct(this.products[0]);
      }
    });
  }

  filterProducts(): void {
    if (!this.searchQuery.trim()) {
      this.filteredProducts = this.products;
    } else {
      const q = this.searchQuery.toLowerCase();
      this.filteredProducts = this.products.filter(p => 
        p.name.toLowerCase().includes(q) || p.id.toString().includes(q)
      );
    }
  }

  // request AI demand explanation card details
  loadAiExplanation(): void {
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    console.log('[DemandForecast] loadAiExplanation', { productId: this.selectedProductId });
    this.aiExplanation = 'Generating AI explanation...';
    this.cdr.markForCheck();

    this.http.get<any>(`/api/products/forecasts/explain?product_id=${this.selectedProductId}${this.i18n.apiLanguageQuery('&')}`, { headers }).subscribe({
      next: (res) => {
        this.ngZone.run(() => {
          this.aiExplanation = res.explanation;
          this.cdr.detectChanges();
        });
        console.log('[DemandForecast] aiExplanation received', { productId: this.selectedProductId });
      },
      error: (err) => {
        this.ngZone.run(() => {
          this.aiExplanation = 'Could not generate dynamic AI explanation at this time.';
          this.cdr.detectChanges();
        });
        console.error('[DemandForecast] failed to load AI explanation', err);
      }
    });
  }

  selectProduct(p: any): void {
    console.log('[DemandForecast] selectProduct', { id: p?.id, name: p?.name });
    this.selectedProduct = p;
    this.selectedProductId = p.id;
    this.searchQuery = p.name;
    this.showDropdown = false;
    this.isLoadingCalendar = true;
    this.productChanged = true;
    this.pollCount = 0;
    if (this._pollingTimer) {
      clearTimeout(this._pollingTimer);
      this._pollingTimer = null;
    }

    this.aiExplanation = 'Generating AI explanation...';
    this.cdr.markForCheck();
    setTimeout(() => this.loadAiExplanation(), 0);
    this.loadEventsAndBuildCalendar();
  }

  hideDropdownWithDelay(): void {
    setTimeout(() => {
      this.showDropdown = false;
      if (this.selectedProduct) {
        this.searchQuery = this.selectedProduct.name;
      }
    }, 200);
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

  onImageError(event: any, productName: string = ''): void {
    const img = event?.target as HTMLImageElement | null;
    if (!img) return;
    img.onerror = null;
    img.src = this.getProductFallbackImage(productName, 'main');
  }

  onProductChange(): void {
    this.isLoadingCalendar = true;
    this.pollCount = 0;
    if (this._pollingTimer) {
      clearTimeout(this._pollingTimer);
      this._pollingTimer = null;
    }
    this.loadEventsAndBuildCalendar();
  }

  prevMonth(): void {
    if (this.currentYear === 2026 && this.currentMonth === 8) return;
    if (this.currentMonth === 0) {
      this.currentMonth = 11;
      this.currentYear--;
    } else {
      this.currentMonth--;
    }
    this.isLoadingCalendar = true;
    this.loadEventsAndBuildCalendar();
  }

  nextMonth(): void {
    if (this.currentYear === 2026 && this.currentMonth === 11) return;
    if (this.currentMonth === 11) {
      this.currentMonth = 0;
      this.currentYear++;
    } else {
      this.currentMonth++;
    }
    this.isLoadingCalendar = true;
    this.loadEventsAndBuildCalendar();
  }

  goToToday(): void {
    this.currentMonth = 8;
    this.currentYear = 2026;
    this.isLoadingCalendar = true;
    this.loadEventsAndBuildCalendar();
  }

  private syncCalendarView(): void {
    if (this.fullcalendarComponent) {
      const monthStr = (this.currentMonth + 1).toString().padStart(2, '0');
      this.fullcalendarComponent.getApi().gotoDate(`${this.currentYear}-${monthStr}-01`);
    }
  }

  private _safetyTimer: any = null;
  private _currentLoadId = 0;

  loadEventsAndBuildCalendar(): void {

    // fix calendar refresh bug on product switch
    const token = this.auth.getToken();
    const loadId = ++this._currentLoadId;

    if (!token) {
      this.isLoadingCalendar = false;
      this.syncCalendarView();
      return;
    }

    if (this._safetyTimer) {
      clearTimeout(this._safetyTimer);
      this._safetyTimer = null;
    }

    if (this._pollingTimer) {
      clearTimeout(this._pollingTimer);
      this._pollingTimer = null;
    }

    this.isLoadingCalendar = true;

    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    const productIdAtRequest = this.selectedProductId;
    const productChangedAtRequest = this.productChanged;
    this.productChanged = false;

    this._safetyTimer = setTimeout(() => {
      this.ngZone.run(() => {
        if (loadId !== this._currentLoadId) return;
        this.isLoadingCalendar = false;
        this.buildCalendarEvents([], []);
      });
    }, 5000);

    this.http.get<any[]>(
      `/api/products/forecasts?product_id=${productIdAtRequest}`,
      { headers }
    ).pipe(timeout(15000)).subscribe({
      next: (forecasts) => {
        if (loadId !== this._currentLoadId) return;
        if (this._safetyTimer) {
          clearTimeout(this._safetyTimer);
          this._safetyTimer = null;
        }

        if (productChangedAtRequest) {
          this.loadAiExplanation();
        }

        try {
          this.buildCalendarEvents(forecasts, []);
          this.forecastsData = forecasts;
          this.buildDemandForecastChart(forecasts);
        } catch (err) {
          console.error(err);
          this.buildCalendarEvents([], []);
          this.forecastsData = [];
          this.buildDemandForecastChart([]);
        }

        this.isLoadingCalendar = false;

        const hasDecemberForecasts = forecasts.some(f => f.sales === null && f.date >= '2026-12-01');
        if (!hasDecemberForecasts && this.pollCount < 8) {
          this.pollCount++;
          // wait 8s for ARIMA model to finish fitting before re-fetching data
          this._pollingTimer = setTimeout(() => {
            this.loadEventsAndBuildCalendar();
          }, 8000);
        }
      },
      error: (err) => {
        if (loadId !== this._currentLoadId) return;
        if (this._safetyTimer) {
          clearTimeout(this._safetyTimer);
          this._safetyTimer = null;
        }
        this.isLoadingCalendar = false;
        this.buildCalendarEvents([], []);
        this.forecastsData = [];
        this.buildDemandForecastChart([]);
        if (productChangedAtRequest) {
          this.loadAiExplanation();
        }
      }
    });
  }

  buildCalendarEvents(forecasts: any[], anomalies: any[]): void {
    const tempEvents: CalendarEvent[] = [];

    const monthForecasts = forecasts.filter(f => {
      const fDate = new Date(f.date);
      return fDate.getMonth() === this.currentMonth && fDate.getFullYear() === this.currentYear;
    });

    let highDemandThreshold = Infinity;
    let stockoutThreshold = Infinity;

    if (monthForecasts.length > 0) {
      const forecastValues = monthForecasts.map(f => f.forecast);
      const mean = forecastValues.reduce((sum, val) => sum + val, 0) / forecastValues.length;
      const variance = forecastValues.reduce((sum, val) => sum + Math.pow(val - mean, 2), 0) / forecastValues.length;
      const stdDev = Math.sqrt(variance);
      
      highDemandThreshold = mean + 1.2 * stdDev;
      stockoutThreshold = mean + 1.7 * stdDev;
    }

    const currentStock = this.selectedProduct?.current_stock ?? 100;
    let runningStock = currentStock;

    monthForecasts
      .sort((a, b) => a.date.localeCompare(b.date))
      .forEach(f => {
        const dateStr = f.date;
        const demandVal = f.sales !== null ? f.sales : f.forecast;
        runningStock = Math.max(0, runningStock - demandVal);
        const projectedStock = Math.round(runningStock);
        const forecastVal = f.forecast;

        if (forecastVal > currentStock && f.sales === null) {
          const recommendedToBuy = Math.ceil(forecastVal - currentStock);
          tempEvents.push({
            title: `Stockout Risk: Buy ${recommendedToBuy} u`,
            date: dateStr,
            type: 'stockout',
            description: `Forecasted demand of ${forecastVal.toFixed(0)} units exceeds stock of ${currentStock}.`,
            projectedStock
          });
        } else if (forecastVal > stockoutThreshold && f.sales === null) {
          tempEvents.push({
            title: `Stockout warning (${forecastVal.toFixed(0)} u)`,
            date: dateStr,
            type: 'stockout',
            projectedStock
          });
        } else if (forecastVal > highDemandThreshold) {
          tempEvents.push({
            title: `High demand: ${forecastVal.toFixed(0)} u`,
            date: dateStr,
            type: 'high_demand',
            projectedStock
          });
        }
      });

    // merge manually added custom events from local storage
    try {
      const saved = localStorage.getItem('custom_calendar_events');
      if (saved) {
        const customEvents: CalendarEvent[] = JSON.parse(saved);
        if (Array.isArray(customEvents)) {
          tempEvents.push(...customEvents);
        }
      }
    } catch (err) {}

    this.events = tempEvents;


    const fcEvents = this.events.map(e => ({
      title: e.title,
      start: e.date,
      className: [`event-${e.type}`, 'event-card'],
      extendedProps: {
        type: e.type,
        description: e.description || ''
      }
    }));

    this.calendarOptions = {
      ...this.calendarOptions,
      events: fcEvents
    };

    this.isLoadingCalendar = false;
    this.syncCalendarView();
  }

  // redraw the Chart.js demand forecast plot
  // round coordinates to integers since we sell whole units
  // and displaying raw decimals in tooltips looks bad
  // so we display only integers
  buildDemandForecastChart(forecasts: any[]): void {
    if (!this.forecastChartCanvas) return;
    const ctx = this.forecastChartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    if (!forecasts || forecasts.length === 0) {
      if (this.forecastChart) {
        this.forecastChart.destroy();
        this.forecastChart = null;
      }
      return;
    }

    const filtered = forecasts.filter(f => f.date >= '2026-09-01' && f.date <= '2026-12-31');
    const sorted = filtered.sort((a, b) => a.date.localeCompare(b.date));

    if (sorted.length === 0) return;

    const labels = sorted.map(s => s.date);
    const actualCoords = sorted.filter(c => c.sales !== null);


    const actualSalesData = sorted.map(s => s.sales !== null ? Math.round(s.sales) : null);

    // locate index of last day with actual sales data
    // visual join: bridge the historical and forecasted curves
    const lastActualIdx = sorted.reduce((last, s, i) => s.sales !== null ? i : last, -1);

    // forecast series calculations:
    //  - keep historical days empty
    //  - start visual curve at bridge point
    //  - display forecasts for upcoming days
    const forecastSalesData = sorted.map((s, idx) => {
      if (idx < lastActualIdx) return null;
      if (idx === lastActualIdx) return s.sales !== null ? Math.round(s.sales) : null;  // connect historical and forecast
      return s.forecast !== null ? Math.round(s.forecast) : null;                           // show future points
    });

    const lowerBoundData = sorted.map((s, idx) => {
      if (s.sales !== null) return null;
      const dist = Math.max(0, idx - (actualCoords.length - 1));
      const errorVal = dist * 0.3;
      return s.forecast !== null ? Math.round(Math.max(0, s.forecast - errorVal)) : null;
    });

    const upperBoundData = sorted.map((s, idx) => {
      if (s.sales !== null) return null;
      const dist = Math.max(0, idx - (actualCoords.length - 1));
      const errorVal = dist * 0.3;
      return s.forecast !== null ? Math.round(s.forecast + errorVal) : null;
    });

    if (this.forecastChart) {
      this.forecastChart.data.labels = labels;
      this.forecastChart.data.datasets[0].data = actualSalesData;
      this.forecastChart.data.datasets[1].data = forecastSalesData;
      this.forecastChart.data.datasets[2].data = lowerBoundData;
      this.forecastChart.data.datasets[3].data = upperBoundData;
      this.forecastChart.update();
    } else {
      this.forecastChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: labels,
          datasets: [
            {
              label: 'ACTUAL',
              data: actualSalesData,
              borderColor: '#10b981',
              backgroundColor: 'rgba(16, 185, 129, 0.05)',
              fill: true,
              tension: 0.2,
              borderWidth: 3,
              pointBackgroundColor: '#10b981',
              pointRadius: (context) => (context.dataIndex % 3 === 0 ? 4 : 0),
              spanGaps: false
            },
            {
              label: 'FORECAST',
              data: forecastSalesData,
              borderColor: '#6366f1',
              borderDash: [5, 5],
              tension: 0.2,
              borderWidth: 3,
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
              backgroundColor: 'rgba(99, 102, 241, 0.08)',
              fill: 2,
              pointRadius: 0,
              spanGaps: true
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
              ticks: {
                color: '#64748b',
                callback: (value, index) => {
                  const dateStr = labels[index];
                  if (!dateStr || index % 4 !== 0) return '';
                  const parts = dateStr.split('-');
                  return `${parts[2]}/${parts[1]}`; // dd/mm
                }
              }
            },
            y: {
              title: { display: true, text: 'VOLUME', color: '#64748b', font: { weight: 'bold', size: 10 } },
              grid: { color: '#f1f5f9' },
              ticks: { color: '#64748b' }
            }
          }
        }
      });
    }
  }

  pad(num: number): string {
    return num < 10 ? '0' + num : num.toString();
  }

  openAddEventModal(): void {
    this.newEventDate = `${this.currentYear}-${this.pad(this.currentMonth + 1)}-15`;
    this.newEventTitle = '';
    this.newEventType = 'meeting';
    this.showAddModal = true;
  }

  closeAddEventModal(): void {
    this.showAddModal = false;
  }

  saveEvent(): void {
    if (!this.newEventTitle.trim()) return;

    const selectedTime = new Date(this.newEventDate).getTime();
    const minTime = new Date('2026-09-01').getTime();
    const maxTime = new Date('2026-12-31').getTime();

    if (isNaN(selectedTime) || selectedTime < minTime || selectedTime > maxTime) {
      alert("Veuillez sélectionner une date comprise entre le 1er septembre 2026 et le 31 décembre 2026 (limite de la fenêtre de prévision de 90 jours).");
      return;
    }

    const newEvent: CalendarEvent = {
      title: this.newEventTitle.trim(),
      date: this.newEventDate,
      type: this.newEventType
    };

    const saved = localStorage.getItem('custom_calendar_events');
    let customEvents: CalendarEvent[] = [];
    if (saved) {
      try {
        customEvents = JSON.parse(saved);
      } catch (err) {}
    }
    customEvents.push(newEvent);
    localStorage.setItem('custom_calendar_events', JSON.stringify(customEvents));

    this.isLoadingCalendar = true;
    this.loadEventsAndBuildCalendar();
    this.showAddModal = false;
  }
}
