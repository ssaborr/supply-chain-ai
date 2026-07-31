import { ComponentFixture, TestBed } from '@angular/core/testing';

import { Segmentation } from './segmentation';

describe('Segmentation', () => {
  let component: Segmentation;
  let fixture: ComponentFixture<Segmentation>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [Segmentation]
    })
    .compileComponents();

    fixture = TestBed.createComponent(Segmentation);
    component = fixture.componentInstance;
    await fixture.whenStable();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
