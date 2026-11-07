export type UserRole = 'USER' | 'ADMIN';

export interface User {
  id: number;
  telegram_id: number;
  username?: string;
  first_name: string;
  last_name?: string;
  role: UserRole;
  language_code: string;
  university_id?: number;
  faculty_id?: number;
  group_id?: number;
  is_active: boolean;
}

export interface University {
  id: number;
  name: string;
  short_name?: string;
  city?: string;
  address?: string;
  description?: string;
  is_active: boolean;
}

export interface Faculty {
  id: number;
  university_id: number;
  name: string;
  short_name?: string;
  is_active: boolean;
}

export interface Group {
  id: number;
  university_id: number;
  faculty_id: number;
  name: string;
  course_number?: number;
  field_of_study?: string;
  is_active: boolean;
}

export interface Building {
  id: number;
  name: string;
  address?: string;
}

export interface Room {
  id: number;
  number: string;
  floor?: number;
  capacity?: number;
  room_type: string;
}

export interface Subject {
  id: number;
  name: string;
  code?: string;
}

export interface Teacher {
  id: number;
  full_name: string;
  email?: string;
  phone?: string;
}

export interface Schedule {
  id: number;
  university_id: number;
  group_id: number;
  subject_id: number;
  teacher_id?: number;
  room_id?: number;
  day_of_week: 'MONDAY' | 'TUESDAY' | 'WEDNESDAY' | 'THURSDAY' | 'FRIDAY' | 'SATURDAY' | 'SUNDAY';
  start_time: string;
  end_time: string;
  lesson_type: 'LECTURE' | 'PRACTICE' | 'LAB' | 'SEMINAR' | 'OTHER';
  is_active: boolean;
  subject?: Subject;
  teacher?: Teacher;
  room?: Room;
  group?: Group;
}

export interface PersonalTask {
  id: number;
  user_id: number;
  title: string;
  description?: string;
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
  due_date?: string;
  is_completed: boolean;
  created_at: string;
}

export interface PersonalEvent {
  id: number;
  user_id: number;
  title: string;
  event_type: string;
  description?: string;
  start_time: string;
  end_time?: string;
}

export interface Announcement {
  id: number;
  university_id: number;
  target_group_id?: number;
  title: string;
  content: string;
  is_pinned: boolean;
  created_at: string;
}

export interface AIResponse {
  answer: string;
  action_type?: string;
  data?: any;
}
