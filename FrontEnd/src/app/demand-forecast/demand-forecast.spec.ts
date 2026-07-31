import { ComponentFixture, TestBed } from '@angular/core/testing';

import { DemandForecast } from './demand-forecast';

describe('DemandForecast', () => {
  let component: DemandForecast;
  let fixture: ComponentFixture<DemandForecast>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [DemandForecast]
    })
    .compileComponents();

    fixture = TestBed.createComponent(DemandForecast);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
