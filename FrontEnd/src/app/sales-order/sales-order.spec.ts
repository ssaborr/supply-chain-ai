import { ComponentFixture, TestBed } from '@angular/core/testing';

import { SalesOrder } from './sales-order';

describe('SalesOrder', () => {
  let component: SalesOrder;
  let fixture: ComponentFixture<SalesOrder>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [SalesOrder]
    })
    .compileComponents();

    fixture = TestBed.createComponent(SalesOrder);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
