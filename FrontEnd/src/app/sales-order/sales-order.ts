import { Component, OnInit, inject, NgZone, ChangeDetectorRef, ViewChild, ElementRef, AfterViewInit } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth } from '../../services/auth';
import { I18nService } from '../../services/i18n';
import { TranslatePipe } from '../../pipes/translate.pipe';
import { ActivatedRoute } from '@angular/router';
import { displayYear } from '../../utils/display-date';

import { FullCalendarModule, FullCalendarComponent } from '@fullcalendar/angular';
import { CalendarOptions } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';

import { Chart } from 'chart.js/auto';

export interface CalendarEvent {
  title: string;
  date: string;
  type: 'order_event' | 'prep_start_event' | 'internal_delay_event' | 'scheduled_event' | 'barred_scheduled' | 'transport_delay_event' | 'delivery_delay_event' | 'delivered_event' | 'delay' | 'meeting' | 'custom';
  description?: string;
  orderId?: number;
}

export interface ScatterPoint {
  id: number;
  cx: number;
  cy: number;
  sales: number;
  profit: number;
  margin: number;
  delay: number;
  status: string;
  client: string;
  category: string;
}

@Component({
  selector: 'app-sales-order',
  standalone: true,
  imports: [CommonModule, FormsModule, FullCalendarModule, TranslatePipe],
  templateUrl: './sales-order.html',
  styleUrl: './sales-order.css',
})
export class SalesOrder implements OnInit, AfterViewInit {
  private http = inject(HttpClient);
  private ngZone = inject(NgZone);
  private cdr = inject(ChangeDetectorRef);
  public auth = inject(Auth);
  private route = inject(ActivatedRoute);
  private i18n = inject(I18nService);

  @ViewChild('fullcalendar') fullcalendarComponent!: FullCalendarComponent;
  @ViewChild('scatterChartCanvas') scatterChartCanvas!: ElementRef<HTMLCanvasElement>;
  @ViewChild('discountChartCanvas') discountChartCanvas!: ElementRef<HTMLCanvasElement>;

  private scatterChart: Chart | null = null;
  private discountChart: Chart | null = null;

  public orders: any[] = [];
  public productsList: any[] = [];
  public productDelaysMap: { [sku: number]: { prep_delay: number, internal_delay: number, transport_delay: number } } = {};
  public purchases: any[] = [];
  public aiExplanation: string = 'Generating executive summary...';
  public isLoading: boolean = false;

  public currentPage: number = 1;
  public pageSize: number = 10;
  public totalOrdersCount: number = 0;

  public currentMonth: number = 8; // September (8)
  public currentYear: number = 2026;

  get displayCurrentYear(): number {
    return displayYear(this.currentYear);
  }
  public weekdays = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  public monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  public calendarOptions: CalendarOptions = {
    initialView: 'dayGridMonth',
    plugins: [dayGridPlugin, interactionPlugin],
    initialDate: '2026-09-01',
    headerToolbar: false, // Custom headers are used in HTML template
    editable: false,
    selectable: false,
    dayMaxEvents: 3,
    events: [],
    eventClick: this.handleCalendarEventClick.bind(this)
  };

  public scatterPoints: ScatterPoint[] = [];
  public selectedScatterPoint: ScatterPoint | null = null;

  public topProducts: any[] = [];

  public avgValidSales: number = 0;
  public avgValidProfit: number = 0;
  public avgValidQuantity: number = 0;
  public avgValidDelay: number = 0;

  public selectedOrderQuantity: number = 0;
  public selectedOrderDelay: number = 0;

  public maxSales: number = 1;
  public minSales: number = 0;
  public maxProfitMargin: number = 1;
  public minProfitMargin: number = -1;
  public maxQuantity: number = 1;
  public minQuantity: number = 0;
  public maxDelay: number = 1;
  public minDelay: number = 0;
  
  public nearestNeighbors: any[] = [];
  public isImportModalOpen: boolean = false;
  public isConfirmModalOpen: boolean = false;
  public isValidationErrorModalOpen: boolean = false;
  public isRetrainStatusModalOpen: boolean = false;
  
  public selectedFileName: string = "";
  public validationCount: number = 0;
  public validationColumns: string = "";
  public validationErrorMessage: string = "";
  public selectedFileForImport: File | null = null;
  
  public importProgress: number = 0;
  public importStatusMessage: string = "";
  public stepsCompleted: number = 0;
  public isImporting: boolean = false;
  public importStatus: boolean = false;

  adjustDateToSepDec2026(dateStr: string): string {
    if (!dateStr) return '';
    try {
      let d: Date;
      if (dateStr.includes('T')) {
        d = new Date(dateStr);
      } else {
        const parts = dateStr.split(' ');
        const dateParts = parts[0].split('/');
        if (dateParts.length === 3) {
          const p0 = parseInt(dateParts[0]);
          const p1 = parseInt(dateParts[1]);
          const p2 = parseInt(dateParts[2]);
          const month = p0 <= 12 ? p0 - 1 : p1 - 1;
          const day = p0 <= 12 ? p1 : p0;
          d = new Date(2026, month, day);
        } else {
          d = new Date(dateStr);
        }
      }
      
      if (!isNaN(d.getTime())) {
        const origMonth = d.getMonth();
        const newMonth = 8 + (origMonth % 4);
        d.setFullYear(2026);
        d.setMonth(newMonth);
        
        const y = d.getFullYear();
        const m = (d.getMonth() + 1).toString().padStart(2, '0');
        const day = d.getDate().toString().padStart(2, '0');
        return `${y}-${m}-${day}`;
      }
    } catch (e) {
      console.warn('Error adjusting date:', dateStr, e);
    }
    return dateStr;
  }

  addDaysSkippingWeekendsClass(startDate: Date, days: number): Date {
    let currentDate = new Date(startDate.getTime());
    while (currentDate.getDay() === 0 || currentDate.getDay() === 6) {
      currentDate.setDate(currentDate.getDate() + 1);
    }
    for (let i = 0; i < days; i++) {
      currentDate.setDate(currentDate.getDate() + 1);
      while (currentDate.getDay() === 0 || currentDate.getDay() === 6) {
        currentDate.setDate(currentDate.getDate() + 1);
      }
    }
    return currentDate;
  }

  ngOnInit(): void {
    this.loadDashboardData();
  }

  ngAfterViewInit(): void {
    this.updateScatterChart();
    this.updateDiscountChart();
  }

  // 2-minute cache helpers
  private getCachedData<T>(key: string): T | null {
    try {
      const cached = localStorage.getItem(`sales_cache_${key}`);
      if (!cached) return null;
      const parsed = JSON.parse(cached);
      const now = Date.now();
      if (now - parsed.timestamp < 2 * 60 * 1000) {
        return parsed.data as T;
      }
      localStorage.removeItem(`sales_cache_${key}`);
    } catch (e) {
      console.error('Error reading sales cache:', e);
    }
    return null;
  }

  private setCachedData<T>(key: string, data: T): void {
    try {
      const entry = {
        timestamp: Date.now(),
        data: data
      };
      localStorage.setItem(`sales_cache_${key}`, JSON.stringify(entry));
    } catch (e) {
      console.error('Error writing sales cache:', e);
    }
  }

  private getWithCache<T>(
    url: string,
    headers: HttpHeaders,
    nextCallback: (res: T) => void,
    errorCallback: (err: any) => void
  ): void {
    // Bypass local cache to ensure real-time synchronization with DB changes
    this.http.get<T>(url, { headers }).subscribe({
      next: (res) => {
        nextCallback(res);
      },
      error: (err) => {
        errorCallback(err);
      }
    });
  }

  loadDashboardData(): void {
    const token = this.auth.getToken();
    if (!token) return;

    this.isLoading = true;
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    // map delays per sku before loading orders (bypassing local cache for real-time Settings coherence)
    this.http.get<any[]>('/api/products', { headers }).subscribe({
      next: (productsData) => {
        this.productsList = productsData;
        this.productDelaysMap = {};
        productsData.forEach(p => {
          this.productDelaysMap[p.sku] = {
            prep_delay: p.prep_delay !== undefined ? p.prep_delay : 4,
            internal_delay: p.internal_delay !== undefined ? p.internal_delay : 0,
            transport_delay: p.transport_delay !== undefined ? p.transport_delay : 0
          };
        });

      // Fetch sales orders
      this.getWithCache<any[]>('/api/orders', headers, (data) => {
        // shift dates to Sep-Dec 2026 timeframe for consistency and compute delivery date using product specific delays
        data.forEach(o => {
          o.order_date = this.adjustDateToSepDec2026(o.order_date);
          const orderDateObj = new Date(o.order_date);
          const prepStartResult = this.addDaysSkippingWeekendsClass(orderDateObj, 0);
          
          const delays = this.getOrderDynamicDelays(o);
          const deliveryDateObj = this.addDaysSkippingWeekendsClass(prepStartResult, delays.real_shipment);
          
          const y = deliveryDateObj.getFullYear();
          const m = (deliveryDateObj.getMonth() + 1).toString().padStart(2, '0');
          const day = deliveryDateObj.getDate().toString().padStart(2, '0');
          o.delivery_date = `${y}-${m}-${day}`;
        });

        this.orders = data;
        this.totalOrdersCount = data.length;

        if (data.length > 0) {
          const salesValues = data.map(o => o.total_sales || 0);
          const margins = data.map(o => o.profit_margin || 0);
          const quantities = data.map(o => o.total_quantity || 0);
          const delays = data.map(o => o.delay_delta || 0);

          this.maxSales = Math.max(...salesValues, 1);
          this.minSales = Math.min(...salesValues, 0);
          this.maxProfitMargin = Math.max(...margins, 1);
          this.minProfitMargin = Math.min(...margins, -1);
          this.maxQuantity = Math.max(...quantities, 1);
          this.minQuantity = Math.min(...quantities, 0);
          this.maxDelay = Math.max(...delays, 1);
          this.minDelay = Math.min(...delays, 0);
        }

        // Calculate baseline averages of valid orders for KNN explainer
        const validOrders = data.filter(o => o.anomaly_status === 'valid');
        if (validOrders.length > 0) {
          const totalSalesSum = validOrders.reduce((sum, o) => sum + (o.total_sales || 0), 0);
          const profitSum = validOrders.reduce((sum, o) => sum + (o.order_profit || 0), 0);
          const qtySum = validOrders.reduce((sum, o) => sum + (o.total_quantity || 0), 0);
          const delaySum = validOrders.reduce((sum, o) => sum + (o.delay_delta || 0), 0);
          
          this.avgValidSales = totalSalesSum / validOrders.length;
          this.avgValidProfit = profitSum / validOrders.length;
          this.avgValidQuantity = qtySum / validOrders.length;
          this.avgValidDelay = delaySum / validOrders.length;
        }

        this.buildScatterPlot();
        this.buildCalendarGrid();

        this.route.queryParams.subscribe(params => {
          const orderIdStr = params['orderId'];
          if (orderIdStr) {
            const orderId = parseInt(orderIdStr);
            const orderObj = this.orders.find(o => o.id === orderId);
            if (orderObj) {
              this.tableSearchQuery = 'SO' + orderId;
              this.currentPage = 1;
              this.selectScatterPointFromNeighbor(orderObj);
            }
          }
        });

        this.isLoading = false;
        this.cdr.markForCheck();
      }, (err) => {
        console.error('Error fetching orders:', err);
        this.isLoading = false;
      });
      },
      error: (err) => {
        console.error('Error fetching products list:', err);
        this.isLoading = false;
      }
    });

    // Fetch purchases
    this.getWithCache<any[]>('/api/orders/purchases', headers, (data) => {
      this.purchases = data;
      this.buildCalendarGrid();
      this.cdr.markForCheck();
    }, (err) => {
      console.error('Error fetching purchases:', err);
    });

    // Fetch AI explanation
    this.getWithCache<any>(`/api/orders/overview/explain${this.i18n.apiLanguageQuery()}`, headers, (res) => {
      this.aiExplanation = res.explanation;
      this.cdr.markForCheck();
    }, (err) => {
      console.error('Error fetching AI overview explanation:', err);
      this.aiExplanation = 'Unable to load executive narrative summary at this time.';
    });

    // Fetch top products
    this.getWithCache<any[]>('/api/orders/top-products', headers, (data) => {
      this.topProducts = data;
      this.cdr.markForCheck();
    }, (err) => {
      console.error('Error fetching top products:', err);
    });
  }

  getOrderDynamicDelays(order: any): { prep_delay: number, internal_delay: number, transport_delay: number, real_shipment: number } {
    // Intermediate delay parameters (prep, internal, transport) come from the product catalog configuration
    let prep_delay = 4;
    let internal_delay = 0;
    let transport_delay = 0;

    const lineItems = order.order_lines || [];
    if (lineItems.length > 0) {
      const preps: number[] = [];
      const internals: number[] = [];
      const transports: number[] = [];

      lineItems.forEach((line: any) => {
        const sku = line.product_sku;
        const config = this.productDelaysMap[sku];
        if (config) {
          preps.push(config.prep_delay);
          internals.push(config.internal_delay);
          transports.push(config.transport_delay);
        }
      });

      if (preps.length > 0) prep_delay = Math.max(...preps);
      if (internals.length > 0) internal_delay = Math.max(...internals);
      if (transports.length > 0) transport_delay = Math.max(...transports);
    } else {
      prep_delay = order.scheduled_shipment !== undefined ? order.scheduled_shipment : 4;
      internal_delay = order.internalDelay !== undefined ? order.internalDelay : 0;
      transport_delay = order.transportDelay !== undefined ? order.transportDelay : 0;
    }

    // Only the actual delivered shipment duration comes from the sales order record itself (original database values)
    const real_shipment = order.real_shipment !== undefined ? order.real_shipment : (prep_delay + internal_delay + transport_delay);

    return { prep_delay, internal_delay, transport_delay, real_shipment };
  }


  public showDetailPopup: boolean = false;
  public selectedOrderForPopup: any = null;
  public popupDecisionComment: string = '';
  public shapFeatures: any[] = [];
  public popupOrderDate: string = '';
  public popupPrepDate: string = '';
  public popupInternalDelayDate: string = '';
  public popupDeliveryDate: string = '';
  public popupAiSummary: string = 'Generating AI explanation summary...';
  public popupNetworkNodes: any[] = [];

  mathAbs(val: number): number {
    return Math.abs(val);
  }

  openOrderDetailPopup(order: any): void {
    this.selectedOrderForPopup = order;
    this.popupDecisionComment = order.user_description || '';
    
    // Parse order date and compute milestones
    const parseDateLocal = (dateStr: string): Date => {
      if (!dateStr) return new Date(2026, 8, 1);
      try {
        if (dateStr.includes('T')) {
          const d = new Date(dateStr);
          d.setFullYear(2026);
          return d;
        }
        const parts = dateStr.split(' ');
        const dateParts = parts[0].split('/');
        if (dateParts.length === 3) {
          const m = parseInt(dateParts[0]) - 1;
          const d = parseInt(dateParts[1]);
          return new Date(2026, m, d);
        }
      } catch {}
      const parsed = new Date(dateStr);
      if (!isNaN(parsed.getTime())) {
        parsed.setFullYear(2026);
        return parsed;
      }
      return new Date(2026, 8, 1);
    };

    const addDaysHelperLocal = (startDate: Date, days: number): Date => {
      let currentDate = new Date(startDate.getTime());
      while (currentDate.getDay() === 0 || currentDate.getDay() === 6) {
        currentDate.setDate(currentDate.getDate() + 1);
      }
      for (let i = 0; i < days; i++) {
        currentDate.setDate(currentDate.getDate() + 1);
        while (currentDate.getDay() === 0 || currentDate.getDay() === 6) {
          currentDate.setDate(currentDate.getDate() + 1);
        }
      }
      return currentDate;
    };

    const addDaysSkippingWeekendsLocal = (startDate: Date, days: number): { targetDate: Date, weekendDelayDays: number, weekendDates: Date[] } => {
      let currentDate = new Date(startDate.getTime());
      let weekendDelayDays = 0;
      const weekendDates: Date[] = [];

      while (currentDate.getDay() === 0 || currentDate.getDay() === 6) {
        weekendDates.push(new Date(currentDate.getTime()));
        currentDate.setDate(currentDate.getDate() + 1);
        weekendDelayDays++;
      }

      for (let i = 0; i < days; i++) {
        currentDate.setDate(currentDate.getDate() + 1);
        while (currentDate.getDay() === 0 || currentDate.getDay() === 6) {
          weekendDates.push(new Date(currentDate.getTime()));
          currentDate.setDate(currentDate.getDate() + 1);
          weekendDelayDays++;
        }
      }

      return { targetDate: currentDate, weekendDelayDays, weekendDates };
    };

    const formatDateStrLocal = (d: Date): string => {
      const y = d.getFullYear();
      const m = (d.getMonth() + 1).toString().padStart(2, '0');
      const day = d.getDate().toString().padStart(2, '0');
      return `${y}-${m}-${day}`;
    };

    const delays = this.getOrderDynamicDelays(order);
    const parsedStart = parseDateLocal(order.order_date);
    const prepStart = addDaysHelperLocal(parsedStart, 0);
    const internalDelayDays = delays.internal_delay;
    const prepDelayDate = addDaysHelperLocal(prepStart, internalDelayDays);
    const realShipment = delays.real_shipment;
    const delivDate = addDaysHelperLocal(prepStart, realShipment);

    this.popupOrderDate = this.formatDateString(order.order_date);
    this.popupPrepDate = formatDateStrLocal(prepStart);
    this.popupInternalDelayDate = formatDateStrLocal(prepDelayDate);
    this.popupDeliveryDate = formatDateStrLocal(delivDate);

    // Simulated SHAP values
    const delayVal = order.delay_delta > 0 ? (order.delay_delta * 12) : -10;
    const qtyVal = order.total_quantity > 80 ? Math.min(45, Math.round(order.total_quantity * 0.4)) : -15;
    const historyVal = order.client_id % 3 === 0 ? -20 : 25;
    const marginVal = order.profit_margin > 0.1 ? -22 : 30;

    this.shapFeatures = [
      { name: 'Shipping Delay Contribution', value: delayVal },
      { name: 'Order Volume Impact', value: qtyVal },
      { name: 'Client Account History', value: historyVal },
      { name: 'Profit Margin Deviation', value: marginVal }
    ];

    // Build timeline network flow
    this.popupNetworkNodes = [];

    this.popupNetworkNodes.push({
      type: 'client',
      label: `Client C${order.client_id}`,
      sub: `Ordered: ${this.popupOrderDate}`,
      linkLabel: 'placed',
      linkRisk: false
    });

    // Check if Prep Start weekend delay happened
    const prepStartResult = addDaysSkippingWeekendsLocal(parsedStart, 0);
    const prepStartActual = prepStartResult.targetDate;
    // Weekend delay calculation kept, but node not pushed to timeline

    const finalDeliveryResult = addDaysSkippingWeekendsLocal(prepStartActual, delays.real_shipment);
    const finalDeliveryDate = finalDeliveryResult.targetDate;

    const scheduledDays = delays.prep_delay + delays.internal_delay + delays.transport_delay;
    const scheduledResult = addDaysSkippingWeekendsLocal(prepStartActual, scheduledDays);
    const scheduledDate = scheduledResult.targetDate;

    this.popupNetworkNodes.push({
      type: 'SO',
      label: `SO #${order.id}`,
      sub: `Prep Started: ${formatDateStrLocal(prepStartActual)}`,
      linkLabel: 'prep duration',
      linkRisk: false
    });

    this.popupNetworkNodes.push({
      type: 'delay',
      label: 'Preparation Delay',
      sub: `Delay: +${delays.prep_delay}d`,
      linkLabel: 'internal delay',
      linkRisk: false,
      isBarred: false
    });

    this.popupNetworkNodes.push({
      type: 'delay',
      label: 'Internal Prep Delay',
      sub: `Delay: +${delays.internal_delay}d`,
      linkLabel: 'transport delay',
      linkRisk: false,
      isBarred: false
    });

    this.popupNetworkNodes.push({
      type: 'delay',
      label: 'Transit Carrier Delay',
      sub: `Delay: +${delays.transport_delay}d`,
      linkLabel: 'scheduled',
      linkRisk: false,
      isBarred: false
    });

    this.popupNetworkNodes.push({
      type: 'milestone',
      label: 'Scheduled Delivery',
      sub: `Expected: ${formatDateStrLocal(scheduledDate)}`,
      linkLabel: 'actual delivery',
      linkRisk: false,
      isBarred: delays.real_shipment < scheduledDays
    });

    const timeDiffLocal = finalDeliveryDate.getTime() - scheduledDate.getTime();
    const calendarDelayDaysLocal = Math.max(0, Math.ceil(timeDiffLocal / (1000 * 3600 * 24)));

    this.popupNetworkNodes.push({
      type: 'milestone',
      label: 'Actual Delivery',
      sub: `Delivered: ${formatDateStrLocal(finalDeliveryDate)}`,
      linkLabel: calendarDelayDaysLocal > 0 ? `+${calendarDelayDaysLocal}d late` : 'on-time',
      linkRisk: calendarDelayDaysLocal > 0
    });

    // Fetch AI explanation from LLM
    this.popupAiSummary = 'Generating AI explanation summary...';
    
    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.get<{ explanation: string }>(`/api/orders/${order.id}/explain${this.i18n.apiLanguageQuery()}`, { headers }).subscribe({
      next: (res) => {
        this.popupAiSummary = res.explanation;
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Failed to load order explanation', err);
        this.popupAiSummary = this.getDynamicPopupSummary();
        this.cdr.markForCheck();
      }
    });

    this.showDetailPopup = true;
    this.cdr.markForCheck();
  }

  closeDetailPopup(): void {
    this.showDetailPopup = false;
    this.selectedOrderForPopup = null;
    this.popupDecisionComment = '';
    this.cdr.markForCheck();
  }

  saveVerdict(verdict: 'TP' | 'FP'): void {
    if (!this.selectedOrderForPopup) return;

    const token = this.auth.getToken();
    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    const payload = {
      verdict: verdict,
      description: this.popupDecisionComment
    };

    this.http.post(`/api/orders/${this.selectedOrderForPopup.id}/verdict`, payload, { headers }).subscribe({
      next: () => {
        this.selectedOrderForPopup.user_verdict = verdict;
        this.selectedOrderForPopup.user_description = this.popupDecisionComment;

        const idx = this.orders.findIndex(o => o.id === this.selectedOrderForPopup.id);
        if (idx !== -1) {
          this.orders[idx].user_verdict = verdict;
          this.orders[idx].user_description = this.popupDecisionComment;
        }
        this.cdr.markForCheck();
      },
      error: (err) => {
        console.error('Failed to save order verdict', err);
        this.selectedOrderForPopup.user_verdict = verdict;
        this.selectedOrderForPopup.user_description = this.popupDecisionComment;

        const idx = this.orders.findIndex(o => o.id === this.selectedOrderForPopup.id);
        if (idx !== -1) {
          this.orders[idx].user_verdict = verdict;
          this.orders[idx].user_description = this.popupDecisionComment;
        }
        this.cdr.markForCheck();
      }
    });
  }

  getDynamicPopupSummary(): string {
    if (!this.selectedOrderForPopup) return '';
    const order = this.selectedOrderForPopup;
    if (order.user_verdict === 'TP') {
      return `User has validated this anomaly as a True Positive. Anomaly resolved based on provided justification: "${order.user_description || 'Confirmed anomaly.'}"`;
    } else if (order.user_verdict === 'FP') {
      return `User has cleared this order as a False Positive. The risk flags have been overridden and approved based on comment: "${order.user_description || 'Cleared false alarm.'}"`;
    }

    if (order.anomaly_status === 'unusual') {
      return `LightGBM analysis notes the client's order value of $${order.total_sales.toFixed(2)} is elevated, contributing to the suspicious fraud risk flag. Immediate review recommended before release.`;
    } else if (order.anomaly_status === 'delay anomaly') {
      return `Analysis indicates a critical shipping delay anomaly of ${order.delay_delta} days beyond scheduled shipment. Relational shared entity detection flags carrier bottleneck.`;
    } else {
      return `No unusual patterns detected. The order price ($${order.total_sales.toFixed(2)}) and shipping duration are within standard parameters.`;
    }
  }

  public tableSearchQuery: string = '';

  get filteredOrders(): any[] {
    const query = this.tableSearchQuery.trim().toLowerCase();
    if (!query) return this.orders;

    const cleanQuery = query.startsWith('so') ? query.substring(2) : query;
    return this.orders.filter(o => 
      o.id.toString().includes(cleanQuery) ||
      o.client_id.toString().toLowerCase().includes(query) ||
      o.status.toString().toLowerCase().includes(query) ||
      o.anomaly_status.toString().toLowerCase().includes(query) ||
      (o.category && o.category.toString().toLowerCase().includes(query))
    );
  }

  get paginatedOrders(): any[] {
    const startIndex = (this.currentPage - 1) * this.pageSize;
    return this.filteredOrders.slice(startIndex, startIndex + this.pageSize);
  }

  nextPage(): void {
    if (this.currentPage * this.pageSize < this.filteredOrders.length) {
      this.currentPage++;
    }
  }

  prevPage(): void {
    if (this.currentPage > 1) {
      this.currentPage--;
    }
  }

  getDisplayStartIndex(): number {
    if (this.filteredOrders.length === 0) return 0;
    return (this.currentPage - 1) * this.pageSize + 1;
  }

  getDisplayEndIndex(): number {
    return Math.min(this.currentPage * this.pageSize, this.filteredOrders.length);
  }

  onTableSearchChange(): void {
    this.currentPage = 1;
  }

  formatDateString(dStr: string): string {
    if (!dStr) return '';
    if (dStr.includes('T')) {
      return dStr.split('T')[0];
    }
    try {
      const parts = dStr.split(' ');
      const dateParts = parts[0].split('/');
      if (dateParts.length === 3) {
        const day = dateParts[0].padStart(2, '0');
        const month = dateParts[1].padStart(2, '0');
        const year = dateParts[2];
        return `${year}-${month}-${day}`;
      }
    } catch {}
    return dStr;
  }

  public calendarSearchQuery: string = '';

  filterCalendarEvents(): void {
    this.buildCalendarGrid();
  }

  // Build the monthly calendar grid mapping sales orders dates and delays
  buildCalendarGrid(): void {
    const parseOrderDateTo2026 = (dateStr: string): Date | null => {
      if (!dateStr) return null;
      try {
        if (dateStr.includes('T')) {
          const d = new Date(dateStr);
          d.setFullYear(2026);
          return d;
        }
        const parts = dateStr.split(' ');
        const dateParts = parts[0].split('/');
        if (dateParts.length === 3) {
          const m = parseInt(dateParts[0]) - 1; // month is 0-indexed in JS Date
          const d = parseInt(dateParts[1]);
          return new Date(2026, m, d);
        }
      } catch (e) {
        console.warn('Error parsing date:', dateStr, e);
      }
      const parsed = new Date(dateStr);
      if (!isNaN(parsed.getTime())) {
        parsed.setFullYear(2026);
        return parsed;
      }
      return null;
    };

    const addDays = (d: Date, days: number): Date => {
      const newDate = new Date(d.getTime());
      newDate.setDate(newDate.getDate() + days);
      return newDate;
    };

    const addDaysSkippingWeekends = (startDate: Date, days: number): { targetDate: Date, weekendDelayDays: number, weekendDates: Date[] } => {
      let currentDate = new Date(startDate.getTime());
      let weekendDelayDays = 0;
      const weekendDates: Date[] = [];

      // Skip weekend delay helper
      while (currentDate.getDay() === 0 || currentDate.getDay() === 6) {
        weekendDates.push(new Date(currentDate.getTime()));
        currentDate.setDate(currentDate.getDate() + 1);
        weekendDelayDays++;
      }

      // Add 'days' working days one by one, skipping weekends
      for (let i = 0; i < days; i++) {
        currentDate.setDate(currentDate.getDate() + 1);
        while (currentDate.getDay() === 0 || currentDate.getDay() === 6) {
          weekendDates.push(new Date(currentDate.getTime()));
          currentDate.setDate(currentDate.getDate() + 1);
          weekendDelayDays++;
        }
      }

      return { targetDate: currentDate, weekendDelayDays, weekendDates };
    };

    const formatDateStr = (d: Date): string => {
      const y = d.getFullYear();
      const m = (d.getMonth() + 1).toString().padStart(2, '0');
      const day = d.getDate().toString().padStart(2, '0');
      return `${y}-${m}-${day}`;
    };

    // Filter by SO number if search query is provided
    const query = this.calendarSearchQuery.trim().toLowerCase();
    const cleanQuery = query.startsWith('so') ? query.substring(2) : query;

    // Map sales orders to calendar events list
    const orderEvents: CalendarEvent[] = [];
    this.orders.forEach(o => {
      // Apply search query filter
      if (cleanQuery && !o.id.toString().includes(cleanQuery)) {
        return;
      }

      const delays = this.getOrderDynamicDelays(o);
      const orderDate = parseOrderDateTo2026(o.order_date);
      if (orderDate) {
        // if preparation start is Saturday/Sunday, push to Monday
        const prepStartResult = addDaysSkippingWeekends(orderDate, 0);
        const prepStartDate = prepStartResult.targetDate;

        const scheduledPrepResult = addDaysSkippingWeekends(prepStartDate, delays.prep_delay);
        const scheduledPrepDate = scheduledPrepResult.targetDate;

        const scheduledInternalResult = addDaysSkippingWeekends(scheduledPrepDate, delays.internal_delay);
        const scheduledInternalDate = scheduledInternalResult.targetDate;

        const scheduledResult = addDaysSkippingWeekends(scheduledInternalDate, delays.transport_delay);
        const scheduledDate = scheduledResult.targetDate;

        const scheduledDays = delays.prep_delay + delays.internal_delay + delays.transport_delay;

        orderEvents.push({
          title: `Order: SO${o.id}`,
          date: formatDateStr(orderDate),
          type: 'order_event',
          description: `Order placed on ${o.order_date}.`,
          orderId: o.id
        });

        orderEvents.push({
          title: `Prep Started: SO${o.id} (+${prepStartResult.weekendDelayDays}d)`,
          date: formatDateStr(prepStartDate),
          type: 'prep_start_event',
          description: `Order date: ${o.order_date}. Preparation started on ${formatDateStr(prepStartDate)}.`,
          orderId: o.id
        });

        orderEvents.push({
          title: `Internal Delay: SO${o.id} (+${delays.internal_delay + scheduledInternalResult.weekendDelayDays}d)`,
          date: formatDateStr(scheduledPrepDate),
          type: 'internal_delay_event',
          description: `Internal preparation delay of ${delays.internal_delay} working days (extended by ${scheduledInternalResult.weekendDelayDays} weekend days).`,
          orderId: o.id
        });

        orderEvents.push({
          title: `Transport Delay: SO${o.id} (+${delays.transport_delay + scheduledResult.weekendDelayDays}d)`,
          date: formatDateStr(scheduledInternalDate),
          type: 'transport_delay_event',
          description: `Transport transit delay of ${delays.transport_delay} working days (extended by ${scheduledResult.weekendDelayDays} weekend days).`,
          orderId: o.id
        });

        const isScheduledBarred = delays.real_shipment < scheduledDays;
        orderEvents.push({
          title: `Scheduled: SO${o.id}`,
          date: formatDateStr(scheduledDate),
          type: isScheduledBarred ? 'barred_scheduled' : 'scheduled_event',
          description: `Scheduled delivery in ${scheduledDays} working days (Prep: ${delays.prep_delay}d, Internal: ${delays.internal_delay}d, Transport: ${delays.transport_delay}d; total calendar days: ${scheduledDays + scheduledResult.weekendDelayDays}).`,
          orderId: o.id
        });

        const deliveryResult = addDaysSkippingWeekends(prepStartDate, delays.real_shipment);
        const deliveryDate = deliveryResult.targetDate;

        const timeDiff = deliveryDate.getTime() - scheduledDate.getTime();
        const calendarDelayDays = Math.max(0, Math.ceil(timeDiff / (1000 * 3600 * 24)));

        orderEvents.push({
          title: `Delivered: SO${o.id}`,
          date: formatDateStr(deliveryDate),
          type: 'delivered_event',
          description: `Actual shipment delivered. Delay from scheduled: ${calendarDelayDays} calendar days.`,
          orderId: o.id
        });

        if (calendarDelayDays > 0) {
          orderEvents.push({
            title: `Delay: SO${o.id} (+${calendarDelayDays}d)`,
            date: formatDateStr(deliveryDate),
            type: 'delivery_delay_event',
            description: `Shipment arrived ${calendarDelayDays} calendar days late (including weekends).`,
            orderId: o.id
          });
        }

        // Gray out any event for this order that occurs strictly after the actual delivery date
        const deliveryDateStr = formatDateStr(deliveryDate);
        orderEvents.forEach(ev => {
          if (ev.orderId === o.id && ev.date > deliveryDateStr) {
            ev.type = 'barred_scheduled';
          }
        });
      }
    });

    const fcEvents = orderEvents.map(e => ({
      title: e.title,
      start: e.date,
      className: [`event-${e.type}`, 'event-card'],
      extendedProps: {
        orderId: e.orderId,
        type: e.type,
        description: e.description || ''
      }
    }));

    this.calendarOptions = {
      ...this.calendarOptions,
      events: fcEvents
    };

    this.syncCalendarView();
  }

  private syncCalendarView(): void {
    if (this.fullcalendarComponent) {
      const monthStr = (this.currentMonth + 1).toString().padStart(2, '0');
      this.fullcalendarComponent.getApi().gotoDate(`${this.currentYear}-${monthStr}-01`);
    }
  }

  prevMonth(): void {
    if (this.currentYear === 2026 && this.currentMonth === 8) return;
    if (this.currentMonth === 0) {
      this.currentMonth = 11;
      this.currentYear--;
    } else {
      this.currentMonth--;
    }
    this.buildCalendarGrid();
  }

  nextMonth(): void {
    if (this.currentYear === 2026 && this.currentMonth === 11) return;
    if (this.currentMonth === 11) {
      this.currentMonth = 0;
      this.currentYear++;
    } else {
      this.currentMonth++;
    }
    this.buildCalendarGrid();
  }

  goToToday(): void {
    this.currentMonth = 8; // Default to Sept 2026 for demo data
    this.currentYear = 2026;
    this.buildCalendarGrid();
  }

  // Handle FullCalendar click on an event card
  handleCalendarEventClick(info: any): void {
    const extProps = info.event.extendedProps;
    if (extProps && extProps.orderId) {
      this.ngZone.run(() => {
        this.calendarSearchQuery = 'SO' + extProps.orderId;
        this.buildCalendarGrid();

        const orderObj = this.orders.find(o => o.id === extProps.orderId);
        if (orderObj) {
          this.selectScatterPointFromNeighbor(orderObj);
        }
      });
    }
  }

  // Build scatter plot
  buildScatterPlot(): void {
    if (this.orders.length === 0) return;

    // Filter positive sales/profit orders
    const validOrders = this.orders.filter(o => o.total_sales > 0);
    if (validOrders.length === 0) return;

    this.scatterPoints = validOrders.map(o => ({
      id: o.id,
      cx: 0,
      cy: 0,
      sales: o.total_sales,
      profit: o.order_profit,
      margin: (o.profit_margin ?? 0) * 100,   // convert to %
      delay:  o.delay_delta ?? 0,
      status: o.anomaly_status,
      client: o.client_id,
      category: o.category
    }));

    this.updateScatterChart();
  }

  updateScatterChart(): void {
    if (!this.scatterChartCanvas) return;
    const ctx = this.scatterChartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    const validData        = this.scatterPoints.filter(p => p.status === 'valid')       .map(p => ({ x: p.sales, y: p.margin, id: p.id, client: p.client, category: p.category, status: p.status, profit: p.profit }));
    const unusualData       = this.scatterPoints.filter(p => p.status === 'unusual')      .map(p => ({ x: p.sales, y: p.margin, id: p.id, client: p.client, category: p.category, status: p.status, profit: p.profit }));
    const delayAnomalyData  = this.scatterPoints.filter(p => p.status === 'delay anomaly').map(p => ({ x: p.sales, y: p.margin, id: p.id, client: p.client, category: p.category, status: p.status, profit: p.profit }));

    const selectedData = this.selectedScatterPoint ? [{
      x: this.selectedScatterPoint.sales,
      y: this.selectedScatterPoint.margin,
      id: this.selectedScatterPoint.id,
      client: this.selectedScatterPoint.client,
      category: this.selectedScatterPoint.category,
      status: this.selectedScatterPoint.status,
      profit: this.selectedScatterPoint.profit
    }] : [];

    if (this.scatterChart) {
      this.scatterChart.data.datasets[0].data = validData;
      this.scatterChart.data.datasets[1].data = unusualData;
      this.scatterChart.data.datasets[2].data = delayAnomalyData;
      this.scatterChart.data.datasets[3].data = selectedData;
      this.scatterChart.update();
    } else {
      this.scatterChart = new Chart(ctx, {
        type: 'scatter',
        data: {
          datasets: [
            {
              label: 'Valid',
              data: validData,
              backgroundColor: '#10b981',
              pointRadius: 6,
              pointHoverRadius: 8,
              order: 3
            },
            {
              label: 'Unusual (LightGBM)',
              data: unusualData,
              backgroundColor: '#ef4444',
              pointRadius: 6,
              pointHoverRadius: 8,
              order: 1
            },
            {
              label: 'Delay Anomaly',
              data: delayAnomalyData,
              backgroundColor: '#f59e0b',
              pointRadius: 6,
              pointHoverRadius: 8,
              order: 2
            },
            {
              label: 'Selected',
              data: selectedData,
              backgroundColor: '#2563eb',
              pointRadius: 9,
              pointHoverRadius: 11,
              borderColor: '#ffffff',
              borderWidth: 2,
              order: 0
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
                label: (context) => {
                  const pt = context.raw as any;
                  const marginStr = pt.y != null ? `${pt.y.toFixed(1)}%` : 'N/A';
                  return `SO${pt.id} | Sales: $${(pt.x||0).toFixed(0)}, Margin: ${marginStr}, Profit: $${(pt.profit||0).toFixed(0)}`;
                }
              }
            }
          },
          scales: {
            x: {
              type: 'logarithmic',
              title: { display: true, text: 'SALES VOLUME ($)', color: '#64748b', font: { weight: 'bold', size: 10 } },
              grid: { color: '#f1f5f9' },
              ticks: {
                color: '#64748b',
                callback: (v: any) => {
                  if (v === 100 || v === 500 || v === 1000 || v === 5000 || v === 10000 || v === 25000) {
                    return v >= 1000 ? `$${v/1000}k` : `$${v}`;
                  }
                  return '';
                }
              }
            },
            y: {
              title: { display: true, text: 'PROFIT MARGIN (%)', color: '#64748b', font: { weight: 'bold', size: 10 } },
              grid: { color: '#f1f5f9' },
              ticks: { color: '#64748b', callback: (v: any) => `${v}%` }
            }
          },
          onClick: (event, elements) => {
            if (elements.length > 0) {
              const datasetIndex = elements[0].datasetIndex;
              const index = elements[0].index;
              const rawPt = this.scatterChart?.data.datasets[datasetIndex].data[index] as any;
              if (rawPt) {
                const matchedPt = this.scatterPoints.find(p => p.id === rawPt.id);
                if (matchedPt) {
                  this.ngZone.run(() => {
                    this.selectScatterPoint(matchedPt);
                  });
                }
              }
            }
          }
        },
        plugins: [
          {
            id: 'neighborLines',
            afterDraw: (chart) => {
              if (!this.selectedScatterPoint || this.nearestNeighbors.length === 0) return;
              
              const ctx = chart.ctx;
              const xAxis = chart.scales['x'];
              const yAxis = chart.scales['y'];
              
              // Get coordinates of selected point
              const selectedX = xAxis.getPixelForValue(this.selectedScatterPoint.sales);
              const selectedY = yAxis.getPixelForValue(this.selectedScatterPoint.margin);
              
              ctx.save();
              ctx.strokeStyle = '#6366f1';
              ctx.lineWidth = 1.5;
              ctx.setLineDash([3, 3]);
              ctx.globalAlpha = 0.7;
              
              this.nearestNeighbors.forEach(n => {
                const neighborPt = this.scatterPoints.find(p => p.id === n.order.id);
                if (neighborPt) {
                  const neighborX = xAxis.getPixelForValue(neighborPt.sales);
                  const neighborY = yAxis.getPixelForValue(neighborPt.margin);
                  
                  ctx.beginPath();
                  ctx.moveTo(selectedX, selectedY);
                  ctx.lineTo(neighborX, neighborY);
                  ctx.stroke();
                }
              });
              
              ctx.restore();
            }
          }
        ]
      });
    }
  }

  updateDiscountChart(): void {
    if (!this.discountChartCanvas) return;
    const ctx = this.discountChartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    const token = this.auth.getToken();
    const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });

    this.getWithCache<any>('/api/orders/discount-analysis', headers, (res) => {
      const labels = res.labels;
      const revenueData = res.revenue;
      const unitsSoldData = res.units_sold;

      if (this.discountChart) {
        this.discountChart.data.datasets[0].data = revenueData;
        this.discountChart.data.datasets[1].data = unitsSoldData;
        this.discountChart.update();
      } else {
        this.discountChart = new Chart(ctx, {
          type: 'line',
          data: {
            labels: labels,
            datasets: [
              {
                label: 'Revenue',
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
                label: 'Units Sold',
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
                title: { display: true, text: 'REVENUE', color: '#64748b', font: { weight: 'bold', size: 10 } },
                grid: { color: '#f1f5f9' },
                ticks: {
                  color: '#64748b',
                  callback: (value) => `$${Number(value) / 1000}k`
                }
              },
              y1: {
                position: 'right',
                title: { display: true, text: 'UNITS SOLD', color: '#64748b', font: { weight: 'bold', size: 10 } },
                grid: { display: false },
                ticks: { color: '#64748b' }
              }
            }
          }
        });
      }
    }, (err) => {
      console.error('Error loading discount analysis:', err);
    });
  }

  selectScatterPoint(pt: ScatterPoint): void {
    this.selectedScatterPoint = pt;
    
    // Find order details
    const orderObj = this.orders.find(o => o.id === pt.id);
    if (orderObj) {
      this.selectedOrderQuantity = orderObj.total_quantity || 0;
      this.selectedOrderDelay = orderObj.delay_delta || 0;
    }
    
    const idx = this.orders.findIndex(o => o.id === pt.id);
    if (idx !== -1) {
      this.currentPage = Math.floor(idx / this.pageSize) + 1;
    }

    // Filter calendar events to this SO
    this.calendarSearchQuery = 'SO' + pt.id;
    this.buildCalendarGrid();

    this.computeNearestNeighbors(pt);
    this.updateScatterChart(); // Redraw scatter chart to show selected border
    this.cdr.detectChanges(); // Force Angular to update UI views immediately
  }

  computeNearestNeighbors(selectedPt: ScatterPoint): void {
    const selectedOrder = this.orders.find(o => o.id === selectedPt.id);
    if (!selectedOrder) return;

    const normSelected = {
      sales: (selectedOrder.total_sales - this.minSales) / (this.maxSales - this.minSales || 1),
      margin: (selectedOrder.profit_margin - this.minProfitMargin) / (this.maxProfitMargin - this.minProfitMargin || 1),
      quantity: (selectedOrder.total_quantity - this.minQuantity) / (this.maxQuantity - this.minQuantity || 1),
      delay: (selectedOrder.delay_delta - this.minDelay) / (this.maxDelay - this.minDelay || 1)
    };

    const distances = this.orders
      .filter(o => o.id !== selectedPt.id)
      .map(o => {
        const normO = {
          sales: (o.total_sales - this.minSales) / (this.maxSales - this.minSales || 1),
          margin: (o.profit_margin - this.minProfitMargin) / (this.maxProfitMargin - this.minProfitMargin || 1),
          quantity: (o.total_quantity - this.minQuantity) / (this.maxQuantity - this.minQuantity || 1),
          delay: (o.delay_delta - this.minDelay) / (this.maxDelay - this.minDelay || 1)
        };
        
        const dist = Math.sqrt(
          Math.pow(normSelected.sales - normO.sales, 2) +
          Math.pow(normSelected.margin - normO.margin, 2) +
          Math.pow(normSelected.quantity - normO.quantity, 2) +
          Math.pow(normSelected.delay - normO.delay, 2)
        );
        
        const pt = this.scatterPoints.find(p => p.id === o.id);
        
        return {
          order: o,
          dist: dist,
          cx: pt ? pt.cx : 0,
          cy: pt ? pt.cy : 0
        };
      });

    distances.sort((a, b) => a.dist - b.dist);
    this.nearestNeighbors = distances.slice(0, 5);
  }

  getUnusualNeighborCount(): number {
    return this.nearestNeighbors.filter(n => n.order.anomaly_status === 'unusual').length;
  }

  selectScatterPointFromNeighbor(order: any): void {
    const pt = this.scatterPoints.find(p => p.id === order.id);
    if (pt) {
      this.selectScatterPoint(pt);
    }
  }

  isNeighbor(orderId: number): boolean {
    return this.nearestNeighbors.some(n => n.order.id === orderId);
  }

  getFeatureBarWidth(val: number, avg: number): number {
    if (avg === 0) return 0;
    if (val < 0) {
      return Math.max(0, 25 + (val / Math.abs(avg)) * 25);
    }
    const ratio = val / avg;
    return Math.min(100, Math.max(0, ratio * 50));
  }


  importfn(): void {
    console.log("importfn click handler triggered. Setting isImportModalOpen to true.");
    this.isImportModalOpen = true;
    this.selectedFileForImport = null;
    this.cdr.detectChanges();
  }

  closeImportModal(): void {
    this.isImportModalOpen = false;
    this.selectedFileForImport = null;
    this.cdr.detectChanges();
  }

  downloadTemplate(): void {
    const token = this.auth.getToken();
    if (!token) return;
    const headers = new HttpHeaders().set('Authorization', 'Bearer ' + token);
    
    this.http.get('/api/orders/download-template', {
      headers,
      responseType: 'blob'
    }).subscribe({
      next: (blob: Blob) => {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'test_orders_new.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        window.URL.revokeObjectURL(url);
      },
      error: (err) => {
        window.alert('Download failed: ' + (err.message || 'Error occurred.'));
      }
    });
  }

  triggerFileInput(): void {
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.csv, .xlsx, .xls';
    fileInput.style.display = 'none';

    fileInput.addEventListener('change', (event: Event) => {
      const target = event.target as HTMLInputElement;
      const file = target.files?.[0];
      if (file) {
        this.ngZone.run(() => {
          this.selectedFileForImport = file;
          this.cdr.detectChanges();
        });
      }
      fileInput.remove();
    });

    document.body.appendChild(fileInput);
    fileInput.click();
  }

  removeSelectedFile(): void {
    this.selectedFileForImport = null;
    this.cdr.detectChanges();
  }

  formatBytes(bytes: number): string {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  }

  validateUploadedFile(): void {
    if (!this.selectedFileForImport) return;
    const file = this.selectedFileForImport;

    const token = this.auth.getToken();
    if (!token) {
      window.alert("Authentication error: Please log in again.");
      return;
    }

    const formData = new FormData();
    formData.append('file', file);

    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.post<any>('/api/orders/validate', formData, { headers }).subscribe({
      next: (res) => {
        if (res.status === 'success') {
          this.selectedFileName = file.name;
          this.validationCount = res.order_count;
          this.validationColumns = res.columns.join(', ');
          
          this.isImportModalOpen = false;
          this.isConfirmModalOpen = true;
          this.cdr.detectChanges();
        } else {
          this.validationErrorMessage = res.message;
          this.isImportModalOpen = false;
          this.isValidationErrorModalOpen = true;
          this.cdr.detectChanges();
        }
      },
      error: (err) => {
        this.validationErrorMessage = err.error?.detail || err.message || 'Server connection error during validation.';
        this.isImportModalOpen = false;
        this.isValidationErrorModalOpen = true;
        this.cdr.detectChanges();
      }
    });
  }

  closeConfirmModal(): void {
    this.isConfirmModalOpen = false;
    this.selectedFileForImport = null;
    this.cdr.detectChanges();
  }

  cancelConfirmModal(): void {
    this.isConfirmModalOpen = false;
    this.isImportModalOpen = true;
    this.cdr.detectChanges();
  }

  closeValidationErrorModal(): void {
    this.isValidationErrorModalOpen = false;
    this.isImportModalOpen = true;
    this.cdr.detectChanges();
  }

  // Close the retraining status view without interrupting the background process.
  // The user gets to keep working while the ML pipeline trains silently out-of-band. Sweet!
  closeRetrainStatusModal(): void {
    this.isRetrainStatusModalOpen = false;
    this.cdr.detectChanges();
  }

  // Pre-flight check passed! Let's swap the confirmation modal for the progress tracker
  // and trigger the actual backend ingestion.
  confirmAndExecuteImport(): void {
    if (!this.selectedFileForImport) return;
    const file = this.selectedFileForImport;
    this.isConfirmModalOpen = false;
    
    this.isRetrainStatusModalOpen = true;
    this.isImporting = true;
    this.importProgress = 10;
    this.importStatusMessage = "Uploading file & saving orders...";
    this.stepsCompleted = 0;
    this.cdr.detectChanges();

    this.executeImport(file);
  }

  // Fires off the upload payload. Note: The backend processes the DataFrame, handles 
  // column deduplication, and forks the ML retraining task to an async OS subprocess.
  // We use nested timeouts to coordinate the visual stage transition for the user.
  executeImport(file: File): void {
    const token = this.auth.getToken();
    if (!token) return;

    const formData = new FormData();
    formData.append('file', file);

    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    this.http.post<any>('/api/orders/import', formData, { headers }).subscribe({
      next: (res) => {
        this.isImporting = false;
        try {
          localStorage.removeItem('dashboard_cache_data');
        } catch (e) {
          console.error('Error clearing dashboard cache:', e);
        }
        this.loadDashboardData();
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.isImporting = false;
        window.alert('Import failed: ' + (err.error?.detail || err.message || 'Error occurred.'));
        this.closeRetrainStatusModal();
        this.cdr.detectChanges();
      }
    });
  }
}
