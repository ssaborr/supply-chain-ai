import { Component, OnInit, inject, ViewChild, ElementRef, AfterViewInit, ChangeDetectorRef } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Auth, UserState } from '../../services/auth';
import { I18nService } from '../../services/i18n';

import { FullCalendarModule, FullCalendarComponent } from '@fullcalendar/angular';
import { DisplayDatePipe } from '../../pipes/display-date.pipe';
import { TranslatePipe } from '../../pipes/translate.pipe';
import {
  displayYear,
  formatDateForDisplay,
  formatDateFromDateForDisplay,
  shiftDateForDisplay,
} from '../../utils/display-date';
import { CalendarOptions } from '@fullcalendar/core';
import dayGridPlugin from '@fullcalendar/daygrid';
import interactionPlugin from '@fullcalendar/interaction';

import { Chart } from 'chart.js/auto';

interface CalendarEvent {
  title: string;
  date: string;
  type: string;
  description?: string;
  orderId?: number;
}

@Component({
  selector: 'app-supplier',
  imports: [CommonModule, FormsModule, FullCalendarModule,  TranslatePipe],
  templateUrl: './supplier.html',
  styleUrl: './supplier.css',
  standalone: true
})
export class Supplier implements OnInit, AfterViewInit {
  private auth = inject(Auth);
  private http = inject(HttpClient);
  private cdr = inject(ChangeDetectorRef);
  private i18n = inject(I18nService);

  @ViewChild('fullcalendar') fullcalendarComponent?: FullCalendarComponent;
  
  private _stockChartCanvas?: ElementRef<HTMLCanvasElement>;
  private _leadTimeChartCanvas?: ElementRef<HTMLCanvasElement>;

  @ViewChild('stockChartCanvas') set stockCanvas(content: ElementRef<HTMLCanvasElement> | undefined) {
    if (content) {
      this._stockChartCanvas = content;
      setTimeout(() => this.updateStockChart(), 0);
    }
  }

  @ViewChild('leadTimeChartCanvas') set leadTimeCanvas(content: ElementRef<HTMLCanvasElement> | undefined) {
    if (content) {
      this._leadTimeChartCanvas = content;
      setTimeout(() => this.updateLeadTimeChart(), 0);
    }
  }

  get stockChartCanvas(): ElementRef<HTMLCanvasElement> | undefined {
    return this._stockChartCanvas;
  }

  get leadTimeChartCanvas(): ElementRef<HTMLCanvasElement> | undefined {
    return this._leadTimeChartCanvas;
  }

  private stockChart: Chart | null = null;
  private leadTimeChart: Chart | null = null;

  public user: UserState | null = null;
  public isAdmin: boolean = false;
  public suppliersList: string[] = [];
  public selectedSupplier: string = '';
  public isLoading: boolean = false;
  public errorMsg: string | null = null;

  public kpis: any = null;
  public salesOrders: any[] = [];
  public products: any[] = [];
  public lowStockItems: any[] = [];
  public aiExplanation: string = '';

  public filteredOrders: any[] = [];
  public searchOrderQuery: string = '';
  public statusFilter: string = 'ALL';
  public currentPage: number = 1;
  public pageSize: number = 10;
  public totalOrdersCount: number = 0;

  public currentMonth: number = 8; // September (8)
  public currentYear: number = 2026;

  get displayCurrentYear(): number {
    return displayYear(this.currentYear);
  }

  public calendarSearchQuery: string = '';
  public selectedCalendarEvent: CalendarEvent | null = null;

  public monthNames = [
    'January', 'February', 'March', 'April', 'May', 'June',
    'July', 'August', 'September', 'October', 'November', 'December'
  ];

  calendarOptions: CalendarOptions = {
    initialView: 'dayGridMonth',
    plugins: [dayGridPlugin, interactionPlugin],
    initialDate: '2026-09-01',
    headerToolbar: false,
    editable: false,
    selectable: false,
    dayMaxEvents: 3,
    events: [],
    eventClick: this.handleCalendarEventClick.bind(this)
  };

  ngOnInit(): void {
    this.auth.userState$.subscribe(user => {
      if (user) {
        this.user = user;
        this.isAdmin = user.role === 'admin' || user.role === 'manager';
        
        if (this.isAdmin) {
          this.loadSuppliersList();
        } else {
          // filter to supplier name
          this.selectedSupplier = user.supplier_name || 'Nike Manufacturing EU';
          this.loadDashboardData();
        }
      }
    });
  }

  ngAfterViewInit(): void {
    // set up initial chart components
    this.updateStockChart();
    this.updateLeadTimeChart();
  }

  private loadSuppliersList(): void {
    const token = this.auth.getToken();
    if (!token) return;
    const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });

    this.http.get<string[]>('/api/supplier/list', { headers }).subscribe({
      next: (list) => {
        this.suppliersList = list;
        if (list.length > 0) {
          this.selectedSupplier = list[0];
          this.loadDashboardData();
        }
      },
      error: (err) => {
        console.error('Error loading suppliers list:', err);
      }
    });
  }

  public loadDashboardData(): void {
    if (!this.selectedSupplier) return;
    this.isLoading = true;
    this.errorMsg = null;

    const token = this.auth.getToken();
    if (!token) {
      this.isLoading = false;
      return;
    }
    const headers = new HttpHeaders({ 'Authorization': `Bearer ${token}` });

    const url = `/api/supplier/dashboard-data?supplier_name=${encodeURIComponent(this.selectedSupplier)}${this.i18n.apiLanguageQuery('&')}`;
    this.http.get<any>(url, { headers }).subscribe({
      next: (data) => {
        this.kpis = data.kpis;
        this.salesOrders = data.sales_orders;
        this.products = data.products;
        this.lowStockItems = data.low_stock_items;
        this.aiExplanation = data.ai_explanation;

        this.filteredOrders = [...this.salesOrders];
        this.totalOrdersCount = this.salesOrders.length;
        this.currentPage = 1;
        this.searchOrderQuery = '';
        this.statusFilter = 'ALL';

        this.buildCalendarGrid();
        this.updateStockChart();
        this.updateLeadTimeChart();
        
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Error loading supplier data:', err);
        this.errorMsg = 'Failed to load supplier dashboard metrics.';
        this.isLoading = false;
        this.cdr.detectChanges();
      }
    });
  }

  filterOrders(): void {
    let result = [...this.salesOrders];

    const query = this.searchOrderQuery.trim().toLowerCase();
    if (query) {
      result = result.filter(o => o.id.toString().includes(query));
    }

    if (this.statusFilter !== 'ALL') {
      result = result.filter(o => {
        if (this.statusFilter === 'VALID') return o.anomaly_status === 'valid';
        if (this.statusFilter === 'DELAY ANOMALY') return o.anomaly_status === 'delay anomaly';
        if (this.statusFilter === 'UNUSUAL') return o.anomaly_status === 'unusual';
        return true;
      });
    }

    this.filteredOrders = result;
    this.totalOrdersCount = result.length;
    this.currentPage = 1;
  }

  get paginatedOrders(): any[] {
    const startIndex = (this.currentPage - 1) * this.pageSize;
    return this.filteredOrders.slice(startIndex, startIndex + this.pageSize);
  }

  totalPages(): number {
    return Math.ceil(this.totalOrdersCount / this.pageSize) || 1;
  }

  prevPage(): void {
    if (this.currentPage > 1) this.currentPage--;
  }

  nextPage(): void {
    if (this.currentPage < this.totalPages()) this.currentPage++;
  }

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
          const m = parseInt(dateParts[0]) - 1;
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

    const addDaysSkippingWeekends = (startDate: Date, days: number): { targetDate: Date, weekendDelayDays: number, weekendDates: Date[] } => {
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

    const formatDateStr = (d: Date): string => {
      const y = d.getFullYear();
      const m = (d.getMonth() + 1).toString().padStart(2, '0');
      const day = d.getDate().toString().padStart(2, '0');
      return `${y}-${m}-${day}`;
    };

    const query = this.calendarSearchQuery.trim().toLowerCase();
    const cleanQuery = query.startsWith('so') ? query.substring(2) : query;//normalize so with or without it

    const orderEvents: CalendarEvent[] = [];
    // build calendar event stream
    this.salesOrders.forEach(o => {
      if (cleanQuery && !o.id.toString().includes(cleanQuery)) {
        return;
      }

      const orderDate = parseOrderDateTo2026(o.order_date);
      if (orderDate) {
        const prepStartResult = addDaysSkippingWeekends(orderDate, 0);// add weekend delays
        const prepStartDate = prepStartResult.targetDate;

        if (prepStartResult.weekendDelayDays > 0) {
          // add weekend delay as event in order events
          prepStartResult.weekendDates.forEach(wd => {
            orderEvents.push({
              title: `Weekend Delay: SO${o.id} (Prep Start)`,
              date: formatDateStr(wd),
              type: 'delay',
              description: `Preparation start delayed by weekend. No operations on weekends.`,
              orderId: o.id
            });
          });
        }

        orderEvents.push({
          title: `Prep: SO${o.id}`,
          date: formatDateStr(prepStartDate),
          type: 'meeting',
          description: `Order date: ${formatDateForDisplay(o.order_date)}. Preparation started on ${formatDateFromDateForDisplay(prepStartDate)}.`,
          orderId: o.id
        });

        let internalDelayDate = prepStartDate;
        if (o.internalDelay > 0) {
          const internalDelayResult = addDaysSkippingWeekends(prepStartDate, o.internalDelay);
          internalDelayDate = internalDelayResult.targetDate;

          if (internalDelayResult.weekendDelayDays > 0) {
            internalDelayResult.weekendDates.forEach(wd => {
              orderEvents.push({
                title: `Weekend Delay: SO${o.id} (+${internalDelayResult.weekendDelayDays}d)`,
                date: formatDateStr(wd),
                type: 'delay',
                description: `Internal preparation delayed by weekend.`,
                orderId: o.id
              });
            });
          }

          orderEvents.push({
            title: `Prep Delay: SO${o.id} (+${o.internalDelay + internalDelayResult.weekendDelayDays}d)`,
            date: formatDateStr(internalDelayDate),
            type: 'delay',
            description: `Internal preparation delay of ${o.internalDelay} working days (extended by ${internalDelayResult.weekendDelayDays} weekend days).`,
            orderId: o.id
          });
        }

        const scheduledResult = addDaysSkippingWeekends(prepStartDate, o.scheduled_shipment);
        const scheduledDate = scheduledResult.targetDate;

        if (scheduledResult.weekendDelayDays > 0) {
          scheduledResult.weekendDates.forEach(wd => {
            const alreadyAdded = orderEvents.some(e => e.orderId === o.id && e.date === formatDateStr(wd) && e.title.includes('Weekend Delay'));
            if (!alreadyAdded) {
              orderEvents.push({
                title: `Weekend Delay: SO${o.id} (Scheduled)`,
                date: formatDateStr(wd),
                type: 'delay',
                description: `Shipment scheduling affected by weekend.`,
                orderId: o.id
              });
            }
          });
        }

        orderEvents.push({
          title: `Scheduled: SO${o.id}`,
          date: formatDateStr(scheduledDate),
          type: 'high_demand',
          description: `Scheduled shipment in ${o.scheduled_shipment} working days (total calendar days: ${o.scheduled_shipment + scheduledResult.weekendDelayDays}).`,
          orderId: o.id
        });

        const deliveryResult = addDaysSkippingWeekends(prepStartDate, o.real_shipment);
        const deliveryDate = deliveryResult.targetDate;

        if (deliveryResult.weekendDelayDays > 0) {
          deliveryResult.weekendDates.forEach(wd => {
            const alreadyAdded = orderEvents.some(e => e.orderId === o.id && e.date === formatDateStr(wd) && e.title.includes('Weekend Delay'));
            if (!alreadyAdded) {
              orderEvents.push({
                title: `Weekend Delay: SO${o.id} (Delivery)`,
                date: formatDateStr(wd),
                type: 'delay',
                description: `Shipment delivery affected by weekend.`,
                orderId: o.id
              });
            }
          });
        }

        orderEvents.push({
          title: `Delivered: SO${o.id}`,
          date: formatDateStr(deliveryDate),
          type: 'custom',
          description: `Actual shipment delivered in ${o.real_shipment} working days (total calendar days: ${o.real_shipment + deliveryResult.weekendDelayDays}).`,
          orderId: o.id
        });

        if (o.transportDelay > 0) {
          orderEvents.push({
            title: `Transport Delay: SO${o.id} (+${o.transportDelay}d)`,
            date: formatDateStr(deliveryDate),
            type: 'delay',
            description: `Transport transit delay of ${o.transportDelay} days.`,
            orderId: o.id
          });
        }

        const timeDiff = deliveryDate.getTime() - scheduledDate.getTime();//time diff in milliseconds
        const calendarDelayDays = Math.ceil(timeDiff / (1000 * 3600 * 24));//convert to days
        if (calendarDelayDays > 0) {
          orderEvents.push({
            title: `Delay: SO${o.id} (+${calendarDelayDays}d)`,
            date: formatDateStr(deliveryDate),
            type: 'delay',
            description: `Shipment arrived ${calendarDelayDays} calendar days late (including weekends).`,
            orderId: o.id
          });
        }
      }
    });

    // mount list of events onto FullCalendar instance
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
    this.currentMonth = 8;
    this.currentYear = 2026;
    this.buildCalendarGrid();
  }

  formatDateString(dStr: string): string {
    return formatDateForDisplay(dStr);
  }

  handleCalendarEventClick(info: any): void {
    const extProps = info.event.extendedProps;
    this.selectedCalendarEvent = {
      title: info.event.title,
      date: info.event.startStr,
      type: extProps.type,
      description: extProps.description,
      orderId: extProps.orderId
    };
  }

  filterCalendarEvents(): void {
    this.buildCalendarGrid();
  }

  closeEventPopup(): void {
    this.selectedCalendarEvent = null;
  }

  private updateStockChart(): void {
    if (!this.stockChartCanvas) return;
    const ctx = this.stockChartCanvas.nativeElement.getContext('2d');//opens a drawing context on the canvas
    if (!ctx) return;

    if (this.stockChart) {
      this.stockChart.destroy();
    }

    if (this.products.length === 0) return;

    const labels = this.products.map(p => p.name.length > 20 ? p.name.substring(0, 18) + '...' : p.name);
    const stocks = this.products.map(p => p.current_stock);
    const safetyStocks = this.products.map(p => p.reorder_point || 120);

    this.stockChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Current Stock Level',
            data: stocks,
            backgroundColor: this.products.map(p => p.current_stock < (p.reorder_point || 120) ? 'rgba(239, 68, 68, 0.75)' : 'rgba(20, 184, 166, 0.75)'),
            borderColor: this.products.map(p => p.current_stock < (p.reorder_point || 120) ? 'rgb(239, 68, 68)' : 'rgb(20, 184, 166)'),
            borderWidth: 1.5,
            borderRadius: 4
          },
          {
            label: 'Dynamic Reorder Point (ROP)',
            data: safetyStocks,
            type: 'line',
            borderColor: 'rgba(245, 158, 11, 0.8)',
            borderWidth: 2,
            borderDash: [5, 5],
            fill: false,
            pointStyle: 'none',
            pointRadius: 0
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            labels: { color: '#475569', font: { family: 'Inter', size: 11 } }
          }
        },
        scales: {
          y: {
            grid: { color: '#f1f5f9' },
            ticks: { color: '#475569', font: { family: 'Inter', size: 10 } }
          },
          x: {
            grid: { display: false },
            ticks: { color: '#475569', font: { family: 'Inter', size: 9 }, maxRotation: 45, minRotation: 45 }
          }
        }
      }
    });
  }

  private updateLeadTimeChart(): void {
    if (!this.leadTimeChartCanvas) return;
    const ctx = this.leadTimeChartCanvas.nativeElement.getContext('2d');
    if (!ctx) return;

    if (this.leadTimeChart) {
      this.leadTimeChart.destroy();
    }

    let onTimeSales = 0;
    let slightDelaySales = 0;
    let severeDelaySales = 0;

    this.salesOrders.forEach(o => {
      const delay = o.delay_delta || 0;
      if (delay <= 0) onTimeSales++;
      else if (delay <= 3) slightDelaySales++;
      else severeDelaySales++;
    });

    if (onTimeSales === 0 && slightDelaySales === 0 && severeDelaySales === 0) {
      onTimeSales = 1; // Default fallback to render chart nicely
    }

    this.leadTimeChart = new Chart(ctx, {
      type: 'doughnut',
      data: {
        labels: ['On-time (<=0d)', 'Minor Delay (1-3d)', 'Critical Delay (>3d)'],
        datasets: [{
          data: [onTimeSales, slightDelaySales, severeDelaySales],
          backgroundColor: [
            'rgba(20, 184, 166, 0.8)',   // Teal
            'rgba(245, 158, 11, 0.8)',   // Amber
            'rgba(239, 68, 68, 0.8)'     // Red
          ],
          borderColor: ['#fff', '#fff', '#fff'],
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { color: '#475569', font: { family: 'Inter', size: 11 } }
          }
        }
      }
    });
  }
}
