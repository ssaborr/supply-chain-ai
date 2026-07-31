import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { BehaviorSubject, Observable, tap, catchError, of, map, switchMap } from 'rxjs';

export interface UserState {
  id: string;
  first_name: string;
  last_name: string;
  email: string;
  role: string;
  supplier_name?: string;
  allowed_tabs?: string[];
}

@Injectable({
  providedIn: 'root',
})
export class Auth {
  private http = inject(HttpClient);
  private apiUrl = 'http://127.0.0.1:8000/api';
  
  private userStateSubject = new BehaviorSubject<UserState | null | undefined>(undefined);
  public userState$ = this.userStateSubject.asObservable();

  constructor() {
    this.checkAuth().subscribe();
  }
  login(email: string, password: string): Observable<any> {
    const body = { email, password };

    return this.http.post<any>(
      `${this.apiUrl}/auth/login`,
      body
    ).pipe(
      tap(response => {
        if (response.status !== 'face_verification_required') {
          localStorage.setItem('access_token', response.access_token);
        }
      }),
      switchMap(response => {
        if (response.status === 'face_verification_required') {
          return of(response);
        }
        return this.fetchCurrentUser();
      })
    );
  }

  loginFace(image: string, email?: string): Observable<UserState | null> {
    const body = { image, email: email || null };

    return this.http.post<{ access_token: string; token_type: string }>(
      `${this.apiUrl}/auth/login-face`,
      body
    ).pipe(
      tap(response => {
        localStorage.setItem('access_token', response.access_token);
      }),
      switchMap(() => this.fetchCurrentUser())
    );
  }

  logout(): void {
    localStorage.removeItem('access_token');
    this.userStateSubject.next(null);
  }

  fetchCurrentUser(): Observable<UserState | null> {
    const token = localStorage.getItem('access_token');
    if (!token) {
      this.userStateSubject.next(null);
      return of(null);
    }

    const headers = new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });

    return this.http.get<UserState>(`${this.apiUrl}/auth/me`, { headers }).pipe(
      tap(user => {
        this.userStateSubject.next(user);
      }),
      catchError(() => {
        this.logout();
        return of(null);
      })
    );
  }

  /* Helper to verify if token is valid and restore admin session*/
  checkAuth(): Observable<boolean> {
    return this.fetchCurrentUser().pipe(
      map(user => !!user)
    );
  }

  getToken(): string | null {
    return localStorage.getItem('access_token');
  }


  isAuthenticated(): boolean {
    return this.userStateSubject.value !== null;
  }

}

