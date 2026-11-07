import {
  Announcement,
  PersonalEvent,
  PersonalTask,
  Schedule,
  University,
  User,
} from '../types';

// Backend manzilini aniqlash: VITE_API_URL berilgan bo'lsa shuni ishlatadi, aks holda
// joriy sahifa qaysi host (localhost, lokal tarmoq IP'si yoki tunnel domeni) orqali
// ochilgan bo'lsa, backend'ni ham o'sha host'ning 8000-portidan avtomatik topadi -
// shunda telefon lokal Wi-Fi orqali ham, tunnel orqali ham API'ga to'g'ri ulanadi.
function resolveApiBaseUrl(): string {
  const envUrl = import.meta.env.VITE_API_URL;
  if (envUrl) return envUrl;
  if (typeof window !== 'undefined' && window.location?.hostname) {
    return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
  }
  return 'http://localhost:8000/api/v1';
}

const API_BASE_URL = resolveApiBaseUrl();

class ApiClient {
  private token: string | null = null;

  constructor() {
    this.token = localStorage.getItem('uninotify_token');
  }

  setToken(token: string) {
    this.token = token;
    localStorage.setItem('uninotify_token', token);
  }

  getToken(): string | null {
    return this.token;
  }

  clearToken() {
    this.token = null;
    localStorage.removeItem('uninotify_token');
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string>),
    };

    if (this.token) {
      headers['Authorization'] = `Bearer ${this.token}`;
    }

    if (!(options.body instanceof FormData)) {
      headers['Content-Type'] = 'application/json';
    }

    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `Xatolik: ${response.status}`);
    }

    if (response.status === 204) {
      return null as unknown as T;
    }

    return response.json();
  }

  // --- Auth ---
  async authWithTelegram(initData: string) {
    const res = await this.request<{ access_token: string; user: User }>(
      '/auth/telegram-webapp',
      {
        method: 'POST',
        body: JSON.stringify({ init_data: initData }),
      }
    );
    this.setToken(res.access_token);
    return res;
  }

  // --- Profile ---
  async getMe(): Promise<User> {
    return this.request<User>('/users/me');
  }

  async updateMe(data: Partial<Pick<User, 'language_code' | 'university_id' | 'faculty_id' | 'group_id'>>): Promise<User> {
    return this.request<User>('/users/me', {
      method: 'PATCH',
      body: JSON.stringify(data),
    });
  }

  // --- Universities & Groups ---
  async getUniversities(): Promise<University[]> {
    return this.request<University[]>('/universities');
  }

  async getFaculties(universityId: number) {
    return this.request<any[]>(`/faculties?university_id=${universityId}`);
  }

  async getGroups(universityId: number, facultyId?: number) {
    const query = facultyId ? `&faculty_id=${facultyId}` : '';
    return this.request<any[]>(`/groups?university_id=${universityId}${query}`);
  }

  // --- Schedules ---
  async getSchedules(groupId?: number, dayOfWeek?: string): Promise<Schedule[]> {
    const params = new URLSearchParams();
    if (groupId) params.append('group_id', groupId.toString());
    if (dayOfWeek) params.append('day_of_week', dayOfWeek);
    return this.request<Schedule[]>(`/schedules?${params.toString()}`);
  }

  // --- Tasks ---
  async getTasks(isCompleted?: boolean): Promise<PersonalTask[]> {
    const query = isCompleted !== undefined ? `?is_completed=${isCompleted}` : '';
    return this.request<PersonalTask[]>(`/tasks${query}`);
  }

  async createTask(data: Partial<PersonalTask>): Promise<PersonalTask> {
    return this.request<PersonalTask>('/tasks', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async updateTask(id: number, data: Partial<PersonalTask>): Promise<PersonalTask> {
    return this.request<PersonalTask>(`/tasks/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    });
  }

  async deleteTask(id: number): Promise<void> {
    return this.request<void>(`/tasks/${id}`, {
      method: 'DELETE',
    });
  }

  // --- Calendar Events ---
  async getEvents(): Promise<PersonalEvent[]> {
    return this.request<PersonalEvent[]>('/events');
  }

  async createEvent(data: Partial<PersonalEvent>): Promise<PersonalEvent> {
    return this.request<PersonalEvent>('/events', {
      method: 'POST',
      body: JSON.stringify(data),
    });
  }

  async deleteEvent(id: number): Promise<void> {
    return this.request<void>(`/events/${id}`, {
      method: 'DELETE',
    });
  }

  // --- Announcements ---
  async getAnnouncements(): Promise<Announcement[]> {
    return this.request<Announcement[]>('/announcements');
  }

  // --- AI Assistant ---
  async askAIAssistant(query: string) {
    return this.request<{ answer: string; action_type?: string; data?: any }>(
      '/ai/assistant',
      {
        method: 'POST',
        body: JSON.stringify({ query }),
      }
    );
  }

  // --- Schedule Screenshot Upload ---
  async submitScheduleScreenshot(formData: FormData) {
    return this.request<any>('/schedule-submissions', {
      method: 'POST',
      body: formData,
    });
  }
}

export const api = new ApiClient();
