import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, computed, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { Socket, io } from 'socket.io-client';

interface Ticket { number: number; status: 'waiting' | 'serving' | 'completed'; desk_id: number | null; }
interface Desk { id: number; ticket: Ticket | null; }
interface QueueState { next_ticket: number; waiting: Ticket[]; desks: Desk[]; completed_count: number; last_completed: Ticket | null; }
interface Notice { type: 'success' | 'error'; text: string; }
const EMPTY_STATE: QueueState = { next_ticket: 1, waiting: [], desks: [1, 2, 3, 4].map((id) => ({ id, ticket: null })), completed_count: 0, last_completed: null };
const API_BASE_URL = (window as Window & { __APP_CONFIG__?: { apiBaseUrl?: string } }).__APP_CONFIG__?.apiBaseUrl?.replace(/\/$/, '') || '';

@Component({ selector: 'app-root', templateUrl: './app.html', styleUrl: './app.css' })
export class App implements OnInit, OnDestroy {
  readonly state = signal<QueueState>(EMPTY_STATE);
  readonly busy = signal(false);
  readonly connected = signal(false);
  readonly message = signal<Notice | null>(null);
  readonly occupiedDeskCount = computed(() => this.state().desks.filter((desk) => desk.ticket !== null).length);
  readonly paddedNextTicket = computed(() => this.pad(this.state().next_ticket));
  private socket?: Socket;
  private noticeTimer?: ReturnType<typeof setTimeout>;

  constructor(private readonly http: HttpClient) {}
  async ngOnInit(): Promise<void> {
    await this.loadState();
    this.socket = io(API_BASE_URL || undefined, { transports: ['websocket', 'polling'] });
    this.socket.on('connect', () => this.connected.set(true));
    this.socket.on('disconnect', () => this.connected.set(false));
    this.socket.on('queue_updated', (state: QueueState) => this.state.set(state));
  }
  ngOnDestroy(): void { this.socket?.disconnect(); if (this.noticeTimer) clearTimeout(this.noticeTimer); }
  async createTicket(): Promise<void> {
    await this.runAction(async () => {
      const response = await firstValueFrom(this.http.post<{ ticket: Ticket; state: QueueState }>(this.apiUrl('/api/tickets'), {}));
      this.state.set(response.state);
      const destination = response.ticket.desk_id ? `Mesa ${response.ticket.desk_id}` : 'fila de espera';
      this.notify('success', `Turno A${this.pad(response.ticket.number)} asignado a ${destination}`);
    });
  }
  async finishDesk(deskId: number): Promise<void> {
    await this.runAction(async () => {
      const response = await firstValueFrom(this.http.post<{ assigned: Ticket | null; state: QueueState }>(this.apiUrl(`/api/desks/${deskId}/finish`), {}));
      this.state.set(response.state);
      this.notify('success', response.assigned ? `Mesa ${deskId} llama al turno A${this.pad(response.assigned.number)}` : `Mesa ${deskId} quedó disponible`);
    });
  }
  async reset(): Promise<void> {
    if (!window.confirm('¿Deseas borrar todos los turnos y comenzar una nueva jornada?')) return;
    await this.runAction(async () => {
      const state = await firstValueFrom(this.http.post<QueueState>(this.apiUrl('/api/reset'), {}, { headers: { 'X-Confirm-Reset': 'true' } }));
      this.state.set(state); this.notify('success', 'La jornada comenzó nuevamente');
    });
  }
  pad(value: number): string { return String(value).padStart(3, '0'); }
  private apiUrl(path: string): string { return `${API_BASE_URL}${path}`; }
  private async loadState(): Promise<void> { try { this.state.set(await firstValueFrom(this.http.get<QueueState>(this.apiUrl('/api/state')))); } catch { this.notify('error', 'No fue posible conectar con el servidor'); } }
  private async runAction(action: () => Promise<void>): Promise<void> {
    if (this.busy()) return; this.busy.set(true);
    try { await action(); } catch (error: unknown) { const backendMessage = (error as { error?: { error?: string } })?.error?.error; this.notify('error', backendMessage || 'Ocurrió un error. Intenta nuevamente.'); } finally { this.busy.set(false); }
  }
  private notify(type: Notice['type'], text: string): void { this.message.set({ type, text }); if (this.noticeTimer) clearTimeout(this.noticeTimer); this.noticeTimer = setTimeout(() => this.message.set(null), 4200); }
}

