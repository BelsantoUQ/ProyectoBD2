import { Injectable } from '@angular/core';
import { HttpClient, HttpHeaders } from '@angular/common/http';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class EstudiantesServicioService {

  private apiUrl = 'http://localhost:8000/examenes-asignados'; // Reemplaza con tu URL de API

  constructor(private http: HttpClient) {}

  private getHeaders(): HttpHeaders {
    const token = localStorage.getItem('authToken');
    return new HttpHeaders({
      'Authorization': `Bearer ${token}`
    });
  }

  obtenerExamenesNoPresentados(): Observable<any[]> {
    const headers = this.getHeaders();
    return this.http.get<any[]>(this.apiUrl, { headers });
  }
}
