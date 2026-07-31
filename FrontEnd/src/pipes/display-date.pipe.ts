import { Pipe, PipeTransform } from '@angular/core';
import { displayYear, shiftDateForDisplay } from '../utils/display-date';

@Pipe({ name: 'displayDate', standalone: true })
export class DisplayDatePipe implements PipeTransform {
  transform(value: string | number | null | undefined): string {
    if (value == null || value === '') return '';
    if (typeof value === 'number') return String(displayYear(value));
    return shiftDateForDisplay(String(value));
  }
}
